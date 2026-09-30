from rest_framework import serializers
from .models import ResignationRequest, NoticePeriod, RESIGNATION_REASON, notice_months


class ResignationRequestCreateSerializer(serializers.ModelSerializer):
    # resignation_date and last_working_date are set by the server, not the client:
    # resignation_date = submission day; last_working_date = resignation_date + notice
    # period (1 month for tenure < 6 months, otherwise 2 months).
    class Meta:
        model = ResignationRequest
        fields = ['reason', 'notes']

    def validate_reason(self, value):
        valid = [r[0] for r in RESIGNATION_REASON]
        if value not in valid:
            raise serializers.ValidationError('Invalid resignation reason.')
        return value


class ResignationRequestListSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_user_id = serializers.IntegerField(source='employee.user_id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(
        source='employee.department.name', read_only=True, default=''
    )
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ResignationRequest
        fields = [
            'id', 'employee_id', 'employee_user_id', 'employee_name', 'department_name',
            'status', 'status_display', 'reason', 'reason_display',
            'resignation_date', 'last_working_date', 'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class ResignationRequestDetailSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_email = serializers.EmailField(source='employee.email', read_only=True)
    department_name = serializers.CharField(
        source='employee.department.name', read_only=True, default=''
    )
    designation_name = serializers.CharField(
        source='employee.designation.name', read_only=True, default=''
    )
    manager_name = serializers.SerializerMethodField()
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    manager_reviewed_by_name = serializers.SerializerMethodField()
    hr_reviewed_by_name = serializers.SerializerMethodField()
    notice_policy_months = serializers.SerializerMethodField()

    class Meta:
        model = ResignationRequest
        fields = [
            'id', 'employee_id', 'employee_name', 'employee_email',
            'department_name', 'designation_name', 'manager_name',
            'status', 'status_display', 'reason', 'reason_display',
            'resignation_date', 'last_working_date', 'notice_policy_months', 'notes',
            'submitted_by_name',
            'manager_reviewed_by_name', 'manager_reviewed_at', 'manager_notes',
            'hr_reviewed_by_name', 'hr_reviewed_at', 'hr_notes',
            'rejection_reason',
            'final_review_status', 'final_review_date', 'final_approval_date',
            'final_review_comments', 'final_rejection_reason',
            'created_at', 'updated_at',
        ]

    def get_notice_policy_months(self, obj):
        return notice_months(obj.employee.joining_date, obj.resignation_date)

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    def get_manager_name(self, obj):
        mgr = obj.employee.manager
        if mgr:
            return f"{mgr.first_name} {mgr.last_name}"
        return None

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return f"{obj.submitted_by.first_name} {obj.submitted_by.last_name}".strip() or obj.submitted_by.email
        return None

    def get_manager_reviewed_by_name(self, obj):
        if obj.manager_reviewed_by:
            name = f"{obj.manager_reviewed_by.first_name} {obj.manager_reviewed_by.last_name}".strip()
            return name or obj.manager_reviewed_by.email
        return None

    def get_hr_reviewed_by_name(self, obj):
        if obj.hr_reviewed_by:
            name = f"{obj.hr_reviewed_by.first_name} {obj.hr_reviewed_by.last_name}".strip()
            return name or obj.hr_reviewed_by.email
        return None


class ManagerActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class HRActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class NoticePeriodCreateSerializer(serializers.ModelSerializer):
    # Write-only convenience field: when set, the view records an approved early
    # release on the notice period; when explicitly null, any early release is cleared.
    early_relief_date = serializers.DateField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = NoticePeriod
        fields = [
            'notice_period_start_date',
            'notice_period_days',
            'expected_last_working_day',
            'early_relief_date',
            'notice_comments',
        ]
        extra_kwargs = {
            'notice_period_start_date': {'required': False, 'allow_null': True},
            'notice_period_days': {'required': False, 'allow_null': True},
            'expected_last_working_day': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        start = data.get('notice_period_start_date')
        elwd = data.get('expected_last_working_day')
        if start and elwd and elwd < start:
            raise serializers.ValidationError(
                {'expected_last_working_day': 'Expected last working day cannot be before notice period start date.'}
            )
        early = data.get('early_relief_date')
        if early and start and early < start:
            raise serializers.ValidationError(
                {'early_relief_date': 'Early relieving date cannot be before notice period start date.'}
            )
        if early and elwd and early > elwd:
            raise serializers.ValidationError(
                {'early_relief_date': 'Early relieving date cannot be after the expected last working day.'}
            )
        return data


class NoticePeriodUpdateSerializer(serializers.ModelSerializer):
    early_relief_date = serializers.DateField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = NoticePeriod
        fields = [
            'notice_period_start_date',
            'notice_period_days',
            'expected_last_working_day',
            'early_relief_date',
            'actual_last_working_day',
            'notice_comments',
        ]
        extra_kwargs = {
            'notice_period_start_date': {'required': False, 'allow_null': True},
            'notice_period_days': {'required': False, 'allow_null': True},
            'expected_last_working_day': {'required': False, 'allow_null': True},
            'actual_last_working_day': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        instance = self.instance
        start = data.get('notice_period_start_date', instance.notice_period_start_date if instance else None)
        elwd = data.get('expected_last_working_day', instance.expected_last_working_day if instance else None)
        alwd = data.get('actual_last_working_day', instance.actual_last_working_day if instance else None)
        if start and elwd and elwd < start:
            raise serializers.ValidationError(
                {'expected_last_working_day': 'Expected last working day cannot be before notice period start date.'}
            )
        if start and alwd and alwd < start:
            raise serializers.ValidationError(
                {'actual_last_working_day': 'Actual last working day cannot be before notice period start date.'}
            )
        if 'early_relief_date' in data:
            early = data['early_relief_date']
            if early and start and early < start:
                raise serializers.ValidationError(
                    {'early_relief_date': 'Early relieving date cannot be before notice period start date.'}
                )
            if early and elwd and early > elwd:
                raise serializers.ValidationError(
                    {'early_relief_date': 'Early relieving date cannot be after the expected last working day.'}
                )
        return data


class NoticePeriodDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    early_release_requested_by_name = serializers.SerializerMethodField()
    early_release_reviewed_by_name = serializers.SerializerMethodField()
    extension_recorded_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = NoticePeriod
        fields = [
            'id', 'status', 'status_display',
            'notice_period_start_date', 'notice_period_days',
            'expected_last_working_day', 'actual_last_working_day',
            'notice_comments',
            'early_release_requested_by_name', 'early_release_requested_at',
            'early_release_request_reason', 'early_release_date',
            'early_release_approved', 'early_release_reviewed_by_name',
            'early_release_reviewed_at', 'early_release_review_notes',
            'notice_extension_date', 'extension_reason',
            'extension_recorded_by_name', 'extension_recorded_at',
            'completed_by_name', 'completed_at',
            'created_by_name', 'created_at', 'updated_at',
        ]

    def get_early_release_requested_by_name(self, obj):
        u = obj.early_release_requested_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_early_release_reviewed_by_name(self, obj):
        u = obj.early_release_reviewed_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_extension_recorded_by_name(self, obj):
        u = obj.extension_recorded_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_completed_by_name(self, obj):
        u = obj.completed_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_created_by_name(self, obj):
        u = obj.created_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class EarlyReleaseRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)


class EarlyReleaseReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    early_release_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data.get('action') == 'approve' and not data.get('early_release_date'):
            raise serializers.ValidationError(
                {'early_release_date': 'Early release date is required when approving.'}
            )
        return data


class NoticeExtensionSerializer(serializers.Serializer):
    notice_extension_date = serializers.DateField(required=True)
    extension_reason = serializers.CharField(required=True, allow_blank=False)


class CompleteNoticePeriodSerializer(serializers.Serializer):
    actual_last_working_day = serializers.DateField(required=True)
