from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.utils import log_action
from apps.employees.models import Employee

from .models import (
    ResignationRequest, FinalSettlement, ExitInterview,
    SETTLEMENT_ADDITION_FIELDS, SETTLEMENT_DEDUCTION_FIELDS,
)
from .views import _notify
from .settlement_serializers import (
    FinalSettlementSerializer, FinalSettlementEmployeeSerializer,
    FinalSettlementWriteSerializer, SettlementRejectSerializer, SettlementApproveSerializer,
    ExitInterviewSerializer, ExitInterviewAnswersSerializer, ExitInterviewReviewSerializer,
    MONEY_FIELDS, EMPLOYEE_ANSWER_FIELDS,
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


def _notify_hr(title, message, obj):
    for u in User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True):
        _notify(u, 'STATUS_UPDATE', title, message, obj)


def _notify_finance(title, message, obj):
    for u in User.objects.filter(role__in=['FINANCE', 'ADMIN'], is_active=True):
        _notify(u, 'ACTION_REQUIRED', title, message, obj)


# ═══ PART A: Final Settlement ════════════════════════════════════════════════

class SettlementView(APIView):
    """GET/POST/PATCH /api/offboarding/{pk}/settlement/"""
    permission_classes = [IsAuthenticated]

    FINANCE_ROLES = ('FINANCE', 'ADMIN')

    def _get_resignation(self, pk):
        return ResignationRequest.objects.select_related('employee').get(pk=pk)

    def _can_view(self, resignation, user):
        role = user.role
        if role in ('FINANCE', 'HR', 'ADMIN'):
            return True
        if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
            return True
        return resignation.employee.user_id == user.pk

    def get(self, request, pk):
        try:
            resignation = self._get_resignation(pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_view(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            settlement = FinalSettlement.objects.select_related(
                'employee', 'prepared_by', 'reviewed_by', 'approved_by').get(offboarding_request=resignation)
        except FinalSettlement.DoesNotExist:
            return Response({'detail': 'No settlement found.'}, status=status.HTTP_404_NOT_FOUND)

        # Employees get a restricted view (no internal comments / reviewer identities)
        is_owner_only = (request.user.role not in ('FINANCE', 'HR', 'ADMIN')
                         and not _is_manager_of(resignation.employee, request.user))
        if is_owner_only:
            return Response(FinalSettlementEmployeeSerializer(settlement).data)
        return Response(FinalSettlementSerializer(settlement).data)

    def post(self, request, pk):
        if request.user.role not in self.FINANCE_ROLES:
            return Response({'detail': 'Only Finance or Admin can create a settlement.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            if FinalSettlement.objects.filter(offboarding_request=resignation).exists():
                return Response({'detail': 'A settlement already exists for this offboarding.'},
                                status=status.HTTP_400_BAD_REQUEST)
            serializer = FinalSettlementWriteSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            settlement = FinalSettlement(
                offboarding_request=resignation, employee=resignation.employee,
                prepared_by=request.user, settlement_status='DRAFT',
                **serializer.validated_data,
            )
            settlement.recompute_totals()
            settlement.save()
            log_action(actor=request.user, action='SETTLEMENT_CREATED', target_obj=settlement,
                       changes={'status': 'DRAFT', 'net_settlement': str(settlement.net_settlement)},
                       request=request)
        return Response(FinalSettlementSerializer(settlement).data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        if request.user.role not in self.FINANCE_ROLES:
            return Response({'detail': 'Only Finance or Admin can edit financial values.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                resignation = self._get_resignation(pk)
                settlement = FinalSettlement.objects.select_for_update().get(offboarding_request=resignation)
            except (ResignationRequest.DoesNotExist, FinalSettlement.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if settlement.settlement_status not in ('DRAFT',):
                return Response({'detail': f'Settlement can only be edited in DRAFT (currently {settlement.settlement_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            serializer = FinalSettlementWriteSerializer(settlement, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Capture old money values for audit of financial changes
            money_changes = {}
            for f in MONEY_FIELDS:
                if f in serializer.validated_data:
                    old = getattr(settlement, f)
                    new = serializer.validated_data[f]
                    if old != new:
                        money_changes[f] = {'old': str(old), 'new': str(new)}

            settlement = serializer.save()
            settlement.recompute_totals()
            settlement.save(update_fields=['gross_amount', 'total_deductions', 'net_settlement', 'updated_at'])

            if money_changes:
                log_action(actor=request.user, action='SETTLEMENT_AMOUNT_CHANGED', target_obj=settlement,
                           changes={'amounts': money_changes,
                                    'reason': request.data.get('reason', '')}, request=request)
            log_action(actor=request.user, action='SETTLEMENT_UPDATED', target_obj=settlement,
                       changes={'net_settlement': str(settlement.net_settlement)}, request=request)
        return Response(FinalSettlementSerializer(settlement).data)


class SettlementSubmitView(APIView):
    """POST /api/offboarding/{pk}/settlement/submit/ — DRAFT → PREPARED → UNDER_REVIEW."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('FINANCE', 'ADMIN'):
            return Response({'detail': 'Only Finance or Admin can submit a settlement.'},
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            try:
                settlement = FinalSettlement.objects.select_for_update().select_related(
                    'offboarding_request', 'employee').get(offboarding_request_id=pk)
            except FinalSettlement.DoesNotExist:
                return Response({'detail': 'No settlement found.'}, status=status.HTTP_404_NOT_FOUND)

            if settlement.settlement_status != 'DRAFT':
                return Response({'detail': f'Only a DRAFT settlement can be submitted (currently {settlement.settlement_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Recompute to guarantee stored totals are correct at submission.
            settlement.recompute_totals()
            settlement.settlement_status = 'UNDER_REVIEW'
            settlement.save(update_fields=['gross_amount', 'total_deductions', 'net_settlement',
                                           'settlement_status', 'updated_at'])
            log_action(actor=request.user, action='SETTLEMENT_SUBMITTED', target_obj=settlement,
                       changes={'status': {'from': 'DRAFT', 'to': 'UNDER_REVIEW'}}, request=request)
            _notify_hr('Settlement submitted for review',
                       f'Final settlement for {settlement.employee.first_name} {settlement.employee.last_name} is ready for HR review.',
                       settlement)
        return Response(FinalSettlementSerializer(settlement).data)


class SettlementApproveView(APIView):
    """POST /api/offboarding/{pk}/settlement/approve/ — HR/Admin, separation of duties."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can approve a settlement.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = SettlementApproveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            try:
                settlement = FinalSettlement.objects.select_for_update().select_related(
                    'employee').get(offboarding_request_id=pk)
            except FinalSettlement.DoesNotExist:
                return Response({'detail': 'No settlement found.'}, status=status.HTTP_404_NOT_FOUND)

            if settlement.settlement_status != 'UNDER_REVIEW':
                return Response({'detail': f'Only a settlement UNDER_REVIEW can be approved (currently {settlement.settlement_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Separation of duties: preparer cannot approve their own settlement (unless Admin).
            if request.user.role != 'ADMIN' and settlement.prepared_by_id == request.user.pk:
                return Response({'detail': 'The preparer cannot approve their own settlement.'},
                                status=status.HTTP_403_FORBIDDEN)

            settlement.settlement_status = 'APPROVED'
            settlement.reviewed_by = request.user
            settlement.approved_by = request.user
            settlement.settlement_date = serializer.validated_data['settlement_date']  # manual
            if serializer.validated_data.get('comments'):
                settlement.comments = serializer.validated_data['comments']
            settlement.save(update_fields=['settlement_status', 'reviewed_by', 'approved_by',
                                           'settlement_date', 'comments', 'updated_at'])
            log_action(actor=request.user, action='SETTLEMENT_APPROVED', target_obj=settlement,
                       changes={'status': {'from': 'UNDER_REVIEW', 'to': 'APPROVED'},
                                'settlement_date': str(settlement.settlement_date)}, request=request)
            _notify(settlement.employee.user, 'STATUS_UPDATE', 'Final settlement approved',
                    'Your final settlement has been approved.', settlement)
            if settlement.prepared_by:
                _notify(settlement.prepared_by, 'STATUS_UPDATE', 'Settlement approved',
                        'A settlement you prepared has been approved.', settlement)
        return Response(FinalSettlementSerializer(settlement).data)


class SettlementRejectView(APIView):
    """POST /api/offboarding/{pk}/settlement/reject/ — HR/Admin; UNDER_REVIEW → REJECTED → DRAFT."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can reject a settlement.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = SettlementRejectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            try:
                settlement = FinalSettlement.objects.select_for_update().select_related(
                    'employee').get(offboarding_request_id=pk)
            except FinalSettlement.DoesNotExist:
                return Response({'detail': 'No settlement found.'}, status=status.HTTP_404_NOT_FOUND)

            if settlement.settlement_status != 'UNDER_REVIEW':
                return Response({'detail': f'Only a settlement UNDER_REVIEW can be rejected (currently {settlement.settlement_status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            settlement.settlement_status = 'DRAFT'  # returns to DRAFT for correction
            settlement.reviewed_by = request.user
            settlement.comments = serializer.validated_data['comments']
            settlement.save(update_fields=['settlement_status', 'reviewed_by', 'comments', 'updated_at'])
            log_action(actor=request.user, action='SETTLEMENT_REJECTED', target_obj=settlement,
                       changes={'status': {'from': 'UNDER_REVIEW', 'to': 'DRAFT'},
                                'comments': settlement.comments}, request=request)
            if settlement.prepared_by:
                _notify(settlement.prepared_by, 'ACTION_REQUIRED', 'Settlement rejected',
                        f'The settlement was returned for correction: {settlement.comments}', settlement)
        return Response(FinalSettlementSerializer(settlement).data)


# ═══ PART B: Exit Interview ══════════════════════════════════════════════════

class ExitInterviewView(APIView):
    """GET/POST/PATCH /api/offboarding/{pk}/exit-interview/"""
    permission_classes = [IsAuthenticated]

    def _get_resignation(self, pk):
        return ResignationRequest.objects.select_related('employee').get(pk=pk)

    def _can_view(self, resignation, user):
        role = user.role
        if role in ('HR', 'ADMIN'):
            return True
        if role == 'MANAGER' and _is_manager_of(resignation.employee, user):
            return True
        return resignation.employee.user_id == user.pk

    def _is_owner(self, resignation, user):
        return resignation.employee.user_id == user.pk

    def get(self, request, pk):
        try:
            resignation = self._get_resignation(pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_view(resignation, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            ei = ExitInterview.objects.select_related(
                'employee', 'conducted_by', 'reviewed_by').get(offboarding_request=resignation)
        except ExitInterview.DoesNotExist:
            return Response({'detail': 'No exit interview found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExitInterviewSerializer(ei).data)

    def post(self, request, pk):
        """Create (start) the interview — owner employee, HR, or Admin."""
        with transaction.atomic():
            try:
                resignation = ResignationRequest.objects.select_for_update().select_related('employee').get(pk=pk)
            except ResignationRequest.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            is_owner = self._is_owner(resignation, request.user)
            if not (is_owner or request.user.role in ('HR', 'ADMIN')):
                return Response({'detail': 'Only the employee, HR, or Admin can start the exit interview.'},
                                status=status.HTTP_403_FORBIDDEN)
            if ExitInterview.objects.filter(offboarding_request=resignation).exists():
                return Response({'detail': 'An exit interview already exists.'},
                                status=status.HTTP_400_BAD_REQUEST)
            ei = ExitInterview.objects.create(
                offboarding_request=resignation, employee=resignation.employee,
                status='IN_PROGRESS',
            )
            log_action(actor=request.user, action='EXIT_INTERVIEW_STARTED', target_obj=ei,
                       changes={'status': 'IN_PROGRESS'}, request=request)
        return Response(ExitInterviewSerializer(ei).data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        """The employee, or HR (who conducts the interview after the notice period),
        saves/updates answers while IN_PROGRESS."""
        with transaction.atomic():
            try:
                resignation = self._get_resignation(pk)
                ei = ExitInterview.objects.select_for_update().get(offboarding_request=resignation)
            except (ResignationRequest.DoesNotExist, ExitInterview.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            is_owner = self._is_owner(resignation, request.user)
            if not (is_owner or request.user.role in ('HR', 'ADMIN')):
                return Response({'detail': 'Only the employee or HR can edit the exit interview.'},
                                status=status.HTTP_403_FORBIDDEN)
            if ei.status not in ('IN_PROGRESS',):
                return Response({'detail': f'Answers can only be edited while IN_PROGRESS (currently {ei.status}).'},
                                status=status.HTTP_400_BAD_REQUEST)

            serializer = ExitInterviewAnswersSerializer(ei, data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            log_action(actor=request.user, action='EXIT_INTERVIEW_UPDATED', target_obj=ei,
                       changes={'fields': list(serializer.validated_data.keys())}, request=request)
        return Response(ExitInterviewSerializer(ei).data)


class ExitInterviewSubmitView(APIView):
    """POST /api/offboarding/{pk}/exit-interview/submit/ — IN_PROGRESS → COMPLETED (owner)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                ei = ExitInterview.objects.select_for_update().select_related(
                    'offboarding_request__employee', 'employee').get(offboarding_request_id=pk)
            except ExitInterview.DoesNotExist:
                return Response({'detail': 'No exit interview found.'}, status=status.HTTP_404_NOT_FOUND)

            is_owner = ei.offboarding_request.employee.user_id == request.user.pk
            if not (is_owner or request.user.role in ('HR', 'ADMIN')):
                return Response({'detail': 'Only the employee or HR can submit the exit interview.'},
                                status=status.HTTP_403_FORBIDDEN)
            if not ei.can_transition_to('COMPLETED'):
                return Response({'detail': f'Cannot submit from status {ei.status}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            ei.status = 'COMPLETED'
            ei.submitted_at = timezone.now()
            ei.save(update_fields=['status', 'submitted_at', 'updated_at'])
            log_action(actor=request.user, action='EXIT_INTERVIEW_SUBMITTED', target_obj=ei,
                       changes={'status': {'from': 'IN_PROGRESS', 'to': 'COMPLETED'}}, request=request)
            _notify_hr('Exit interview submitted',
                       f'{ei.employee.first_name} {ei.employee.last_name} submitted their exit interview.', ei)
        return Response(ExitInterviewSerializer(ei).data)


class ExitInterviewReviewView(APIView):
    """POST /api/offboarding/{pk}/exit-interview/review/ — HR marks REVIEWED (+ notes).
    Also supports action=reopen to send it back to IN_PROGRESS.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can review an exit interview.'},
                            status=status.HTTP_403_FORBIDDEN)
        action = request.data.get('action', 'review')
        with transaction.atomic():
            try:
                ei = ExitInterview.objects.select_for_update().select_related('employee').get(offboarding_request_id=pk)
            except ExitInterview.DoesNotExist:
                return Response({'detail': 'No exit interview found.'}, status=status.HTTP_404_NOT_FOUND)

            if action == 'reopen':
                if ei.status not in ('COMPLETED', 'REVIEWED'):
                    return Response({'detail': 'Only a completed/reviewed interview can be reopened.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                ei.status = 'IN_PROGRESS'
                ei.save(update_fields=['status', 'updated_at'])
                log_action(actor=request.user, action='EXIT_INTERVIEW_UPDATED', target_obj=ei,
                           changes={'status': {'to': 'IN_PROGRESS'}, 'reopened': True}, request=request)
                return Response(ExitInterviewSerializer(ei).data)

            # review
            serializer = ExitInterviewReviewSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            if ei.status != 'COMPLETED':
                return Response({'detail': f'Only a COMPLETED interview can be reviewed (currently {ei.status}).'},
                                status=status.HTTP_400_BAD_REQUEST)
            # HR review is stored separately — employee answers are never overwritten here.
            ei.status = 'REVIEWED'
            ei.hr_review_notes = serializer.validated_data.get('hr_review_notes', '')
            ei.reviewed_by = request.user
            ei.reviewed_at = timezone.now()
            ei.conducted_by = ei.conducted_by or request.user
            ei.save(update_fields=['status', 'hr_review_notes', 'reviewed_by', 'reviewed_at',
                                   'conducted_by', 'updated_at'])
            log_action(actor=request.user, action='EXIT_INTERVIEW_REVIEWED', target_obj=ei,
                       changes={'status': {'from': 'COMPLETED', 'to': 'REVIEWED'}}, request=request)
            _notify(ei.employee.user, 'STATUS_UPDATE', 'Exit interview reviewed',
                    'Your exit interview has been reviewed by HR. Thank you for your feedback.', ei)
        return Response(ExitInterviewSerializer(ei).data)


class ExitInterviewAnalyticsView(APIView):
    """GET /api/exit-interviews/analytics/ — aggregate only, no individual identification."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        qs = ExitInterview.objects.filter(status__in=['COMPLETED', 'REVIEWED'])
        total = qs.count()

        def _count_by(field):
            out = {}
            for val in qs.values_list(field, flat=True):
                key = val if val not in (None, '') else 'UNSPECIFIED'
                out[str(key)] = out.get(str(key), 0) + 1
            return out

        would_recommend_yes = qs.filter(would_recommend=True).count()
        would_rejoin_yes = qs.filter(would_rejoin=True).count()

        # Overall experience distribution (1–5)
        exp_dist = {str(i): qs.filter(overall_experience=i).count() for i in range(1, 6)}

        return Response({
            'total_interviews': total,
            'top_leaving_reasons': _count_by('primary_reason'),
            'overall_experience_distribution': exp_dist,
            'would_recommend': {'yes': would_recommend_yes,
                                'no': qs.filter(would_recommend=False).count()},
            'would_rejoin': {'yes': would_rejoin_yes,
                             'no': qs.filter(would_rejoin=False).count()},
        })
