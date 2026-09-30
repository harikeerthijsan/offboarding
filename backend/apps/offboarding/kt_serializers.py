from rest_framework import serializers

from apps.employees.models import Employee
from .models import Project, KnowledgeTransfer, KTDocument


# ─── Project ─────────────────────────────────────────────────────────────────

class ProjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'code', 'description', 'department', 'department_name',
            'manager', 'manager_name', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_manager_name(self, obj):
        if obj.manager:
            return f"{obj.manager.first_name} {obj.manager.last_name}"
        return None


# ─── KT Documents ────────────────────────────────────────────────────────────

class KTDocumentSerializer(serializers.ModelSerializer):
    added_by_name = serializers.SerializerMethodField()

    class Meta:
        model = KTDocument
        fields = ['id', 'url', 'description', 'added_by_name', 'created_at']
        read_only_fields = ['added_by_name', 'created_at']

    def get_added_by_name(self, obj):
        u = obj.added_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class KTDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KTDocument
        fields = ['url', 'description']

    def validate_url(self, value):
        # URLField already validates format; guard against obvious secret leakage.
        lowered = value.lower()
        for bad in ('password=', 'api_key=', 'apikey=', 'secret=', 'token='):
            if bad in lowered:
                raise serializers.ValidationError('Do not include credentials or secrets in documentation URLs.')
        return value


# ─── KT create / update ──────────────────────────────────────────────────────

def _validate_kt_dates(start, target, completed):
    if start and target and target < start:
        raise serializers.ValidationError(
            {'target_completion_date': 'Target completion date cannot be before the start date.'}
        )
    if start and completed and completed < start:
        raise serializers.ValidationError(
            {'completed_date': 'Completion date cannot be before the start date.'}
        )


class KnowledgeTransferCreateSerializer(serializers.ModelSerializer):
    receiver = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(employment_status='ACTIVE')
    )

    class Meta:
        model = KnowledgeTransfer
        fields = [
            'title', 'description', 'project', 'responsibility',
            'receiver', 'priority', 'start_date', 'target_completion_date',
        ]
        extra_kwargs = {
            'start_date': {'required': False, 'allow_null': True},
            'target_completion_date': {'required': False, 'allow_null': True},
        }

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('Title is required.')
        return value

    def validate(self, data):
        offboarding_employee = self.context.get('offboarding_employee')
        receiver = data.get('receiver')
        if offboarding_employee and receiver and receiver.pk == offboarding_employee.pk:
            raise serializers.ValidationError(
                {'receiver': 'The offboarding employee cannot be their own receiver.'}
            )
        _validate_kt_dates(data.get('start_date'), data.get('target_completion_date'), None)
        return data


class KTEmployeeUpdateSerializer(serializers.ModelSerializer):
    """Fields the offboarding employee may edit while working on the KT."""
    class Meta:
        model = KnowledgeTransfer
        fields = ['description', 'responsibility', 'completion_notes']


class KTManagerUpdateSerializer(serializers.ModelSerializer):
    """Fields HR / Manager / Admin may edit (task metadata; never status/receiver here)."""
    class Meta:
        model = KnowledgeTransfer
        fields = [
            'title', 'description', 'project', 'responsibility', 'priority',
            'start_date', 'target_completion_date', 'completion_notes',
        ]
        extra_kwargs = {
            'start_date': {'required': False, 'allow_null': True},
            'target_completion_date': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        inst = self.instance
        start = data.get('start_date', inst.start_date if inst else None)
        target = data.get('target_completion_date', inst.target_completion_date if inst else None)
        completed = inst.completed_date if inst else None
        _validate_kt_dates(start, target, completed)
        return data


# ─── KT read serializers ─────────────────────────────────────────────────────

class KnowledgeTransferListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    assigned_to_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = KnowledgeTransfer
        fields = [
            'id', 'title', 'project', 'project_name', 'responsibility',
            'assigned_to', 'assigned_to_name', 'receiver', 'receiver_name',
            'priority', 'priority_display', 'status', 'status_display',
            'start_date', 'target_completion_date', 'completed_date',
            'created_at', 'updated_at',
        ]

    def get_assigned_to_name(self, obj):
        e = obj.assigned_to
        return f"{e.first_name} {e.last_name}" if e else None

    def get_receiver_name(self, obj):
        e = obj.receiver
        return f"{e.first_name} {e.last_name}" if e else None


class KnowledgeTransferDetailSerializer(serializers.ModelSerializer):
    project_detail = ProjectSerializer(source='project', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_user_id = serializers.IntegerField(source='assigned_to.user_id', read_only=True)
    receiver_name = serializers.SerializerMethodField()
    receiver_user_id = serializers.IntegerField(source='receiver.user_id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    receiver_reviewed_by_name = serializers.SerializerMethodField()
    manager_reviewed_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    documents = KTDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = KnowledgeTransfer
        fields = [
            'id', 'offboarding_request', 'title', 'description',
            'project', 'project_detail', 'project_name', 'responsibility',
            'assigned_to', 'assigned_to_name', 'assigned_to_user_id',
            'receiver', 'receiver_name', 'receiver_user_id',
            'priority', 'priority_display', 'status', 'status_display',
            'start_date', 'target_completion_date', 'completed_date',
            'completion_notes', 'receiver_comments', 'manager_comments',
            'submitted_at',
            'receiver_reviewed_by_name', 'receiver_reviewed_at',
            'manager_reviewed_by_name', 'manager_reviewed_at',
            'created_by_name', 'created_at', 'updated_at',
            'documents',
        ]

    def get_assigned_to_name(self, obj):
        e = obj.assigned_to
        return f"{e.first_name} {e.last_name}" if e else None

    def get_receiver_name(self, obj):
        e = obj.receiver
        return f"{e.first_name} {e.last_name}" if e else None

    def _uname(self, u):
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_receiver_reviewed_by_name(self, obj):
        return self._uname(obj.receiver_reviewed_by)

    def get_manager_reviewed_by_name(self, obj):
        return self._uname(obj.manager_reviewed_by)

    def get_created_by_name(self, obj):
        return self._uname(obj.created_by)


# ─── Action serializers ──────────────────────────────────────────────────────

class KTReceiverActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'request_changes'])
    comments = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] == 'request_changes' and not data.get('comments', '').strip():
            raise serializers.ValidationError(
                {'comments': 'Comments are required when requesting changes.'}
            )
        return data


class KTManagerActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'request_changes'])
    completed_date = serializers.DateField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] == 'approve' and not data.get('completed_date'):
            raise serializers.ValidationError(
                {'completed_date': 'A completion date must be entered to approve a KT.'}
            )
        if data['action'] == 'request_changes' and not data.get('comments', '').strip():
            raise serializers.ValidationError(
                {'comments': 'Comments are required when requesting changes.'}
            )
        return data


class KTReassignSerializer(serializers.Serializer):
    receiver = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(employment_status='ACTIVE')
    )
    comments = serializers.CharField(required=False, allow_blank=True, default='')
