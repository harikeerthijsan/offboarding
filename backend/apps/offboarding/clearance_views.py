from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.utils import log_action
from apps.employees.models import Employee

from .models import (
    ResignationRequest, Asset, AssetClearance, DepartmentClearance,
    ClearanceChecklistItem, ASSET_CLEARANCE_FINAL, CLEARANCE_DEPARTMENT_ROLES,
)
from .views import _notify
from .clearance_serializers import (
    AssetSerializer, AssetCreateSerializer, AssetUpdateSerializer,
    AssetClearanceSerializer, AssetClearanceCreateSerializer,
    AssetReturnSerializer, AssetVerifySerializer,
    DepartmentClearanceSerializer, DepartmentClearanceCreateSerializer,
    DepartmentClearanceActionSerializer,
    ClearanceChecklistItemSerializer, ChecklistItemCreateSerializer,
    ChecklistItemUpdateSerializer,
)

User = get_user_model()

ASSET_ACTION_ROLES = {'IT', 'ADMIN', 'HR'}  # may record returns / verify assets


# ─── helpers ─────────────────────────────────────────────────────────────────

def _employee_for(user):
    try:
        return Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        return None


def _is_manager_of(employee, user):
    if not employee:
        return False
    mgr = _employee_for(user)
    return bool(mgr and employee.manager_id == mgr.pk)


def _can_view_offboarding(resignation, user):
    role = user.role
    if role in ('HR', 'ADMIN', 'IT', 'FINANCE'):
        return True
    if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
        return True
    return resignation.employee.user_id == user.pk


def _can_act_department(dept_clearance, user):
    """Whether user may act on a department clearance / its checklist."""
    role = user.role
    allowed_roles = CLEARANCE_DEPARTMENT_ROLES.get(dept_clearance.department, set())
    if role == 'ADMIN':
        return True
    if dept_clearance.department == 'MANAGER':
        return _is_manager_of(dept_clearance.offboarding_request.employee, user)
    return role in allowed_roles


def _notify_hr(title, message, obj):
    for hr_user in User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True):
        _notify(hr_user, 'STATUS_UPDATE', title, message, obj)


def _create_it_asset_clearance(resignation):
    """Set up the IT asset clearance after the employee's asset declaration:
    an IT department clearance + a checklist item, and queue each of the
    employee's assigned assets for IT to confirm return. Idempotent."""
    emp = resignation.employee

    it_dc, _ = DepartmentClearance.objects.get_or_create(
        offboarding_request=resignation, department='IT', defaults={'status': 'PENDING'})
    ClearanceChecklistItem.objects.get_or_create(
        department_clearance=it_dc, title='Company assets returned & verified',
        defaults={'status': 'PENDING'})

    for asset in Asset.objects.filter(assigned_to=emp).exclude(status__in=['CLEARED', 'LOST']):
        _, made = AssetClearance.objects.get_or_create(
            offboarding_request=resignation, asset=asset,
            defaults={'employee': emp, 'status': 'RETURN_PENDING'})
        if made and asset.status == 'ASSIGNED':
            Asset.objects.filter(pk=asset.pk).update(status='RETURN_PENDING')


# ─── Assets (catalogue) ──────────────────────────────────────────────────────

class AssetListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Employees may only see their own assets here; privileged roles see all.
        role = request.user.role
        qs = Asset.objects.select_related('assigned_to').all()
        if role not in ('IT', 'ADMIN', 'HR', 'FINANCE', 'MANAGER'):
            emp = _employee_for(request.user)
            qs = qs.filter(assigned_to=emp) if emp else Asset.objects.none()

        p = request.query_params
        if p.get('asset_type'):
            qs = qs.filter(asset_type=p['asset_type'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('condition'):
            qs = qs.filter(condition=p['condition'])
        if p.get('assigned_to'):
            qs = qs.filter(assigned_to_id=p['assigned_to'])
        search = p.get('search')
        if search:
            qs = qs.filter(
                Q(asset_id__icontains=search) | Q(serial_number__icontains=search) |
                Q(asset_name__icontains=search)
            )
        return Response(AssetSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role not in ('IT', 'ADMIN'):
            return Response({'detail': 'Only IT or Admin can create assets.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssetCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # status defaults to ASSIGNED if assigned_to given, else ASSIGNED regardless (catalogue default)
        asset = serializer.save()
        log_action(actor=request.user, action='ASSET_CREATED', target_obj=asset,
                   changes={'asset_id': asset.asset_id, 'type': asset.asset_type,
                            'assigned_to': asset.assigned_to_id}, request=request)
        return Response(AssetSerializer(asset).data, status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            asset = Asset.objects.select_related('assigned_to').get(pk=pk)
        except Asset.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Employee may only view own asset
        if request.user.role not in ('IT', 'ADMIN', 'HR', 'FINANCE', 'MANAGER'):
            emp = _employee_for(request.user)
            if not emp or asset.assigned_to_id != emp.pk:
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(AssetSerializer(asset).data)

    def patch(self, request, pk):
        if request.user.role not in ('IT', 'ADMIN'):
            return Response({'detail': 'Only IT or Admin can update assets.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            asset = Asset.objects.get(pk=pk)
        except Asset.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssetUpdateSerializer(asset, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        was_assigned = asset.assigned_to_id
        asset = serializer.save()
        action = 'ASSET_ASSIGNED' if (not was_assigned and asset.assigned_to_id) else 'ASSET_UPDATED'
        log_action(actor=request.user, action=action, target_obj=asset,
                   changes=serializer.validated_data, request=request)
        return Response(AssetSerializer(asset).data)


class EmployeeAssetsView(APIView):
    """GET /api/employees/{pk}/assets/  (pk = Employee id)"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            emp = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        role = request.user.role
        if role not in ('IT', 'ADMIN', 'HR', 'FINANCE', 'MANAGER') and emp.user_id != request.user.pk:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        assets = Asset.objects.filter(assigned_to=emp)
        return Response(AssetSerializer(assets, many=True).data)


# ─── Asset Clearance (per offboarding) ───────────────────────────────────────

def _sync_asset_status(asset, new_status):
    Asset.objects.filter(pk=asset.pk).update(status=new_status)


class AssetClearanceListCreateView(APIView):
    """GET/POST /api/offboarding/{pk}/assets/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        qs = AssetClearance.objects.select_related('asset', 'employee', 'verified_by').filter(
            offboarding_request=resignation)
        p = request.query_params
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('condition'):
            qs = qs.filter(condition_at_return=p['condition'])
        if p.get('asset_type'):
            qs = qs.filter(asset__asset_type=p['asset_type'])
        search = p.get('search')
        if search:
            qs = qs.filter(Q(asset__asset_id__icontains=search) |
                           Q(asset__serial_number__icontains=search) |
                           Q(asset__asset_name__icontains=search))
        return Response(AssetClearanceSerializer(qs, many=True).data)

    def post(self, request, pk):
        if request.user.role not in ASSET_ACTION_ROLES:
            return Response({'detail': 'Only IT, HR, or Admin can add assets to clearance.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            serializer = AssetClearanceCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            asset = serializer.validated_data['asset']

            if asset.assigned_to_id != resignation.employee_id:
                return Response({'detail': 'This asset is not assigned to the offboarding employee.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if AssetClearance.objects.filter(offboarding_request=resignation, asset=asset).exists():
                return Response({'detail': 'This asset is already part of the clearance.'},
                                status=status.HTTP_400_BAD_REQUEST)

            ac = AssetClearance.objects.create(
                offboarding_request=resignation, asset=asset,
                employee=resignation.employee, status='RETURN_PENDING',
            )
            _sync_asset_status(asset, 'RETURN_PENDING')
            log_action(actor=request.user, action='ASSET_RETURN_RECORDED', target_obj=ac,
                       changes={'asset': asset.asset_id, 'status': 'RETURN_PENDING'}, request=request)
            _notify(resignation.employee.user, 'ACTION_REQUIRED', 'Asset return required',
                    f'Please return your assigned asset "{asset.asset_name}".', ac)

        return Response(
            AssetClearanceSerializer(
                AssetClearance.objects.select_related('asset', 'employee', 'verified_by').get(pk=ac.pk)
            ).data, status=status.HTTP_201_CREATED)


class AssetClearanceDetailView(APIView):
    """PATCH /api/asset-clearance/{pk}/ — record return / verify / reject / damaged / lost."""
    permission_classes = [IsAuthenticated]

    def _resp(self, ac_pk, http_status=status.HTTP_200_OK):
        ac = AssetClearance.objects.select_related('asset', 'employee', 'verified_by').get(pk=ac_pk)
        return Response(AssetClearanceSerializer(ac).data, status=http_status)

    def get(self, request, pk):
        try:
            ac = AssetClearance.objects.select_related('asset', 'employee', 'verified_by',
                                                       'offboarding_request__employee').get(pk=pk)
        except AssetClearance.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(ac.offboarding_request, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return self._resp(pk)

    def patch(self, request, pk):
        # 'record_return' action or verification actions
        action = request.data.get('action')
        if action == 'record_return':
            return self._record_return(request, pk)
        return self._verify(request, pk)

    def _record_return(self, request, pk):
        if request.user.role not in ASSET_ACTION_ROLES:
            return Response({'detail': 'Only IT, HR, or Admin can record an asset return.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = AssetReturnSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            try:
                ac = AssetClearance.objects.select_for_update().select_related('asset', 'employee').get(pk=pk)
            except AssetClearance.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            if not ac.can_transition_to('RETURNED'):
                return Response({'detail': f'Cannot record return from status {ac.status}.'},
                                status=status.HTTP_400_BAD_REQUEST)
            old = ac.status
            ac.status = 'RETURNED'
            ac.return_date = serializer.validated_data['return_date']  # manual
            ac.condition_at_return = serializer.validated_data['condition']
            ac.remarks = serializer.validated_data.get('remarks', '')
            ac.save(update_fields=['status', 'return_date', 'condition_at_return', 'remarks', 'updated_at'])
            _sync_asset_status(ac.asset, 'RETURNED')
            log_action(actor=request.user, action='ASSET_RETURN_RECORDED', target_obj=ac,
                       changes={'status': {'from': old, 'to': 'RETURNED'},
                                'return_date': str(ac.return_date), 'condition': ac.condition_at_return},
                       request=request)
            _notify_hr('Asset returned', f'Asset "{ac.asset.asset_name}" was recorded as returned.', ac)
        return self._resp(pk)

    def _verify(self, request, pk):
        if request.user.role not in ASSET_ACTION_ROLES:
            return Response({'detail': 'Only IT, HR, or Admin can verify assets.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = AssetVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')
        with transaction.atomic():
            try:
                ac = AssetClearance.objects.select_for_update().select_related('asset', 'employee').get(pk=pk)
            except AssetClearance.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            target = {'verify': 'CLEARED', 'reject': 'REJECTED',
                      'mark_damaged': 'DAMAGED', 'mark_lost': 'LOST'}[action]
            if not ac.can_transition_to(target):
                return Response({'detail': f'Cannot {action} from status {ac.status}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            old = ac.status
            now = timezone.now()
            ac.status = target
            ac.verified_by = request.user
            ac.verified_at = now
            if comments:
                ac.remarks = comments
            ac.save(update_fields=['status', 'verified_by', 'verified_at', 'remarks', 'updated_at'])
            _sync_asset_status(ac.asset, target)

            audit = {'verify': 'ASSET_VERIFIED', 'reject': 'ASSET_REJECTED',
                     'mark_damaged': 'ASSET_DAMAGED', 'mark_lost': 'ASSET_LOST'}[action]
            log_action(actor=request.user, action=audit, target_obj=ac,
                       changes={'status': {'from': old, 'to': target}, 'comments': comments}, request=request)
            if action == 'reject':
                _notify(ac.employee.user, 'ACTION_REQUIRED', 'Asset verification rejected',
                        f'Verification of "{ac.asset.asset_name}" was rejected: {comments}', ac)
            else:
                _notify(ac.employee.user, 'STATUS_UPDATE', 'Asset verification updated',
                        f'Asset "{ac.asset.asset_name}" is now {ac.get_status_display()}.', ac)
        return self._resp(pk)


# ─── Department Clearance ────────────────────────────────────────────────────

class DepartmentClearanceListCreateView(APIView):
    """GET/POST /api/offboarding/{pk}/clearances/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        qs = DepartmentClearance.objects.prefetch_related('checklist_items__completed_by').select_related(
            'assigned_to', 'cleared_by').filter(offboarding_request=resignation)
        p = request.query_params
        if p.get('department'):
            qs = qs.filter(department=p['department'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        return Response(DepartmentClearanceSerializer(qs, many=True).data)

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can set up clearances.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            serializer = DepartmentClearanceCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            department = serializer.validated_data['department']
            if DepartmentClearance.objects.filter(offboarding_request=resignation, department=department).exists():
                return Response({'detail': f'{department} clearance already exists.'},
                                status=status.HTTP_400_BAD_REQUEST)
            dc = DepartmentClearance.objects.create(
                offboarding_request=resignation, department=department,
                assigned_to=serializer.validated_data.get('assigned_to'), status='PENDING',
            )
            log_action(actor=request.user, action='DEPARTMENT_CLEARANCE_CREATED', target_obj=dc,
                       changes={'department': department}, request=request)
        return Response(DepartmentClearanceSerializer(dc).data, status=status.HTTP_201_CREATED)


class DepartmentClearanceDetailView(APIView):
    """PATCH /api/clearances/{pk}/ — clear/reject/in_progress/not_applicable/reopen."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            dc = DepartmentClearance.objects.prefetch_related('checklist_items').select_related(
                'offboarding_request__employee', 'assigned_to', 'cleared_by').get(pk=pk)
        except DepartmentClearance.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(dc.offboarding_request, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(DepartmentClearanceSerializer(dc).data)

    def patch(self, request, pk):
        serializer = DepartmentClearanceActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')
        clearance_date = serializer.validated_data.get('clearance_date')

        with transaction.atomic():
            try:
                dc = DepartmentClearance.objects.select_for_update().select_related(
                    'offboarding_request__employee').get(pk=pk)
            except DepartmentClearance.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not _can_act_department(dc, request.user):
                return Response({'detail': 'You are not authorised to act on this clearance.'},
                                status=status.HTTP_403_FORBIDDEN)

            old = dc.status
            now = timezone.now()

            if action == 'clear':
                # All checklist items must be resolved (COMPLETED or NOT_APPLICABLE)
                unresolved = dc.checklist_items.filter(status='PENDING').count()
                if unresolved:
                    return Response({'detail': f'{unresolved} checklist item(s) are still pending.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                dc.status = 'CLEARED'
                dc.clearance_date = clearance_date  # manual
                dc.cleared_by = request.user
                dc.cleared_at = now
                dc.comments = comments or dc.comments
                dc.save(update_fields=['status', 'clearance_date', 'cleared_by', 'cleared_at', 'comments', 'updated_at'])
                audit = 'DEPARTMENT_CLEARANCE_COMPLETED'
                _notify_hr(f'{dc.department} clearance completed',
                           f'{dc.get_department_display()} clearance completed for '
                           f'{dc.offboarding_request.employee.first_name} {dc.offboarding_request.employee.last_name}.', dc)
            elif action == 'reject':
                dc.status = 'REJECTED'
                dc.comments = comments
                dc.save(update_fields=['status', 'comments', 'updated_at'])
                audit = 'DEPARTMENT_CLEARANCE_REJECTED'
                _notify_hr(f'{dc.department} clearance rejected',
                           f'{dc.get_department_display()} clearance was rejected: {comments}', dc)
            elif action == 'in_progress':
                dc.status = 'IN_PROGRESS'
                dc.comments = comments or dc.comments
                dc.save(update_fields=['status', 'comments', 'updated_at'])
                audit = 'DEPARTMENT_CLEARANCE_UPDATED'
            elif action == 'not_applicable':
                dc.status = 'NOT_APPLICABLE'
                dc.comments = comments or dc.comments
                dc.save(update_fields=['status', 'comments', 'updated_at'])
                audit = 'DEPARTMENT_CLEARANCE_UPDATED'
            else:  # reopen
                dc.status = 'IN_PROGRESS'
                dc.clearance_date = None
                dc.cleared_by = None
                dc.cleared_at = None
                dc.save(update_fields=['status', 'clearance_date', 'cleared_by', 'cleared_at', 'updated_at'])
                audit = 'DEPARTMENT_CLEARANCE_UPDATED'

            log_action(actor=request.user, action=audit, target_obj=dc,
                       changes={'status': {'from': old, 'to': dc.status}, 'comments': comments}, request=request)

        return Response(DepartmentClearanceSerializer(
            DepartmentClearance.objects.prefetch_related('checklist_items').select_related(
                'assigned_to', 'cleared_by').get(pk=pk)).data)


# ─── Checklist items ─────────────────────────────────────────────────────────

class ChecklistListCreateView(APIView):
    """GET/POST /api/clearances/{pk}/checklist/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            dc = DepartmentClearance.objects.select_related('offboarding_request__employee').get(pk=pk)
        except DepartmentClearance.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(dc.offboarding_request, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        items = dc.checklist_items.select_related('completed_by').all()
        return Response(ClearanceChecklistItemSerializer(items, many=True).data)

    def post(self, request, pk):
        try:
            dc = DepartmentClearance.objects.select_related('offboarding_request__employee').get(pk=pk)
        except DepartmentClearance.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # HR/Admin configure checklists, or the department's own responsible role
        if not (request.user.role in ('HR', 'ADMIN') or _can_act_department(dc, request.user)):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ChecklistItemCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        item = serializer.save(department_clearance=dc, status='PENDING')
        log_action(actor=request.user, action='CHECKLIST_ITEM_CREATED', target_obj=item,
                   changes={'title': item.title}, request=request)
        return Response(ClearanceChecklistItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ChecklistItemDetailView(APIView):
    """PATCH /api/checklist/{pk}/ — complete / not_applicable / reset / reject."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = ChecklistItemUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')

        with transaction.atomic():
            try:
                item = ClearanceChecklistItem.objects.select_for_update().select_related(
                    'department_clearance__offboarding_request__employee').get(pk=pk)
            except ClearanceChecklistItem.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not _can_act_department(item.department_clearance, request.user):
                return Response({'detail': 'You are not authorised to act on this checklist.'},
                                status=status.HTTP_403_FORBIDDEN)

            old = item.status
            now = timezone.now()
            if action == 'complete':
                item.status = 'COMPLETED'
                item.completed_by = request.user
                item.completed_at = now
                item.comments = comments or item.comments
                audit = 'CHECKLIST_ITEM_COMPLETED'
            elif action == 'not_applicable':
                item.status = 'NOT_APPLICABLE'
                item.completed_by = request.user
                item.completed_at = now
                item.comments = comments or item.comments
                audit = 'CHECKLIST_ITEM_COMPLETED'
            elif action == 'reject':
                item.status = 'PENDING'
                item.completed_by = None
                item.completed_at = None
                item.comments = comments
                audit = 'CHECKLIST_ITEM_REJECTED'
            else:  # reset
                item.status = 'PENDING'
                item.completed_by = None
                item.completed_at = None
                audit = 'CHECKLIST_ITEM_REJECTED'
            item.save(update_fields=['status', 'completed_by', 'completed_at', 'comments'])
            log_action(actor=request.user, action=audit, target_obj=item,
                       changes={'status': {'from': old, 'to': item.status}, 'comments': comments}, request=request)

        return Response(ClearanceChecklistItemSerializer(
            ClearanceChecklistItem.objects.select_related('completed_by').get(pk=pk)).data)


# ─── Summary & completion ────────────────────────────────────────────────────

class ClearanceSummaryView(APIView):
    """GET /api/offboarding/{pk}/clearance/summary/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        depts = DepartmentClearance.objects.filter(offboarding_request=resignation)
        assets = AssetClearance.objects.filter(offboarding_request=resignation)

        dept_counts = {'total': depts.count(), 'cleared': 0, 'pending': 0,
                       'in_progress': 0, 'rejected': 0, 'not_applicable': 0}
        for s in depts.values_list('status', flat=True):
            key = {'CLEARED': 'cleared', 'PENDING': 'pending', 'IN_PROGRESS': 'in_progress',
                   'REJECTED': 'rejected', 'NOT_APPLICABLE': 'not_applicable'}[s]
            dept_counts[key] += 1

        asset_counts = {'total': assets.count(), 'returned': 0, 'pending': 0,
                        'cleared': 0, 'damaged': 0, 'lost': 0, 'rejected': 0}
        for s in assets.values_list('status', flat=True):
            key = {'RETURNED': 'returned', 'RETURN_PENDING': 'pending', 'CLEARED': 'cleared',
                   'DAMAGED': 'damaged', 'LOST': 'lost', 'REJECTED': 'rejected'}[s]
            asset_counts[key] += 1

        decl_by = resignation.asset_declaration_by
        decl_by_name = None
        if decl_by:
            decl_by_name = f"{decl_by.first_name} {decl_by.last_name}".strip() or decl_by.email

        return Response({
            'departments': dept_counts,
            'assets': asset_counts,
            'clearance_completed': resignation.clearance_completed_at is not None,
            'clearance_completed_at': resignation.clearance_completed_at,
            'asset_declaration_submitted': resignation.asset_declaration_at is not None,
            'asset_declaration_at': resignation.asset_declaration_at,
            'asset_declaration_by_name': decl_by_name,
            'asset_declaration_notes': resignation.asset_declaration_notes,
        })


class AssetDeclarationView(APIView):
    """POST /api/offboarding/{pk}/asset-declaration/ — the departing employee
    declares they have returned/submitted all company assets. Notes optional."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Only the offboarding employee (or admin) may make the declaration.
            is_owner = resignation.employee.user_id == request.user.pk
            if not (is_owner or request.user.role == 'ADMIN'):
                return Response({'detail': 'Only the offboarding employee can make this declaration.'},
                                status=status.HTTP_403_FORBIDDEN)

            if resignation.status not in ('APPROVED', 'NOTICE_PERIOD'):
                return Response(
                    {'detail': 'The asset declaration is only available once the offboarding is approved and in progress.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if resignation.asset_declaration_at is not None:
                return Response({'detail': 'You have already submitted the asset declaration.'},
                                status=status.HTTP_400_BAD_REQUEST)

            notes = (request.data.get('notes') or '').strip()
            resignation.asset_declaration_at = timezone.now()
            resignation.asset_declaration_by = request.user
            resignation.asset_declaration_notes = notes
            resignation.save(update_fields=[
                'asset_declaration_at', 'asset_declaration_by', 'asset_declaration_notes', 'updated_at',
            ])
            log_action(actor=request.user, action='ASSET_DECLARATION_SUBMITTED', target_obj=resignation,
                       changes={'notes': notes}, request=request)

            # The declaration unlocks the IT asset clearance.
            _create_it_asset_clearance(resignation)
            log_action(actor=request.user, action='CLEARANCES_AUTO_CREATED', target_obj=resignation,
                       changes={'departments': ['IT']}, request=request)

            name = f"{resignation.employee.first_name} {resignation.employee.last_name}".strip()
            for u in User.objects.filter(role__in=['IT', 'ADMIN'], is_active=True):
                _notify(u, 'CLEARANCE_ACTION_REQUIRED', 'IT asset clearance required',
                        f'{name} has declared all company assets returned. '
                        f'Please verify asset returns and complete IT clearance.', resignation)
            _notify_hr('Asset return declaration submitted',
                       f'{name} has declared that all company assets have been returned.', resignation)

        return Response({
            'detail': 'Asset declaration submitted. IT asset clearance has been created.',
            'asset_declaration_at': resignation.asset_declaration_at,
            'asset_declaration_notes': resignation.asset_declaration_notes,
        })


class ClearanceCompleteView(APIView):
    """POST /api/offboarding/{pk}/clearance/complete/ — explicit 'Mark Clearance Complete'."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can mark clearance complete.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            depts = DepartmentClearance.objects.filter(offboarding_request=resignation)
            assets = AssetClearance.objects.filter(offboarding_request=resignation)

            if not depts.exists():
                return Response({'detail': 'No department clearances have been set up.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # No unresolved rejections
            if depts.filter(status='REJECTED').exists() or assets.filter(status='REJECTED').exists():
                return Response({'detail': 'There are unresolved rejected items.'},
                                status=status.HTTP_400_BAD_REQUEST)
            # All required departments cleared or N/A
            not_done = depts.exclude(status__in=['CLEARED', 'NOT_APPLICABLE']).count()
            if not_done:
                return Response({'detail': f'{not_done} department clearance(s) are not yet complete.'},
                                status=status.HTTP_400_BAD_REQUEST)
            # All assets resolved (cleared/lost/damaged)
            assets_pending = assets.exclude(status__in=list(ASSET_CLEARANCE_FINAL)).count()
            if assets_pending:
                return Response({'detail': f'{assets_pending} asset(s) are not yet cleared.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if resignation.clearance_completed_at is not None:
                return Response({'detail': 'Clearance is already marked complete.'},
                                status=status.HTTP_400_BAD_REQUEST)

            resignation.clearance_completed_by = request.user
            resignation.clearance_completed_at = timezone.now()
            resignation.save(update_fields=['clearance_completed_by', 'clearance_completed_at', 'updated_at'])
            log_action(actor=request.user, action='CLEARANCE_COMPLETED', target_obj=resignation,
                       changes={'departments': depts.count(), 'assets': assets.count()}, request=request)
            _notify(resignation.employee.user, 'STATUS_UPDATE', 'Clearance completed',
                    'All required clearances for your offboarding are complete.', resignation)
            _notify_hr('Clearance completed',
                       f'Clearance for {resignation.employee.first_name} {resignation.employee.last_name} is complete.',
                       resignation)

        return Response({'detail': 'Clearance marked complete.',
                         'clearance_completed_at': resignation.clearance_completed_at})


class MyClearanceQueueView(APIView):
    """GET /api/clearances/queue/ — offboardings with a department clearance the
    current user is authorised to act on (IT, Finance, HR, Manager, Admin)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role
        # which departments can this user act on?
        actable = {dept for dept, roles in CLEARANCE_DEPARTMENT_ROLES.items() if role in roles}
        if role == 'ADMIN':
            actable = set(CLEARANCE_DEPARTMENT_ROLES.keys())

        dcs = (DepartmentClearance.objects
               .select_related('offboarding_request__employee__department')
               .filter(department__in=actable,
                       status__in=['PENDING', 'IN_PROGRESS', 'REJECTED'])
               .exclude(offboarding_request__status__in=['REJECTED', 'CANCELLED', 'COMPLETED'])
               .order_by('-created_at'))

        rows = []
        for dc in dcs:
            # MANAGER department requires being the employee's direct manager
            if dc.department == 'MANAGER' and role != 'ADMIN' and not _is_manager_of(
                    dc.offboarding_request.employee, user):
                continue
            r = dc.offboarding_request
            e = r.employee
            pending_assets = 0
            if dc.department == 'IT':
                pending_assets = AssetClearance.objects.filter(
                    offboarding_request=r).exclude(status__in=list(ASSET_CLEARANCE_FINAL)).count()
            rows.append({
                'offboarding_id': r.id,
                'department': dc.department,
                'department_display': dc.get_department_display(),
                'status': dc.status,
                'status_display': dc.get_status_display(),
                'employee_name': f"{e.first_name} {e.last_name}",
                'employee_id': e.employee_id,
                'employee_department': e.department.name if e.department else '',
                'pending_assets': pending_assets,
            })
        return Response(rows)
