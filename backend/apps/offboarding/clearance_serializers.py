from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Asset, AssetClearance, DepartmentClearance, ClearanceChecklistItem,
    ASSET_CONDITION, CLEARANCE_DEPARTMENTS,
)

User = get_user_model()


# ─── Assets ──────────────────────────────────────────────────────────────────

class AssetSerializer(serializers.ModelSerializer):
    asset_type_display = serializers.CharField(source='get_asset_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_employee_id = serializers.CharField(source='assigned_to.employee_id', read_only=True, default=None)

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_id', 'asset_type', 'asset_type_display', 'asset_name',
            'serial_number', 'description',
            'assigned_to', 'assigned_to_name', 'assigned_to_employee_id',
            'assigned_date', 'status', 'status_display',
            'condition', 'condition_display', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def get_assigned_to_name(self, obj):
        e = obj.assigned_to
        return f"{e.first_name} {e.last_name}" if e else None


class AssetCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            'asset_id', 'asset_type', 'asset_name', 'serial_number', 'description',
            'assigned_to', 'assigned_date', 'condition', 'remarks',
        ]
        extra_kwargs = {
            'assigned_date': {'required': False, 'allow_null': True},
        }


class AssetUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            'asset_type', 'asset_name', 'serial_number', 'description',
            'assigned_to', 'assigned_date', 'condition', 'remarks',
        ]
        extra_kwargs = {
            'assigned_date': {'required': False, 'allow_null': True},
        }


# ─── Asset Clearance ─────────────────────────────────────────────────────────

class AssetClearanceSerializer(serializers.ModelSerializer):
    asset_detail = AssetSerializer(source='asset', read_only=True)
    asset_name = serializers.CharField(source='asset.asset_name', read_only=True)
    asset_code = serializers.CharField(source='asset.asset_id', read_only=True)
    serial_number = serializers.CharField(source='asset.serial_number', read_only=True)
    employee_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_at_return_display', read_only=True)
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AssetClearance
        fields = [
            'id', 'offboarding_request', 'asset', 'asset_detail', 'asset_name',
            'asset_code', 'serial_number', 'employee', 'employee_name',
            'status', 'status_display', 'return_date',
            'condition_at_return', 'condition_display', 'remarks',
            'verified_by_name', 'verified_at', 'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        e = obj.employee
        return f"{e.first_name} {e.last_name}" if e else None

    def get_verified_by_name(self, obj):
        u = obj.verified_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class AssetClearanceCreateSerializer(serializers.Serializer):
    asset = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.all())


class AssetReturnSerializer(serializers.Serializer):
    return_date = serializers.DateField(required=True)
    condition = serializers.ChoiceField(choices=[c[0] for c in ASSET_CONDITION], required=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


class AssetVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['verify', 'reject', 'mark_damaged', 'mark_lost'])
    comments = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] in ('reject', 'mark_damaged') and not data.get('comments', '').strip():
            raise serializers.ValidationError({'comments': 'Comments are required for this action.'})
        return data


# ─── Department Clearance ────────────────────────────────────────────────────

class ClearanceChecklistItemSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ClearanceChecklistItem
        fields = [
            'id', 'department_clearance', 'title', 'description', 'status',
            'status_display', 'completed_by_name', 'completed_at', 'comments',
            'created_at',
        ]
        read_only_fields = ['status', 'completed_by_name', 'completed_at', 'created_at']

    def get_completed_by_name(self, obj):
        u = obj.completed_by
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class ChecklistItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClearanceChecklistItem
        fields = ['title', 'description']


class ChecklistItemUpdateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['complete', 'not_applicable', 'reset', 'reject'])
    comments = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] == 'reject' and not data.get('comments', '').strip():
            raise serializers.ValidationError({'comments': 'Comments are required to reject an item.'})
        return data


class DepartmentClearanceSerializer(serializers.ModelSerializer):
    department_display = serializers.CharField(source='get_department_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    cleared_by_name = serializers.SerializerMethodField()
    checklist_items = ClearanceChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = DepartmentClearance
        fields = [
            'id', 'offboarding_request', 'department', 'department_display',
            'assigned_to', 'assigned_to_name', 'status', 'status_display',
            'comments', 'clearance_date', 'cleared_by_name', 'cleared_at',
            'created_at', 'updated_at', 'checklist_items',
        ]

    def _uname(self, u):
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_assigned_to_name(self, obj):
        return self._uname(obj.assigned_to)

    def get_cleared_by_name(self, obj):
        return self._uname(obj.cleared_by)


class DepartmentClearanceCreateSerializer(serializers.Serializer):
    department = serializers.ChoiceField(choices=[c[0] for c in CLEARANCE_DEPARTMENTS])
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True,
    )


class DepartmentClearanceActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['clear', 'reject', 'in_progress', 'not_applicable', 'reopen'])
    clearance_date = serializers.DateField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] == 'clear' and not data.get('clearance_date'):
            raise serializers.ValidationError({'clearance_date': 'A clearance date must be entered to clear a department.'})
        if data['action'] == 'reject' and not data.get('comments', '').strip():
            raise serializers.ValidationError({'comments': 'Comments are required to reject a clearance.'})
        return data
