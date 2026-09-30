from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHR, IsAdmin
from apps.audit.utils import log_action
from apps.employees.models import Employee
from apps.notifications.models import Notification

from .models import ResignationRequest, NoticePeriod, add_months, notice_months
from .serializers import (
    ResignationRequestCreateSerializer,
    ResignationRequestDetailSerializer,
    ResignationRequestListSerializer,
    ManagerActionSerializer,
    HRActionSerializer,
    CancelSerializer,
    NoticePeriodCreateSerializer,
    NoticePeriodUpdateSerializer,
    NoticePeriodDetailSerializer,
    EarlyReleaseRequestSerializer,
    EarlyReleaseReviewSerializer,
    NoticeExtensionSerializer,
    CompleteNoticePeriodSerializer,
)


def _notify(recipient_user, notification_type, title, message, obj):
    if recipient_user:
        Notification.objects.create(
            recipient=recipient_user,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type='ResignationRequest',
            related_object_id=obj.pk,
        )


_UNSET = object()


def _apply_early_relief(np, early_relief, actor):
    """Apply the HR-entered early relieving date on a notice period.

    A date records an approved early release (resolving any pending request);
    an explicit null clears a recorded early release. Returns True when a date
    was newly set/changed.
    """
    if early_relief:
        newly_set = np.early_release_date != early_relief or not np.early_release_approved
        np.early_release_date = early_relief
        np.early_release_approved = True
        if newly_set:
            np.early_release_reviewed_by = actor
            np.early_release_reviewed_at = timezone.now()
        if np.status == 'EARLY_RELEASE_REQUESTED':
            np.status = 'ACTIVE'
    elif np.early_release_date or np.early_release_approved:
        # Explicit null — remove the recorded early release (a rejection record is kept).
        newly_set = False
        np.early_release_date = None
        np.early_release_approved = None
        np.early_release_reviewed_by = None
        np.early_release_reviewed_at = None
        np.early_release_review_notes = ''
    else:
        return False
    np.save(update_fields=[
        'early_release_date', 'early_release_approved', 'early_release_reviewed_by',
        'early_release_reviewed_at', 'early_release_review_notes', 'status', 'updated_at',
    ])
    return newly_set


class ResignationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role

        if role in ('HR', 'ADMIN'):
            qs = ResignationRequest.objects.select_related(
                'employee__department', 'employee__designation', 'employee__manager'
            ).all()
        elif role == 'MANAGER':
            # Show own resignations + direct reports' resignations
            try:
                from django.db.models import Q
                manager_employee = Employee.objects.get(user=user)
                qs = ResignationRequest.objects.select_related(
                    'employee__department', 'employee__designation', 'employee__manager'
                ).filter(
                    Q(employee=manager_employee) | Q(employee__manager=manager_employee)
                )
            except Employee.DoesNotExist:
                qs = ResignationRequest.objects.none()
        elif role == 'EMPLOYEE':
            try:
                employee = Employee.objects.get(user=user)
                qs = ResignationRequest.objects.filter(employee=employee)
            except Employee.DoesNotExist:
                qs = ResignationRequest.objects.none()
        else:
            qs = ResignationRequest.objects.none()

        # Optional status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = ResignationRequestListSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Only employees can create resignation requests
        if request.user.role not in ('EMPLOYEE', 'MANAGER', 'HR', 'ADMIN'):
            return Response(
                {'detail': 'Only employees can submit resignations.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'No employee profile found for this user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if employee.employment_status not in ('ACTIVE',):
            return Response(
                {'detail': 'Only active employees can submit a resignation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing active resignation
        active = ResignationRequest.objects.filter(
            employee=employee,
            status__in=['DRAFT', 'SUBMITTED', 'MANAGER_REVIEW', 'HR_REVIEW'],
        ).exists()
        if active:
            return Response(
                {'detail': 'An active resignation request already exists for this employee.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ResignationRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Dates are set by the server: resignation date = today; last working day =
        # resignation date + notice period (1 month if tenure < 6 months, else 2).
        resignation_date = timezone.localdate()
        notice = notice_months(employee.joining_date, resignation_date)
        last_working_date = add_months(resignation_date, notice)

        with transaction.atomic():
            resignation = serializer.save(
                employee=employee,
                submitted_by=request.user,
                status='DRAFT',
                resignation_date=resignation_date,
                last_working_date=last_working_date,
            )
            log_action(
                actor=request.user,
                action='RESIGNATION_DRAFT_CREATED',
                target_obj=resignation,
                changes={'status': 'DRAFT'},
                request=request,
            )

        return Response(
            ResignationRequestDetailSerializer(resignation).data,
            status=status.HTTP_201_CREATED,
        )


class ResignationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_resignation(self, pk, user):
        try:
            return ResignationRequest.objects.select_related(
                'employee__user',
                'employee__department',
                'employee__designation',
                'employee__manager__user',
                'submitted_by',
                'manager_reviewed_by',
                'hr_reviewed_by',
            ).get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return None

    def _has_read_access(self, resignation, user):
        role = user.role
        # HR/Admin see all; IT and Finance need read access to action clearances.
        if role in ('HR', 'ADMIN', 'IT', 'FINANCE'):
            return True
        if role == 'MANAGER':
            try:
                mgr_emp = Employee.objects.get(user=user)
                return resignation.employee.manager_id == mgr_emp.pk
            except Employee.DoesNotExist:
                return False
        # Employee can only see own
        return resignation.employee.user_id == user.pk

    def get(self, request, pk):
        resignation = self._get_resignation(pk, request.user)
        if not resignation:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not self._has_read_access(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(ResignationRequestDetailSerializer(resignation).data)


class SubmitResignationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Only the employee who owns this request can submit it
            if resignation.employee.user_id != request.user.pk:
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

            if not resignation.can_transition_to('SUBMITTED'):
                return Response(
                    {'detail': f'Cannot submit from status {resignation.status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            old_status = resignation.status
            resignation.status = 'SUBMITTED'
            resignation.save(update_fields=['status', 'updated_at'])

            # Update employee status to OFFBOARDING
            Employee.objects.filter(pk=resignation.employee_id).update(
                employment_status='OFFBOARDING'
            )

            log_action(
                actor=request.user,
                action='RESIGNATION_SUBMITTED',
                target_obj=resignation,
                changes={'status': {'from': old_status, 'to': 'SUBMITTED'}},
                request=request,
            )

            # Notify manager — fetch separately to avoid N+1 through nullable FK chain
            manager_id = resignation.employee.manager_id
            if manager_id:
                manager = Employee.objects.select_related('user').filter(pk=manager_id).first()
            else:
                manager = None
            if manager and manager.user:
                _notify(
                    manager.user,
                    'ACTION_REQUIRED',
                    'Resignation submitted for your review',
                    f"{resignation.employee.first_name} {resignation.employee.last_name} has submitted a resignation request.",
                    resignation,
                )

        return Response(ResignationRequestDetailSerializer(resignation).data)


class ManagerActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = ManagerActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Only the direct manager or ADMIN can act
            user = request.user
            if user.role not in ('ADMIN',):
                try:
                    manager_emp = Employee.objects.get(user=user)
                    if resignation.employee.manager_id != manager_emp.pk:
                        return Response(
                            {'detail': 'You are not the direct manager of this employee.'},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except Employee.DoesNotExist:
                    return Response(
                        {'detail': 'No employee profile found for your account.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            if resignation.status != 'SUBMITTED':
                return Response(
                    {'detail': f'Manager action requires SUBMITTED status, got {resignation.status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            old_status = resignation.status
            now = timezone.now()

            if action == 'approve':
                resignation.status = 'MANAGER_REVIEW'
                resignation.manager_reviewed_by = user
                resignation.manager_reviewed_at = now
                resignation.manager_notes = notes
                resignation.save(update_fields=[
                    'status', 'manager_reviewed_by', 'manager_reviewed_at',
                    'manager_notes', 'updated_at',
                ])
                log_action(
                    actor=user,
                    action='RESIGNATION_MANAGER_APPROVED',
                    target_obj=resignation,
                    changes={'status': {'from': old_status, 'to': 'MANAGER_REVIEW'}, 'notes': notes},
                    request=request,
                )
                # Notify HR users
                from django.contrib.auth import get_user_model
                User = get_user_model()
                hr_users = User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True)
                for hr_user in hr_users:
                    _notify(
                        hr_user,
                        'ACTION_REQUIRED',
                        'Resignation pending HR review',
                        f"Resignation from {resignation.employee.first_name} {resignation.employee.last_name} has been approved by manager and requires HR review.",
                        resignation,
                    )
                # Notify employee
                _notify(
                    resignation.employee.user,
                    'STATUS_UPDATE',
                    'Your resignation is under HR review',
                    'Your manager has approved your resignation request. It is now with HR for final review.',
                    resignation,
                )

            else:  # reject
                resignation.status = 'REJECTED'
                resignation.manager_reviewed_by = user
                resignation.manager_reviewed_at = now
                resignation.manager_notes = notes
                resignation.rejection_reason = notes
                resignation.save(update_fields=[
                    'status', 'manager_reviewed_by', 'manager_reviewed_at',
                    'manager_notes', 'rejection_reason', 'updated_at',
                ])
                # Revert employee to ACTIVE if no other active offboarding
                _revert_employee_status(resignation.employee)
                log_action(
                    actor=user,
                    action='RESIGNATION_MANAGER_REJECTED',
                    target_obj=resignation,
                    changes={'status': {'from': old_status, 'to': 'REJECTED'}, 'notes': notes},
                    request=request,
                )
                _notify(
                    resignation.employee.user,
                    'RESIGNATION_REJECTED',
                    'Your resignation has been rejected',
                    f'Your resignation request has been rejected by your manager. Reason: {notes or "No reason provided."}',
                    resignation,
                )

        return Response(ResignationRequestDetailSerializer(resignation).data)


class HRActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = HRActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if resignation.status != 'MANAGER_REVIEW':
                return Response(
                    {'detail': f'HR action requires MANAGER_REVIEW status, got {resignation.status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            old_status = resignation.status
            now = timezone.now()
            user = request.user

            if action == 'approve':
                resignation.status = 'APPROVED'
                resignation.hr_reviewed_by = user
                resignation.hr_reviewed_at = now
                resignation.hr_notes = notes
                resignation.save(update_fields=[
                    'status', 'hr_reviewed_by', 'hr_reviewed_at', 'hr_notes', 'updated_at',
                ])
                log_action(
                    actor=user,
                    action='RESIGNATION_HR_APPROVED',
                    target_obj=resignation,
                    changes={'status': {'from': old_status, 'to': 'APPROVED'}, 'notes': notes},
                    request=request,
                )
                _notify(
                    resignation.employee.user,
                    'RESIGNATION_APPROVED',
                    'Your resignation has been approved',
                    'Your resignation request has been fully approved by HR.',
                    resignation,
                )

            else:  # reject
                resignation.status = 'REJECTED'
                resignation.hr_reviewed_by = user
                resignation.hr_reviewed_at = now
                resignation.hr_notes = notes
                resignation.rejection_reason = notes
                resignation.save(update_fields=[
                    'status', 'hr_reviewed_by', 'hr_reviewed_at',
                    'hr_notes', 'rejection_reason', 'updated_at',
                ])
                _revert_employee_status(resignation.employee)
                log_action(
                    actor=user,
                    action='RESIGNATION_HR_REJECTED',
                    target_obj=resignation,
                    changes={'status': {'from': old_status, 'to': 'REJECTED'}, 'notes': notes},
                    request=request,
                )
                _notify(
                    resignation.employee.user,
                    'RESIGNATION_REJECTED',
                    'Your resignation has been rejected',
                    f'Your resignation request has been rejected by HR. Reason: {notes or "No reason provided."}',
                    resignation,
                )

        return Response(ResignationRequestDetailSerializer(resignation).data)


class CancelResignationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = CancelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reason = serializer.validated_data.get('reason', '')

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            user = request.user
            is_owner = resignation.employee.user_id == user.pk
            is_privileged = user.role in ('HR', 'ADMIN')

            if not (is_owner or is_privileged):
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

            if not resignation.can_transition_to('CANCELLED'):
                return Response(
                    {'detail': f'Cannot cancel from status {resignation.status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            old_status = resignation.status
            resignation.status = 'CANCELLED'
            resignation.rejection_reason = reason
            resignation.save(update_fields=['status', 'rejection_reason', 'updated_at'])

            _revert_employee_status(resignation.employee)

            log_action(
                actor=user,
                action='RESIGNATION_CANCELLED',
                target_obj=resignation,
                changes={'status': {'from': old_status, 'to': 'CANCELLED'}, 'reason': reason},
                request=request,
            )
            _notify(
                resignation.employee.user,
                'RESIGNATION_CANCELLED',
                'Your resignation has been cancelled',
                f'Your resignation request has been cancelled. {reason}',
                resignation,
            )

        return Response(ResignationRequestDetailSerializer(resignation).data)


def _revert_employee_status(employee):
    """Revert employee to ACTIVE only if they have no other active offboarding requests."""
    other_active = ResignationRequest.objects.filter(
        employee=employee,
        status__in=['SUBMITTED', 'MANAGER_REVIEW', 'HR_REVIEW'],
    ).exists()
    if not other_active:
        Employee.objects.filter(pk=employee.pk).update(employment_status='ACTIVE')


def _get_resignation_with_access(pk, user, require_notice_period=False):
    """Return (resignation, error_response) tuple. error_response is None on success."""
    try:
        resignation = ResignationRequest.objects.select_related(
            'employee__user', 'employee__manager',
        ).get(pk=pk)
    except ResignationRequest.DoesNotExist:
        return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    role = user.role
    if role in ('HR', 'ADMIN'):
        return resignation, None
    if role == 'MANAGER':
        try:
            mgr_emp = Employee.objects.get(user=user)
            if resignation.employee.manager_id == mgr_emp.pk or resignation.employee.user_id == user.pk:
                return resignation, None
        except Employee.DoesNotExist:
            pass
        return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    # EMPLOYEE — only own
    if resignation.employee.user_id == user.pk:
        return resignation, None
    return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)


class NoticePeriodView(APIView):
    """GET/POST/PATCH /api/offboarding/{pk}/notice-period/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        resignation, err = _get_resignation_with_access(pk, request.user)
        if err:
            return err
        try:
            np = NoticePeriod.objects.select_related(
                'early_release_requested_by',
                'early_release_reviewed_by',
                'extension_recorded_by',
                'completed_by',
                'created_by',
            ).get(resignation=resignation)
        except NoticePeriod.DoesNotExist:
            return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(NoticePeriodDetailSerializer(np).data)

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR can create a notice period.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = NoticePeriodCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        early_relief = serializer.validated_data.pop('early_relief_date', _UNSET)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not resignation.can_transition_to('NOTICE_PERIOD'):
                return Response(
                    {'detail': f'Cannot create notice period for resignation with status {resignation.status}. Must be APPROVED.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if NoticePeriod.objects.filter(resignation=resignation).exists():
                return Response(
                    {'detail': 'A notice period already exists for this resignation.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            np = serializer.save(resignation=resignation, created_by=request.user)

            if early_relief is not _UNSET and early_relief:
                _apply_early_relief(np, early_relief, request.user)
                _notify(
                    resignation.employee.user,
                    'STATUS_UPDATE',
                    'Early relieving date recorded',
                    f'HR has recorded an early relieving date for you: {early_relief}.',
                    resignation,
                )

            # Transition resignation APPROVED → NOTICE_PERIOD
            resignation.status = 'NOTICE_PERIOD'
            resignation.save(update_fields=['status', 'updated_at'])

            audit_changes = {
                'status': {'from': 'APPROVED', 'to': 'NOTICE_PERIOD'},
                'notice_period_id': np.pk,
            }
            if early_relief is not _UNSET and early_relief:
                audit_changes['early_relief_date'] = early_relief
            log_action(
                actor=request.user,
                action='NOTICE_PERIOD_CREATED',
                target_obj=resignation,
                changes=audit_changes,
                request=request,
            )
            _notify(
                resignation.employee.user,
                'STATUS_UPDATE',
                'Notice period started',
                'HR has started your notice period. Please log in to view the details.',
                resignation,
            )

        return Response(
            NoticePeriodDetailSerializer(
                NoticePeriod.objects.select_related(
                    'early_release_requested_by', 'early_release_reviewed_by',
                    'extension_recorded_by', 'completed_by', 'created_by',
                ).get(pk=np.pk)
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR can update a notice period.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            try:
                np = NoticePeriod.objects.select_for_update().get(resignation=resignation)
            except NoticePeriod.DoesNotExist:
                return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)

            if np.status == 'COMPLETED':
                return Response({'detail': 'Cannot update a completed notice period.'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = NoticePeriodUpdateSerializer(np, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            early_relief = serializer.validated_data.pop('early_relief_date', _UNSET)

            serializer.save()
            if early_relief is not _UNSET:
                if _apply_early_relief(np, early_relief, request.user):
                    _notify(
                        resignation.employee.user,
                        'STATUS_UPDATE',
                        'Early relieving date recorded',
                        f'HR has recorded an early relieving date for you: {early_relief}.',
                        resignation,
                    )
            changes = dict(serializer.validated_data)
            if early_relief is not _UNSET:
                changes['early_relief_date'] = early_relief
            log_action(
                actor=request.user,
                action='NOTICE_PERIOD_UPDATED',
                target_obj=resignation,
                changes=changes,
                request=request,
            )

        return Response(
            NoticePeriodDetailSerializer(
                NoticePeriod.objects.select_related(
                    'early_release_requested_by', 'early_release_reviewed_by',
                    'extension_recorded_by', 'completed_by', 'created_by',
                ).get(pk=np.pk)
            ).data
        )


class EarlyReleaseView(APIView):
    """POST /api/offboarding/{pk}/early-release/
    action: 'request' (employee — own resignation only) or 'approve'/'reject' (HR)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        action = request.data.get('action')
        if action == 'request':
            return self._handle_request(request, pk)
        elif action in ('approve', 'reject'):
            return self._handle_review(request, pk, action)
        return Response({'detail': 'action must be request, approve, or reject.'}, status=status.HTTP_400_BAD_REQUEST)

    def _handle_request(self, request, pk):
        serializer = EarlyReleaseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Early release is initiated by the employee whose resignation it is.
            if resignation.employee.user_id != request.user.pk:
                return Response(
                    {'detail': 'Only the employee can request their own early release.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            try:
                np = NoticePeriod.objects.select_for_update().get(resignation=resignation)
            except NoticePeriod.DoesNotExist:
                return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)

            if resignation.status != 'NOTICE_PERIOD':
                return Response({'detail': 'Early release can only be requested during notice period.'}, status=status.HTTP_400_BAD_REQUEST)
            if np.early_release_approved:
                return Response({'detail': 'An early release has already been approved.'}, status=status.HTTP_400_BAD_REQUEST)
            if np.status != 'ACTIVE':
                return Response({'detail': f'Cannot request early release when notice period status is {np.status}.'}, status=status.HTTP_400_BAD_REQUEST)

            np.status = 'EARLY_RELEASE_REQUESTED'
            np.early_release_requested_by = request.user
            np.early_release_requested_at = timezone.now()
            np.early_release_request_reason = serializer.validated_data['reason']
            np.save(update_fields=[
                'status', 'early_release_requested_by', 'early_release_requested_at',
                'early_release_request_reason', 'updated_at',
            ])

            log_action(
                actor=request.user,
                action='EARLY_RELEASE_REQUESTED',
                target_obj=resignation,
                changes={'reason': serializer.validated_data['reason']},
                request=request,
            )
            from django.contrib.auth import get_user_model
            User = get_user_model()
            for hr_user in User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True):
                _notify(
                    hr_user,
                    'ACTION_REQUIRED',
                    'Early release requested',
                    f"{resignation.employee.first_name} {resignation.employee.last_name} has requested early release.",
                    resignation,
                )

        return Response(NoticePeriodDetailSerializer(
            NoticePeriod.objects.select_related(
                'early_release_requested_by', 'early_release_reviewed_by',
                'extension_recorded_by', 'completed_by', 'created_by',
            ).get(pk=np.pk)
        ).data)

    def _handle_review(self, request, pk, action):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR can approve or reject early release.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = EarlyReleaseReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            try:
                np = NoticePeriod.objects.select_for_update().get(resignation=resignation)
            except NoticePeriod.DoesNotExist:
                return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)

            if np.status != 'EARLY_RELEASE_REQUESTED':
                return Response({'detail': 'No pending early release request.'}, status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            np.early_release_reviewed_by = request.user
            np.early_release_reviewed_at = now
            np.early_release_review_notes = serializer.validated_data.get('notes', '')

            if action == 'approve':
                np.early_release_approved = True
                np.early_release_date = serializer.validated_data['early_release_date']
                np.status = 'ACTIVE'
                audit_action = 'EARLY_RELEASE_APPROVED'
                notify_title = 'Early release approved'
                notify_msg = f'Your early release request has been approved. Your release date is {np.early_release_date}.'
            else:
                np.early_release_approved = False
                np.status = 'ACTIVE'
                audit_action = 'EARLY_RELEASE_REJECTED'
                notify_title = 'Early release request rejected'
                notify_msg = f'Your early release request has been rejected. {serializer.validated_data.get("notes", "")}'

            np.save(update_fields=[
                'status', 'early_release_approved', 'early_release_date',
                'early_release_reviewed_by', 'early_release_reviewed_at',
                'early_release_review_notes', 'updated_at',
            ])

            log_action(
                actor=request.user,
                action=audit_action,
                target_obj=resignation,
                changes={
                    'approved': np.early_release_approved,
                    'early_release_date': str(np.early_release_date) if np.early_release_date else None,
                },
                request=request,
            )
            _notify(resignation.employee.user, 'STATUS_UPDATE', notify_title, notify_msg, resignation)

        return Response(NoticePeriodDetailSerializer(
            NoticePeriod.objects.select_related(
                'early_release_requested_by', 'early_release_reviewed_by',
                'extension_recorded_by', 'completed_by', 'created_by',
            ).get(pk=np.pk)
        ).data)


class NoticeExtensionView(APIView):
    """POST /api/offboarding/{pk}/notice-extension/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR can record a notice extension.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = NoticeExtensionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if resignation.status != 'NOTICE_PERIOD':
                return Response({'detail': 'Extension can only be recorded during active notice period.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                np = NoticePeriod.objects.select_for_update().get(resignation=resignation)
            except NoticePeriod.DoesNotExist:
                return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)

            if np.status == 'COMPLETED':
                return Response({'detail': 'Cannot extend a completed notice period.'}, status=status.HTTP_400_BAD_REQUEST)

            if np.status == 'EARLY_RELEASE_REQUESTED':
                return Response(
                    {'detail': 'Resolve the pending early release request before recording an extension.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            now = timezone.now()
            np.notice_extension_date = serializer.validated_data['notice_extension_date']
            np.extension_reason = serializer.validated_data['extension_reason']
            np.extension_recorded_by = request.user
            np.extension_recorded_at = now
            np.save(update_fields=[
                'notice_extension_date', 'extension_reason',
                'extension_recorded_by', 'extension_recorded_at', 'updated_at',
            ])

            log_action(
                actor=request.user,
                action='NOTICE_PERIOD_EXTENDED',
                target_obj=resignation,
                changes={
                    'notice_extension_date': str(np.notice_extension_date),
                    'reason': np.extension_reason,
                },
                request=request,
            )
            _notify(
                resignation.employee.user,
                'STATUS_UPDATE',
                'Notice period extended',
                f'Your notice period has been extended. New extended date: {np.notice_extension_date}.',
                resignation,
            )

        return Response(NoticePeriodDetailSerializer(
            NoticePeriod.objects.select_related(
                'early_release_requested_by', 'early_release_reviewed_by',
                'extension_recorded_by', 'completed_by', 'created_by',
            ).get(pk=np.pk)
        ).data)


class CompleteNoticePeriodView(APIView):
    """POST /api/offboarding/{pk}/notice-period/complete/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR can complete a notice period.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CompleteNoticePeriodSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related(
                    'employee'
                ).get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not resignation.can_transition_to('COMPLETED'):
                return Response(
                    {'detail': f'Cannot complete notice period for resignation with status {resignation.status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                np = NoticePeriod.objects.select_for_update().get(resignation=resignation)
            except NoticePeriod.DoesNotExist:
                return Response({'detail': 'No notice period found.'}, status=status.HTTP_404_NOT_FOUND)

            if np.status == 'COMPLETED':
                return Response({'detail': 'Notice period is already completed.'}, status=status.HTTP_400_BAD_REQUEST)

            if np.status == 'EARLY_RELEASE_REQUESTED':
                return Response(
                    {'detail': 'Resolve the pending early release request before completing the notice period.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            now = timezone.now()
            np.actual_last_working_day = serializer.validated_data['actual_last_working_day']
            np.status = 'COMPLETED'
            np.completed_by = request.user
            np.completed_at = now
            np.save(update_fields=[
                'actual_last_working_day', 'status', 'completed_by', 'completed_at', 'updated_at',
            ])

            # Transition resignation NOTICE_PERIOD → COMPLETED
            resignation.status = 'COMPLETED'
            resignation.save(update_fields=['status', 'updated_at'])

            # Employee becomes EXITED
            Employee.objects.filter(pk=resignation.employee_id).update(employment_status='EXITED')

            log_action(
                actor=request.user,
                action='NOTICE_PERIOD_COMPLETED',
                target_obj=resignation,
                changes={
                    'status': {'from': 'NOTICE_PERIOD', 'to': 'COMPLETED'},
                    'actual_last_working_day': str(np.actual_last_working_day),
                },
                request=request,
            )
            _notify(
                resignation.employee.user,
                'STATUS_UPDATE',
                'Offboarding complete',
                f'Your notice period has been completed. Your last working day was {np.actual_last_working_day}. Thank you for your service.',
                resignation,
            )

        return Response(
            ResignationRequestDetailSerializer(
                ResignationRequest.objects.select_related(
                    'employee__user', 'employee__department', 'employee__designation',
                    'employee__manager__user', 'submitted_by',
                    'manager_reviewed_by', 'hr_reviewed_by',
                ).get(pk=pk)
            ).data
        )
