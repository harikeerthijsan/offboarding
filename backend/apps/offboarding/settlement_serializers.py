from rest_framework import serializers

from .models import (
    FinalSettlement, ExitInterview,
    SETTLEMENT_ADDITION_FIELDS, SETTLEMENT_DEDUCTION_FIELDS,
)

MONEY_FIELDS = SETTLEMENT_ADDITION_FIELDS + SETTLEMENT_DEDUCTION_FIELDS


# ─── Final Settlement ────────────────────────────────────────────────────────

class FinalSettlementSerializer(serializers.ModelSerializer):
    """Full read serializer — used by Finance/HR/Admin."""
    status_display = serializers.CharField(source='get_settlement_status_display', read_only=True)
    employee_name = serializers.SerializerMethodField()
    prepared_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'offboarding_request', 'employee', 'employee_name',
            'pending_salary', 'leave_encashment', 'bonus', 'incentives', 'other_additions',
            'notice_recovery', 'loan_deduction', 'advance_deduction', 'other_deductions',
            'gross_amount', 'total_deductions', 'net_settlement',
            'settlement_status', 'status_display',
            'prepared_by_name', 'reviewed_by_name', 'approved_by_name',
            'settlement_date', 'comments', 'created_at', 'updated_at',
        ]
        # Totals & workflow fields are backend-controlled.
        read_only_fields = [
            'gross_amount', 'total_deductions', 'net_settlement',
            'settlement_status', 'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        e = obj.employee
        return f"{e.first_name} {e.last_name}" if e else None

    def _uname(self, u):
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_prepared_by_name(self, obj):
        return self._uname(obj.prepared_by)

    def get_reviewed_by_name(self, obj):
        return self._uname(obj.reviewed_by)

    def get_approved_by_name(self, obj):
        return self._uname(obj.approved_by)


class FinalSettlementEmployeeSerializer(serializers.ModelSerializer):
    """Restricted view for the employee — no internal comments / reviewer identities."""
    status_display = serializers.CharField(source='get_settlement_status_display', read_only=True)

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'gross_amount', 'total_deductions', 'net_settlement',
            'settlement_status', 'status_display', 'settlement_date',
        ]
        read_only_fields = fields


class FinalSettlementWriteSerializer(serializers.ModelSerializer):
    """Create/update of financial values — DRAFT only. Totals are recomputed server-side."""
    class Meta:
        model = FinalSettlement
        fields = MONEY_FIELDS + ['settlement_date', 'comments']
        extra_kwargs = {
            'settlement_date': {'required': False, 'allow_null': True},
            **{f: {'required': False} for f in MONEY_FIELDS},
        }

    def validate(self, data):
        for f in MONEY_FIELDS:
            if f in data and data[f] is not None and data[f] < 0:
                raise serializers.ValidationError({f: 'Amount cannot be negative.'})
        return data


class SettlementRejectSerializer(serializers.Serializer):
    comments = serializers.CharField(required=True, allow_blank=False)


class SettlementApproveSerializer(serializers.Serializer):
    settlement_date = serializers.DateField(required=True)
    comments = serializers.CharField(required=False, allow_blank=True, default='')


# ─── Exit Interview ──────────────────────────────────────────────────────────

EMPLOYEE_ANSWER_FIELDS = [
    'interview_date', 'primary_reason', 'secondary_reason',
    'overall_experience', 'manager_feedback', 'work_environment_feedback',
    'role_feedback', 'growth_feedback', 'compensation_feedback',
    'what_went_well', 'what_could_improve', 'suggestions', 'additional_comments',
    'would_recommend', 'would_rejoin',
]


class ExitInterviewSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    employee_name = serializers.SerializerMethodField()
    conducted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExitInterview
        fields = [
            'id', 'offboarding_request', 'employee', 'employee_name',
            'interview_date', 'conducted_by', 'conducted_by_name',
            'primary_reason', 'secondary_reason',
            'overall_experience', 'manager_feedback', 'work_environment_feedback',
            'role_feedback', 'growth_feedback', 'compensation_feedback',
            'what_went_well', 'what_could_improve', 'suggestions', 'additional_comments',
            'would_recommend', 'would_rejoin',
            'status', 'status_display',
            'hr_review_notes', 'reviewed_by_name', 'reviewed_at', 'submitted_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'hr_review_notes', 'reviewed_at', 'submitted_at',
            'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        e = obj.employee
        return f"{e.first_name} {e.last_name}" if e else None

    def _uname(self, u):
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_conducted_by_name(self, obj):
        return self._uname(obj.conducted_by)

    def get_reviewed_by_name(self, obj):
        return self._uname(obj.reviewed_by)


class ExitInterviewAnswersSerializer(serializers.ModelSerializer):
    """Employee-editable answer fields only."""
    class Meta:
        model = ExitInterview
        fields = EMPLOYEE_ANSWER_FIELDS
        extra_kwargs = {
            'interview_date': {'required': False, 'allow_null': True},
            'would_recommend': {'required': False, 'allow_null': True},
            'would_rejoin': {'required': False, 'allow_null': True},
        }


class ExitInterviewReviewSerializer(serializers.Serializer):
    hr_review_notes = serializers.CharField(required=False, allow_blank=True, default='')
