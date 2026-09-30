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
    ResignationRequest, Project, KnowledgeTransfer, KTDocument,
    DepartmentClearance, ClearanceChecklistItem, Asset, AssetClearance,
)
from .views import _notify
from .kt_serializers import (
    ProjectSerializer,
    KnowledgeTransferCreateSerializer,
    KTEmployeeUpdateSerializer,
    KTManagerUpdateSerializer,
    KnowledgeTransferListSerializer,
    KnowledgeTransferDetailSerializer,
    KTReceiverActionSerializer,
    KTManagerActionSerializer,
    KTReassignSerializer,
    KTDocumentSerializer,
    KTDocumentCreateSerializer,
)

User = get_user_model()


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
    if role in ('HR', 'ADMIN'):
        return True
    if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
        return True
    return resignation.employee.user_id == user.pk


def _can_manage_kt_creation(resignation, user):
    """Manager (of the employee), HR, Admin may create/assign KT."""
    role = user.role
    if role in ('HR', 'ADMIN'):
        return True
    if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
        return True
    return False


def _can_view_kt(kt, user):
    role = user.role
    if role in ('HR', 'ADMIN'):
        return True
    if kt.assigned_to.user_id == user.pk:      # offboarding employee
        return True
    if kt.receiver.user_id == user.pk:         # receiver
        return True
    if role == 'MANAGER' and _is_manager_of(kt.assigned_to, user):
        return True
    return False


def _kt_detail_response(kt_pk, http_status=status.HTTP_200_OK):
    kt = KnowledgeTransfer.objects.select_related(
        'project', 'assigned_to', 'receiver',
        'receiver_reviewed_by', 'manager_reviewed_by', 'created_by',
    ).prefetch_related('documents__added_by').get(pk=kt_pk)
    return Response(KnowledgeTransferDetailSerializer(kt).data, status=http_status)


def _notify_hr(title, message, obj):
    for hr_user in User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True):
        _notify(hr_user, 'STATUS_UPDATE', title, message, obj)


def _auto_create_clearances(resignation):
    """Once notice period + KT are done, set up the IT asset clearance and the
    Finance clearance so IT and HR/Finance can action them (no manual add needed).
    Returns the list of departments newly created."""
    created = []
    emp = resignation.employee

    # IT clearance — asset return confirmation
    it_dc, made_it = DepartmentClearance.objects.get_or_create(
        offboarding_request=resignation, department='IT', defaults={'status': 'PENDING'})
    if made_it:
        created.append('IT')
        ClearanceChecklistItem.objects.get_or_create(
            department_clearance=it_dc, title='Company assets returned & verified',
            defaults={'status': 'PENDING'})

    # Queue the employee's assigned assets for IT to confirm return
    for asset in Asset.objects.filter(assigned_to=emp).exclude(status__in=['CLEARED', 'LOST']):
        _, made = AssetClearance.objects.get_or_create(
            offboarding_request=resignation, asset=asset,
            defaults={'employee': emp, 'status': 'RETURN_PENDING'})
        if made and asset.status == 'ASSIGNED':
            Asset.objects.filter(pk=asset.pk).update(status='RETURN_PENDING')

    # Finance clearance — HR or Finance can sign off
    _, made_fin = DepartmentClearance.objects.get_or_create(
        offboarding_request=resignation, department='FINANCE', defaults={'status': 'PENDING'})
    if made_fin:
        created.append('FINANCE')

    return created


# ─── Projects ────────────────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Project.objects.select_related('department', 'manager').all()
        if request.query_params.get('active') == 'true':
            qs = qs.filter(is_active=True)
        dept = request.query_params.get('department')
        if dept:
            qs = qs.filter(department_id=dept)
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
        return Response(ProjectSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role not in ('MANAGER', 'HR', 'ADMIN'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProjectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        project = serializer.save()
        log_action(
            actor=request.user, action='PROJECT_CREATED', target_obj=project,
            changes={'name': project.name, 'code': project.code}, request=request,
        )
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = Project.objects.select_related('department', 'manager').get(pk=pk)
        except Project.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectSerializer(project).data)

    def patch(self, request, pk):
        if request.user.role not in ('MANAGER', 'HR', 'ADMIN'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        project = serializer.save()
        log_action(actor=request.user, action='PROJECT_UPDATED', target_obj=project,
                   changes=serializer.validated_data, request=request)
        return Response(ProjectSerializer(project).data)


# ─── KT list / create (per offboarding) ──────────────────────────────────────

class KTListCreateView(APIView):
    """GET/POST /api/offboarding/{pk}/kt/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        qs = KnowledgeTransfer.objects.select_related(
            'project', 'assigned_to', 'receiver',
        ).filter(offboarding_request=resignation)

        # Filters
        params = request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('priority'):
            qs = qs.filter(priority=params['priority'])
        if params.get('project'):
            qs = qs.filter(project_id=params['project'])
        if params.get('receiver'):
            qs = qs.filter(receiver_id=params['receiver'])
        if params.get('assigned_to'):
            qs = qs.filter(assigned_to_id=params['assigned_to'])
        search = params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(responsibility__icontains=search)
            )

        # Sorting (whitelist)
        ordering = params.get('ordering')
        allowed = {
            'created_at', '-created_at', 'target_completion_date', '-target_completion_date',
            'priority', '-priority', 'status', '-status', 'title', '-title',
        }
        if ordering in allowed:
            qs = qs.order_by(ordering)

        return Response(KnowledgeTransferListSerializer(qs, many=True).data)

    def post(self, request, pk):
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not _can_manage_kt_creation(resignation, request.user):
                return Response({'detail': 'Only a manager, HR, or admin can create KT items.'},
                                status=status.HTTP_403_FORBIDDEN)

            if resignation.status not in ('APPROVED', 'NOTICE_PERIOD'):
                return Response(
                    {'detail': f'Knowledge transfer can only be set up for an approved offboarding in progress (status {resignation.status}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = KnowledgeTransferCreateSerializer(
                data=request.data,
                context={'offboarding_employee': resignation.employee},
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            kt = serializer.save(
                offboarding_request=resignation,
                assigned_to=resignation.employee,   # derived server-side, not from payload
                created_by=request.user,
                status='PENDING',
            )
            log_action(
                actor=request.user, action='KT_CREATED', target_obj=kt,
                changes={
                    'title': kt.title,
                    'receiver': kt.receiver_id,
                    'priority': kt.priority,
                    'status': 'PENDING',
                },
                request=request,
            )
            _notify(
                resignation.employee.user, 'ACTION_REQUIRED',
                'New knowledge transfer assigned',
                f'A knowledge transfer task "{kt.title}" has been assigned to you.',
                kt,
            )

        return _kt_detail_response(kt.pk, http_status=status.HTTP_201_CREATED)


class KTSummaryView(APIView):
    """GET /api/offboarding/{pk}/kt/summary/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_offboarding(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        qs = KnowledgeTransfer.objects.filter(offboarding_request=resignation)
        counts = {s: 0 for s, _ in KnowledgeTransfer._meta.get_field('status').choices}
        for row in qs.values_list('status', flat=True):
            counts[row] = counts.get(row, 0) + 1
        total = qs.count()

        return Response({
            'total': total,
            'pending': counts.get('PENDING', 0),
            'in_progress': counts.get('IN_PROGRESS', 0),
            'submitted': counts.get('SUBMITTED', 0),
            'receiver_review': counts.get('RECEIVER_REVIEW', 0),
            'manager_review': counts.get('MANAGER_REVIEW', 0),
            'completed': counts.get('COMPLETED', 0),
            'rejected': counts.get('REJECTED', 0),
            'kt_phase_completed': resignation.kt_completed_at is not None,
            'kt_phase_completed_at': resignation.kt_completed_at,
        })


class KTPhaseCompleteView(APIView):
    """POST /api/offboarding/{pk}/kt/complete/ — explicit 'Mark Knowledge Transfer Complete'."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not _can_manage_kt_creation(resignation, request.user):
                return Response({'detail': 'Only a manager, HR, or admin can mark KT complete.'},
                                status=status.HTTP_403_FORBIDDEN)

            qs = KnowledgeTransfer.objects.filter(offboarding_request=resignation)
            if not qs.exists():
                return Response({'detail': 'There are no KT tasks to complete.'},
                                status=status.HTTP_400_BAD_REQUEST)

            incomplete = qs.exclude(status='COMPLETED').count()
            if incomplete:
                return Response(
                    {'detail': f'Cannot mark KT complete: {incomplete} task(s) are not yet completed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if resignation.kt_completed_at is not None:
                return Response({'detail': 'Knowledge transfer is already marked complete.'},
                                status=status.HTTP_400_BAD_REQUEST)

            resignation.kt_completed_by = request.user
            resignation.kt_completed_at = timezone.now()
            resignation.save(update_fields=['kt_completed_by', 'kt_completed_at', 'updated_at'])

            log_action(
                actor=request.user, action='KT_PHASE_COMPLETED', target_obj=resignation,
                changes={'kt_task_count': qs.count()}, request=request,
            )
            _notify(
                resignation.employee.user, 'STATUS_UPDATE',
                'Knowledge transfer complete',
                'All of your knowledge transfer tasks have been completed and signed off.',
                resignation,
            )
            _notify_hr(
                'Knowledge transfer complete',
                f'Knowledge transfer for {resignation.employee.first_name} {resignation.employee.last_name} is complete.',
                resignation,
            )

            # Auto-create the next clearance steps: IT asset clearance + Finance clearance
            created = _auto_create_clearances(resignation)
            log_action(actor=request.user, action='CLEARANCES_AUTO_CREATED', target_obj=resignation,
                       changes={'departments': created}, request=request)
            name = f"{resignation.employee.first_name} {resignation.employee.last_name}"
            if 'IT' in created:
                for u in User.objects.filter(role__in=['IT', 'ADMIN'], is_active=True):
                    _notify(u, 'CLEARANCE_ACTION_REQUIRED', 'IT asset clearance required',
                            f'Please confirm asset return and clearance for {name}.', resignation)
            if 'FINANCE' in created:
                for u in User.objects.filter(role__in=['FINANCE', 'HR', 'ADMIN'], is_active=True):
                    _notify(u, 'CLEARANCE_ACTION_REQUIRED', 'Finance clearance required',
                            f'Please complete finance clearance for {name}.', resignation)

        return Response({
            'detail': 'Knowledge transfer marked complete. IT asset clearance and finance clearance have been created.',
            'kt_completed_at': resignation.kt_completed_at,
            'clearances_created': created,
        })


# ─── KT detail / update ──────────────────────────────────────────────────────

class KTDetailView(APIView):
    """GET/PATCH /api/kt/{pk}/"""
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        return KnowledgeTransfer.objects.select_related(
            'offboarding_request', 'assigned_to', 'receiver', 'project',
        ).get(pk=pk)

    def get(self, request, pk):
        try:
            kt = self._get(pk)
        except KnowledgeTransfer.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_kt(kt, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return _kt_detail_response(kt.pk)

    def patch(self, request, pk):
        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related(
                    'assigned_to', 'receiver',
                ).get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            role = request.user.role
            is_owner = kt.assigned_to.user_id == request.user.pk
            is_privileged = role in ('HR', 'ADMIN') or (role == 'MANAGER' and _is_manager_of(kt.assigned_to, request.user))

            if kt.status == 'COMPLETED':
                return Response({'detail': 'A completed KT cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)

            if is_privileged:
                serializer = KTManagerUpdateSerializer(kt, data=request.data, partial=True)
            elif is_owner:
                if kt.status not in ('PENDING', 'IN_PROGRESS', 'REJECTED'):
                    return Response(
                        {'detail': 'You can only edit this KT while it is in progress.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                serializer = KTEmployeeUpdateSerializer(kt, data=request.data, partial=True)
            else:
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            log_action(
                actor=request.user, action='KT_UPDATED', target_obj=kt,
                changes=serializer.validated_data, request=request,
            )

        return _kt_detail_response(kt.pk)


# ─── Employee actions: start / submit ────────────────────────────────────────

class KTStartView(APIView):
    """POST /api/kt/{pk}/start/ — PENDING/REJECTED → IN_PROGRESS (assigned employee)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related('assigned_to').get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not (kt.assigned_to.user_id == request.user.pk or request.user.role == 'ADMIN'):
                return Response({'detail': 'Only the assigned employee can start this KT.'},
                                status=status.HTTP_403_FORBIDDEN)

            if not kt.can_transition_to('IN_PROGRESS'):
                return Response({'detail': f'Cannot start KT from status {kt.status}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            old = kt.status
            kt.status = 'IN_PROGRESS'
            kt.save(update_fields=['status', 'updated_at'])
            log_action(actor=request.user, action='KT_STARTED', target_obj=kt,
                       changes={'status': {'from': old, 'to': 'IN_PROGRESS'}}, request=request)

        return _kt_detail_response(kt.pk)


class KTSubmitView(APIView):
    """POST /api/kt/{pk}/submit/ — IN_PROGRESS → SUBMITTED (assigned employee)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related(
                    'assigned_to', 'receiver',
                ).get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not (kt.assigned_to.user_id == request.user.pk or request.user.role == 'ADMIN'):
                return Response({'detail': 'Only the assigned employee can submit this KT.'},
                                status=status.HTTP_403_FORBIDDEN)

            if not kt.can_transition_to('SUBMITTED'):
                return Response({'detail': f'Cannot submit KT from status {kt.status}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            old = kt.status
            kt.status = 'SUBMITTED'
            kt.submitted_at = timezone.now()
            kt.save(update_fields=['status', 'submitted_at', 'updated_at'])
            log_action(actor=request.user, action='KT_SUBMITTED', target_obj=kt,
                       changes={'status': {'from': old, 'to': 'SUBMITTED'}}, request=request)
            _notify(
                kt.receiver.user, 'ACTION_REQUIRED',
                'Knowledge transfer awaiting your review',
                f'A knowledge transfer "{kt.title}" has been submitted for your review.',
                kt,
            )

        return _kt_detail_response(kt.pk)


# ─── Receiver review ─────────────────────────────────────────────────────────

class KTReceiverActionView(APIView):
    """POST /api/kt/{pk}/receiver-action/ — accept → MANAGER_REVIEW, request_changes → REJECTED."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = KTReceiverActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')

        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related(
                    'assigned_to', 'receiver',
                ).get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not (kt.receiver.user_id == request.user.pk or request.user.role == 'ADMIN'):
                return Response({'detail': 'Only the receiver can review this KT.'},
                                status=status.HTTP_403_FORBIDDEN)

            if kt.status not in ('SUBMITTED', 'RECEIVER_REVIEW'):
                return Response({'detail': f'KT is not awaiting receiver review (status {kt.status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            old = kt.status
            kt.receiver_reviewed_by = request.user
            kt.receiver_reviewed_at = now
            kt.receiver_comments = comments

            if action == 'accept':
                kt.status = 'MANAGER_REVIEW'
                kt.save(update_fields=['status', 'receiver_reviewed_by', 'receiver_reviewed_at',
                                       'receiver_comments', 'updated_at'])
                log_action(actor=request.user, action='KT_ACCEPTED_BY_RECEIVER', target_obj=kt,
                           changes={'status': {'from': old, 'to': 'MANAGER_REVIEW'}}, request=request)
                # Notify the offboarding employee's manager
                mgr = kt.assigned_to.manager
                if mgr and mgr.user:
                    _notify(mgr.user, 'ACTION_REQUIRED', 'Knowledge transfer awaiting manager approval',
                            f'KT "{kt.title}" was accepted by the receiver and needs your approval.', kt)
            else:  # request_changes
                kt.status = 'REJECTED'
                kt.save(update_fields=['status', 'receiver_reviewed_by', 'receiver_reviewed_at',
                                       'receiver_comments', 'updated_at'])
                log_action(actor=request.user, action='KT_CHANGES_REQUESTED', target_obj=kt,
                           changes={'status': {'from': old, 'to': 'REJECTED'}, 'comments': comments},
                           request=request)
                _notify(kt.assigned_to.user, 'ACTION_REQUIRED', 'Changes requested on your knowledge transfer',
                        f'The receiver requested changes on "{kt.title}": {comments}', kt)

        return _kt_detail_response(kt.pk)


# ─── Manager review ──────────────────────────────────────────────────────────

class KTManagerActionView(APIView):
    """POST /api/kt/{pk}/manager-action/ — approve → COMPLETED (manual completed_date), request_changes → REJECTED."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = KTManagerActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')
        completed_date = serializer.validated_data.get('completed_date')

        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related(
                    'assigned_to', 'receiver',
                ).get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Only the offboarding employee's manager or admin may do manager review
            if not (request.user.role == 'ADMIN' or _is_manager_of(kt.assigned_to, request.user)):
                return Response({'detail': 'Only the employee\'s manager can perform manager review.'},
                                status=status.HTTP_403_FORBIDDEN)

            if kt.status != 'MANAGER_REVIEW':
                return Response({'detail': f'KT is not awaiting manager review (status {kt.status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            old = kt.status
            kt.manager_reviewed_by = request.user
            kt.manager_reviewed_at = now
            kt.manager_comments = comments

            if action == 'approve':
                # completed_date is manually supplied; validate against start_date only.
                if kt.start_date and completed_date < kt.start_date:
                    return Response(
                        {'completed_date': 'Completion date cannot be before the start date.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not kt.can_transition_to('COMPLETED'):
                    return Response({'detail': 'Invalid transition.'}, status=status.HTTP_400_BAD_REQUEST)
                kt.status = 'COMPLETED'
                kt.completed_date = completed_date
                kt.save(update_fields=['status', 'completed_date', 'manager_reviewed_by',
                                       'manager_reviewed_at', 'manager_comments', 'updated_at'])
                log_action(actor=request.user, action='KT_APPROVED_BY_MANAGER', target_obj=kt,
                           changes={'status': {'from': old, 'to': 'COMPLETED'},
                                    'completed_date': str(completed_date)}, request=request)
                _notify(kt.assigned_to.user, 'STATUS_UPDATE', 'Knowledge transfer approved',
                        f'Your knowledge transfer "{kt.title}" has been approved and completed.', kt)
                if kt.receiver.user:
                    _notify(kt.receiver.user, 'STATUS_UPDATE', 'Knowledge transfer completed',
                            f'The knowledge transfer "{kt.title}" you received is now complete.', kt)
                _notify_hr('Knowledge transfer completed',
                           f'KT "{kt.title}" for {kt.assigned_to.first_name} {kt.assigned_to.last_name} is complete.', kt)
            else:  # request_changes
                kt.status = 'REJECTED'
                kt.save(update_fields=['status', 'manager_reviewed_by', 'manager_reviewed_at',
                                       'manager_comments', 'updated_at'])
                log_action(actor=request.user, action='KT_REJECTED_BY_MANAGER', target_obj=kt,
                           changes={'status': {'from': old, 'to': 'REJECTED'}, 'comments': comments},
                           request=request)
                _notify(kt.assigned_to.user, 'ACTION_REQUIRED', 'Changes requested on your knowledge transfer',
                        f'Your manager requested changes on "{kt.title}": {comments}', kt)

        return _kt_detail_response(kt.pk)


# ─── Reassign receiver ───────────────────────────────────────────────────────

class KTReassignView(APIView):
    """POST /api/kt/{pk}/reassign/ — change receiver (manager/HR/admin)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = KTReassignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        new_receiver = serializer.validated_data['receiver']
        comments = serializer.validated_data.get('comments', '')

        with transaction.atomic():
            try:
                kt = KnowledgeTransfer.objects.select_for_update().select_related(
                    'assigned_to', 'receiver',
                ).get(pk=pk)
            except KnowledgeTransfer.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            role = request.user.role
            allowed = role in ('HR', 'ADMIN') or (role == 'MANAGER' and _is_manager_of(kt.assigned_to, request.user))
            if not allowed:
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

            if kt.status == 'COMPLETED':
                return Response({'detail': 'Cannot reassign a completed KT.'}, status=status.HTTP_400_BAD_REQUEST)

            if new_receiver.pk == kt.assigned_to_id:
                return Response({'detail': 'The offboarding employee cannot be their own receiver.'},
                                status=status.HTTP_400_BAD_REQUEST)

            old_receiver_id = kt.receiver_id
            kt.receiver = new_receiver
            kt.save(update_fields=['receiver', 'updated_at'])
            log_action(actor=request.user, action='KT_RECEIVER_CHANGED', target_obj=kt,
                       changes={'receiver': {'from': old_receiver_id, 'to': new_receiver.pk},
                                'comments': comments}, request=request)
            if new_receiver.user:
                _notify(new_receiver.user, 'STATUS_UPDATE', 'Knowledge transfer assigned to you',
                        f'You have been assigned as the receiver for KT "{kt.title}".', kt)

        return _kt_detail_response(kt.pk)


# ─── My KT (employee & receiver) ─────────────────────────────────────────────

class KTMineView(APIView):
    """GET /api/kt/mine/ — KT where the user is the assigned employee or the receiver."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        emp = _employee_for(request.user)
        if not emp:
            return Response([])
        role_param = request.query_params.get('role')  # 'assigned' | 'receiver' | None(both)
        qs = KnowledgeTransfer.objects.select_related('project', 'assigned_to', 'receiver')
        if role_param == 'assigned':
            qs = qs.filter(assigned_to=emp)
        elif role_param == 'receiver':
            qs = qs.filter(receiver=emp)
        else:
            qs = qs.filter(Q(assigned_to=emp) | Q(receiver=emp))
        if request.query_params.get('status'):
            qs = qs.filter(status=request.query_params['status'])
        return Response(KnowledgeTransferListSerializer(qs, many=True).data)


# ─── Documents ───────────────────────────────────────────────────────────────

class KTDocumentListCreateView(APIView):
    """GET/POST /api/kt/{pk}/documents/"""
    permission_classes = [IsAuthenticated]

    def _get_kt(self, pk):
        return KnowledgeTransfer.objects.select_related('assigned_to', 'receiver').get(pk=pk)

    def get(self, request, pk):
        try:
            kt = self._get_kt(pk)
        except KnowledgeTransfer.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_kt(kt, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        docs = kt.documents.select_related('added_by').all()
        return Response(KTDocumentSerializer(docs, many=True).data)

    def post(self, request, pk):
        try:
            kt = self._get_kt(pk)
        except KnowledgeTransfer.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        role = request.user.role
        is_owner = kt.assigned_to.user_id == request.user.pk
        is_privileged = role in ('HR', 'ADMIN') or (role == 'MANAGER' and _is_manager_of(kt.assigned_to, request.user))
        if not (is_owner or is_privileged):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if kt.status == 'COMPLETED':
            return Response({'detail': 'Cannot add documents to a completed KT.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = KTDocumentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        doc = serializer.save(knowledge_transfer=kt, added_by=request.user)
        log_action(actor=request.user, action='KT_UPDATED', target_obj=kt,
                   changes={'document_added': doc.url}, request=request)
        return Response(KTDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class KTDocumentDeleteView(APIView):
    """DELETE /api/kt/{pk}/documents/{doc_id}/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, doc_id):
        try:
            kt = KnowledgeTransfer.objects.select_related('assigned_to').get(pk=pk)
        except KnowledgeTransfer.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        role = request.user.role
        is_owner = kt.assigned_to.user_id == request.user.pk
        is_privileged = role in ('HR', 'ADMIN') or (role == 'MANAGER' and _is_manager_of(kt.assigned_to, request.user))
        if not (is_owner or is_privileged):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            doc = KTDocument.objects.get(pk=doc_id, knowledge_transfer=kt)
        except KTDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
        url = doc.url
        doc.delete()
        log_action(actor=request.user, action='KT_UPDATED', target_obj=kt,
                   changes={'document_removed': url}, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
