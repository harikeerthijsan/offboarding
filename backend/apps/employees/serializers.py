from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import Department, Designation, Employee

User = get_user_model()


class DesignationSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True, default=None
    )

    class Meta:
        model = Designation
        fields = ['id', 'name', 'code', 'description', 'department', 'department_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'head', 'head_name', 'is_active', 'employee_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_head_name(self, obj):
        if obj.head:
            return f"{obj.head.first_name} {obj.head.last_name}"
        return None

    def get_employee_count(self, obj):
        return obj.employees.filter(employment_status='ACTIVE').count()


class ManagerBriefSerializer(serializers.ModelSerializer):
    designation_name = serializers.CharField(source='designation.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'first_name', 'last_name', 'email', 'designation_name', 'department_name']


class EmployeeListSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    designation_name = serializers.CharField(source='designation.name', read_only=True, default='')
    manager_name = serializers.SerializerMethodField()
    manager_id = serializers.IntegerField(source='manager.id', read_only=True, default=None)

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'first_name', 'last_name', 'email', 'phone',
            'department', 'designation_name', 'manager_id', 'manager_name',
            'joining_date', 'employment_type', 'employment_status', 'location',
        ]

    def get_manager_name(self, obj):
        if obj.manager:
            return f"{obj.manager.first_name} {obj.manager.last_name}"
        return None


class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    designation = DesignationSerializer(read_only=True)
    manager = ManagerBriefSerializer(read_only=True)
    direct_reports_count = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'user', 'first_name', 'last_name', 'email',
            'phone', 'profile_photo', 'date_of_birth', 'gender',
            'department', 'designation', 'manager',
            'joining_date', 'employment_status', 'employment_type',
            'location', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
            'direct_reports_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_direct_reports_count(self, obj):
        return obj.direct_reports.count()


class EmployeeCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source='user', queryset=User.objects.all(),
    )
    department_id = serializers.PrimaryKeyRelatedField(
        source='department', queryset=Department.objects.all(),
        required=False, allow_null=True,
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        source='designation', queryset=Designation.objects.all(),
        required=False, allow_null=True,
    )
    manager_id = serializers.PrimaryKeyRelatedField(
        source='manager', queryset=Employee.objects.all(),
        required=False, allow_null=True,
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'user_id', 'first_name', 'last_name', 'email',
            'phone', 'date_of_birth', 'gender',
            'department_id', 'designation_id', 'manager_id',
            'joining_date', 'employment_type', 'employment_status',
            'location', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        manager = attrs.get('manager')
        instance = self.instance
        if manager and instance and manager.pk == instance.pk:
            raise serializers.ValidationError({'manager_id': 'An employee cannot be their own manager.'})
        return attrs

    def to_representation(self, instance):
        return EmployeeSerializer(instance, context=self.context).data
