from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.utils import log_action
from apps.employees.models import Employee

from .models import ResignationRequest
from .views import _notify

User = get_user_model()

# Resignation statuses that mean "HR-approved and in the offboarding execution phase".
_ACTIVE_STATUSES = ['APPROVED', 'NOTICE_PERIOD', 'COMPLETED']


# ─── helpers ─────────────────────────────────────────────────────────────────

def _one2one(obj, attr):
    try:
        return getattr(obj, attr)
    except ObjectDoesNotExist:
        return None


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


def _can_view(resignation, user):
    role = user.role
    if role in ('HR', 'ADMIN', 'FINANCE', 'IT'):
        return True
    if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
        return True
    return resignation.employee.user_id == user.pk


def section_statuses(r):
    """Per-section status for the summary/timeline. Values: COMPLETE / IN_PROGRESS /
    REJECTED / PENDING / NOT_APPLICABLE."""
    s = {}

    # Resignation
    if r.status in _ACTIVE_STATUSES:
        s['resignation'] = 'COMPLETE'
    elif r.status in ('REJECTED', 'CANCELLED'):
        s['resignation'] = 'REJECTED'
    else:
        s['resignation'] = 'IN_PROGRESS'

    # Notice period
    np = _one2one(r, 'notice_period')
    if np and np.status == 'COMPLETED':
        s['notice_period'] = 'COMPLETE'
    elif np:
        s['notice_period'] = 'IN_PROGRESS'
    else:
        s['notice_period'] = 'PENDING'

    # Knowledge transfer
    kt_exists = r.kt_items.exists()
    if r.kt_completed_at is not None:
        s['knowledge_transfer'] = 'COMPLETE'
    elif not kt_exists:
        s['knowledge_transfer'] = 'NOT_APPLICABLE'
    else:
        s['knowledge_transfer'] = 'IN_PROGRESS'

    # Assets (informational; the clearance completion marker covers the gate)
    ac = r.asset_clearances.all()
    if not ac.exists():
        s['assets'] = 'NOT_APPLICABLE'
    elif ac.exclude(status__in=['CLEARED', 'LOST', 'DAMAGED']).exists():
        s['assets'] = 'IN_PROGRESS'
    else:
        s['assets'] = 'COMPLETE'

    # Department clearance
    if r.clearance_completed_at is not None:
        s['department_clearance'] = 'COMPLETE'
    elif r.department_clearances.filter(status='REJECTED').exists():
        s['department_clearance'] = 'REJECTED'
    elif r.department_clearances.exists():
        s['department_clearance'] = 'IN_PROGRESS'
    else:
        s['department_clearance'] = 'PENDING'

    # Final settlement
    fs = _one2one(r, 'final_settlement')
    if fs and fs.settlement_status == 'APPROVED':
        s['settlement'] = 'COMPLETE'
    elif fs and fs.settlement_status == 'REJECTED':
        s['settlement'] = 'REJECTED'
    elif fs:
        s['settlement'] = 'IN_PROGRESS'
    else:
        s['settlement'] = 'PENDING'

    # Exit interview
    ei = _one2one(r, 'exit_interview')
    if ei and ei.status in ('COMPLETED', 'REVIEWED'):
        s['exit_interview'] = 'COMPLETE'
    elif ei:
        s['exit_interview'] = 'IN_PROGRESS'
    else:
        s['exit_interview'] = 'PENDING'

    return s


def pending_items(r):
    """Human-readable list of prerequisites blocking final approval."""
    pending = []
    if r.status not in _ACTIVE_STATUSES:
        pending.append('Resignation approval')
    np = _one2one(r, 'notice_period')
    if not (np and np.status == 'COMPLETED'):
        pending.append('Notice Period')
    if r.kt_completed_at is None and r.kt_items.exists():
        pending.append('Knowledge Transfer')
    if r.clearance_completed_at is None:
        pending.append('Department & Asset Clearance')
    fs = _one2one(r, 'final_settlement')
    if not (fs and fs.settlement_status == 'APPROVED'):
        pending.append('Final Settlement')
    ei = _one2one(r, 'exit_interview')
    if not (ei and ei.status in ('COMPLETED', 'REVIEWED')):
        pending.append('Exit Interview')
    return pending


def current_stage(r):
    if r.final_review_status == 'APPROVED':
        return 'Completed'
    if r.final_review_status == 'UNDER_REVIEW':
        return 'Final Review'
    if r.status == 'DRAFT':
        return 'Draft'
    if r.status == 'SUBMITTED':
        return 'Manager Review'
    if r.status == 'MANAGER_REVIEW':
        return 'HR Review'
    if r.status in ('REJECTED', 'CANCELLED'):
        return r.get_status_display()
    # Active execution phase
    if not pending_items(r):
        return 'Ready for Final Review'
    np = _one2one(r, 'notice_period')
    if not (np and np.status == 'COMPLETED'):
        return 'Notice Period'
    if r.kt_completed_at is None and r.kt_items.exists():
        return 'Knowledge Transfer'
    if r.clearance_completed_at is None:
        return 'Clearance'
    fs = _one2one(r, 'final_settlement')
    if not (fs and fs.settlement_status == 'APPROVED'):
        return 'Settlement'
    return 'Exit Interview'


def _summary_payload(r):
    fs = _one2one(r, 'final_settlement')
    ei = _one2one(r, 'exit_interview')
    np = _one2one(r, 'notice_period')
    return {
        'id': r.id,
        'employee_name': f"{r.employee.first_name} {r.employee.last_name}",
        'employee_id': r.employee.employee_id,
        'department_name': r.employee.department.name if r.employee.department else '',
        'resignation_status': r.status,
        'resignation_status_display': r.get_status_display(),
        'resignation_date': r.resignation_date,
        'expected_last_working_day': np.expected_last_working_day if np else None,
        'sections': section_statuses(r),
        'pending_items': pending_items(r),
        'is_ready': len(pending_items(r)) == 0,
        'final_review_status': r.final_review_status,
        'final_review_status_display': r.get_final_review_status_display(),
        'final_reviewed_by_name': (
            f"{r.final_reviewed_by.first_name} {r.final_reviewed_by.last_name}".strip()
            or r.final_reviewed_by.email) if r.final_reviewed_by else None,
        'final_review_date': r.final_review_date,
        'final_approval_date': r.final_approval_date,
        'final_review_comments': r.final_review_comments,
        'final_rejection_reason': r.final_rejection_reason,
        'settlement_status': fs.settlement_status if fs else None,
        'exit_interview_status': ei.status if ei else None,
    }


# ─── Summary (final review page + HR detail) ─────────────────────────────────

class OffboardingSummaryView(APIView):
    """GET /api/offboarding/{pk}/summary/ — section statuses, readiness, final review."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            r = ResignationRequest.objects.select_related('employee__department').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view(r, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(_summary_payload(r))


# ─── Final review workflow ───────────────────────────────────────────────────

class FinalReviewStartView(APIView):
    """POST /api/offboarding/{pk}/final-review/start/ — verify prerequisites, → UNDER_REVIEW."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can start the final review.'},
                            status=status.HTTP_403_FORBIDDEN)
        review_date = request.data.get('final_review_date')
        with transaction.atomic():
            try:
                r = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if r.final_review_status == 'APPROVED':
                return Response({'detail': 'Final approval is already complete.'},
                                status=status.HTTP_400_BAD_REQUEST)

            pending = pending_items(r)
            if pending:
                log_action(actor=request.user, action='PREREQUISITE_VALIDATION_FAILED', target_obj=r,
                           changes={'pending_items': pending}, request=request)
                return Response(
                    {'detail': 'Final approval cannot be completed.', 'pending_items': pending},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not review_date:
                return Response({'final_review_date': 'Final review date must be entered.'},
                                status=status.HTTP_400_BAD_REQUEST)

            old = r.final_review_status
            r.final_review_status = 'UNDER_REVIEW'
            r.final_reviewed_by = request.user
            r.final_review_date = review_date  # manual
            r.final_review_comments = request.data.get('comments', '') or r.final_review_comments
            r.save(update_fields=['final_review_status', 'final_reviewed_by', 'final_review_date',
                                  'final_review_comments', 'updated_at'])
            log_action(actor=request.user, action='FINAL_REVIEW_STARTED', target_obj=r,
                       changes={'status': {'from': old, 'to': 'UNDER_REVIEW'},
                                'final_review_date': str(review_date)}, request=request)
            for u in User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True):
                _notify(u, 'STATUS_UPDATE', 'Final review started',
                        f'Final review has started for {r.employee.first_name} {r.employee.last_name}.', r)
        return Response(_summary_payload(
            ResignationRequest.objects.select_related('employee__department', 'final_reviewed_by').get(pk=pk)))


class FinalReviewApproveView(APIView):
    """POST /api/offboarding/{pk}/final-review/approve/ — UNDER_REVIEW → APPROVED (manual date)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can approve the final offboarding.'},
                            status=status.HTTP_403_FORBIDDEN)
        approval_date = request.data.get('final_approval_date')
        with transaction.atomic():
            try:
                r = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if r.final_review_status != 'UNDER_REVIEW':
                return Response({'detail': f'Final review must be UNDER_REVIEW to approve (currently {r.final_review_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Re-verify prerequisites independently (never trust the frontend).
            pending = pending_items(r)
            if pending:
                log_action(actor=request.user, action='PREREQUISITE_VALIDATION_FAILED', target_obj=r,
                           changes={'pending_items': pending}, request=request)
                return Response({'detail': 'Final approval cannot be completed.', 'pending_items': pending},
                                status=status.HTTP_400_BAD_REQUEST)

            if not approval_date:
                return Response({'final_approval_date': 'Final approval date must be entered.'},
                                status=status.HTTP_400_BAD_REQUEST)

            r.final_review_status = 'APPROVED'
            r.final_reviewed_by = request.user
            r.final_approval_date = approval_date  # manual
            r.final_review_comments = request.data.get('comments', '') or r.final_review_comments
            r.save(update_fields=['final_review_status', 'final_reviewed_by', 'final_approval_date',
                                  'final_review_comments', 'updated_at'])
            # NOTE: employee intentionally stays OFFBOARDING; EXITED/deactivation is a later phase.
            log_action(actor=request.user, action='FINAL_APPROVAL', target_obj=r,
                       changes={'status': {'from': 'UNDER_REVIEW', 'to': 'APPROVED'},
                                'final_approval_date': str(approval_date)}, request=request)
            _notify(r.employee.user, 'STATUS_UPDATE', 'Offboarding finally approved',
                    'Your offboarding has received final HR approval.', r)
            mgr = r.employee.manager
            if mgr and mgr.user:
                _notify(mgr.user, 'STATUS_UPDATE', 'Offboarding finally approved',
                        f'{r.employee.first_name} {r.employee.last_name}\'s offboarding has been finally approved.', r)
        return Response(_summary_payload(
            ResignationRequest.objects.select_related('employee__department', 'final_reviewed_by').get(pk=pk)))


class FinalReviewRejectView(APIView):
    """POST /api/offboarding/{pk}/final-review/reject/ — UNDER_REVIEW → REJECTED (reason required)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can reject the final offboarding.'},
                            status=status.HTTP_403_FORBIDDEN)
        reason = (request.data.get('rejection_reason') or '').strip()
        if not reason:
            return Response({'rejection_reason': 'A rejection reason is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            try:
                r = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if r.final_review_status != 'UNDER_REVIEW':
                return Response({'detail': f'Final review must be UNDER_REVIEW to reject (currently {r.final_review_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            r.final_review_status = 'REJECTED'
            r.final_reviewed_by = request.user
            r.final_rejection_reason = reason
            # Existing workflow data is left intact; employee stays OFFBOARDING.
            r.save(update_fields=['final_review_status', 'final_reviewed_by',
                                  'final_rejection_reason', 'updated_at'])
            log_action(actor=request.user, action='FINAL_APPROVAL_REJECTED', target_obj=r,
                       changes={'status': {'from': 'UNDER_REVIEW', 'to': 'REJECTED'},
                                'reason': reason}, request=request)
            _notify(r.employee.user, 'STATUS_UPDATE', 'Final offboarding review returned',
                    f'Your final offboarding review was returned: {reason}', r)
        return Response(_summary_payload(
            ResignationRequest.objects.select_related('employee__department', 'final_reviewed_by').get(pk=pk)))


# ─── HR dashboard (aggregates) ───────────────────────────────────────────────

class HRDashboardView(APIView):
    """GET /api/offboarding/dashboard/ — aggregate counts + pipeline (fixed # of queries)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        RR = ResignationRequest.objects
        base = RR.exclude(status__in=['DRAFT', 'REJECTED', 'CANCELLED'])
        active = base.filter(status__in=_ACTIVE_STATUSES)

        ready = active.filter(
            notice_period__status='COMPLETED',
            clearance_completed_at__isnull=False,
            final_settlement__settlement_status='APPROVED',
            exit_interview__status__in=['COMPLETED', 'REVIEWED'],
        ).filter(
            Q(kt_completed_at__isnull=False) | ~Q(kt_items__isnull=False)
        ).exclude(final_review_status='APPROVED').distinct()

        summary = {
            'total_offboarding': base.count(),
            'pending_manager_review': RR.filter(status='SUBMITTED').count(),
            'pending_hr_review': RR.filter(status='MANAGER_REVIEW').count(),
            'notice_period': base.filter(status='NOTICE_PERIOD').count(),
            'kt_in_progress': active.filter(kt_items__isnull=False, kt_completed_at__isnull=True).distinct().count(),
            'clearance_pending': active.filter(clearance_completed_at__isnull=True).count(),
            'settlement_pending': active.exclude(final_settlement__settlement_status='APPROVED').count(),
            'exit_interview_pending': active.exclude(exit_interview__status__in=['COMPLETED', 'REVIEWED']).count(),
            'ready_for_final_review': ready.count(),
            'under_final_review': base.filter(final_review_status='UNDER_REVIEW').count(),
            'completed': base.filter(final_review_status='APPROVED').count(),
        }

        pipeline = {
            'resignation': RR.filter(status__in=['SUBMITTED', 'MANAGER_REVIEW', 'HR_REVIEW']).count(),
            'notice': base.filter(status='NOTICE_PERIOD').count(),
            'kt': active.filter(kt_items__isnull=False, kt_completed_at__isnull=True).distinct().count(),
            'clearance': active.filter(kt_completed_at__isnull=False, clearance_completed_at__isnull=True).count(),
            'settlement': active.filter(clearance_completed_at__isnull=False).exclude(
                final_settlement__settlement_status='APPROVED').count(),
            'exit_interview': active.filter(
                clearance_completed_at__isnull=False,
                final_settlement__settlement_status='APPROVED',
            ).exclude(exit_interview__status__in=['COMPLETED', 'REVIEWED']).count(),
            'final_review': summary['ready_for_final_review'] + summary['under_final_review'],
            'completed': summary['completed'],
        }
        return Response({'summary': summary, 'pipeline': pipeline})


class _DashboardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class HROffboardingListView(APIView):
    """GET /api/offboarding/dashboard/list/ — comprehensive, filterable, paginated table."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role
        RR = ResignationRequest.objects.select_related(
            'employee__department', 'employee__manager', 'notice_period',
            'final_settlement', 'exit_interview',
        ).prefetch_related('kt_items', 'asset_clearances', 'department_clearances')

        if role in ('HR', 'ADMIN'):
            qs = RR.all()
        elif role == 'MANAGER':
            mgr = _employee_for(user)
            qs = RR.filter(Q(employee__manager=mgr) | Q(employee__user=user)) if mgr else RR.none()
        else:
            qs = RR.filter(employee__user=user)

        qs = qs.exclude(status='DRAFT')

        p = request.query_params
        search = p.get('search')
        if search:
            qs = qs.filter(
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search) |
                Q(employee__employee_id__icontains=search) |
                Q(employee__email__icontains=search)
            )
        if p.get('department'):
            qs = qs.filter(employee__department_id=p['department'])
        if p.get('manager'):
            qs = qs.filter(employee__manager_id=p['manager'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('final_review_status'):
            qs = qs.filter(final_review_status=p['final_review_status'])
        if p.get('settlement_status'):
            qs = qs.filter(final_settlement__settlement_status=p['settlement_status'])
        if p.get('exit_interview_status'):
            qs = qs.filter(exit_interview__status=p['exit_interview_status'])
        # Date filter only against stored values
        if p.get('resignation_date_from'):
            qs = qs.filter(resignation_date__gte=p['resignation_date_from'])
        if p.get('resignation_date_to'):
            qs = qs.filter(resignation_date__lte=p['resignation_date_to'])

        qs = qs.distinct().order_by('-created_at')

        paginator = _DashboardPagination()
        page = paginator.paginate_queryset(qs, request)
        rows = [self._row(r) for r in page]

        # optional stage filter applied post-derivation
        stage = p.get('stage')
        if stage:
            rows = [row for row in rows if row['current_stage'] == stage]
        return paginator.get_paginated_response(rows)

    def _row(self, r):
        fs = _one2one(r, 'final_settlement')
        ei = _one2one(r, 'exit_interview')
        np = _one2one(r, 'notice_period')
        secs = section_statuses(r)
        mgr = r.employee.manager
        return {
            'id': r.id,
            'employee_name': f"{r.employee.first_name} {r.employee.last_name}",
            'employee_id': r.employee.employee_id,
            'department_name': r.employee.department.name if r.employee.department else '',
            'manager_name': f"{mgr.first_name} {mgr.last_name}" if mgr else None,
            'current_stage': current_stage(r),
            'resignation_date': r.resignation_date,
            'expected_last_working_day': np.expected_last_working_day if np else None,
            'kt_status': secs['knowledge_transfer'],
            'clearance_status': secs['department_clearance'],
            'settlement_status': fs.settlement_status if fs else 'PENDING',
            'exit_interview_status': ei.status if ei else 'NOT_STARTED',
            'final_review_status': r.final_review_status,
            'is_ready': len(pending_items(r)) == 0,
        }
