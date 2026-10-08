import re
import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import ROLE_CHOICES
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
            'aadhaar_number', 'pan_number', 'uan_number', 'esi_number',
            'bank_name', 'bank_account_holder_name',
            'bank_account_number', 'bank_ifsc_code',
            'direct_reports_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_direct_reports_count(self, obj):
        return obj.direct_reports.count()


class StatutoryFieldsMixin:
    """Shared format validation for statutory / bank fields. Blank is allowed;
    non-empty values are normalized and must match the expected format."""

    def validate_aadhaar_number(self, value):
        value = (value or '').replace(' ', '')
        if value and not re.fullmatch(r'\d{12}', value):
            raise serializers.ValidationError('Aadhaar number must be 12 digits.')
        return value

    def validate_pan_number(self, value):
        value = (value or '').upper().strip()
        if value and not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', value):
            raise serializers.ValidationError('PAN must be in the format ABCDE1234F.')
        return value

    def validate_uan_number(self, value):
        value = (value or '').strip()
        if value and not re.fullmatch(r'\d{12}', value):
            raise serializers.ValidationError('UAN must be 12 digits.')
        return value

    def validate_bank_ifsc_code(self, value):
        value = (value or '').upper().strip()
        if value and not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', value):
            raise serializers.ValidationError('IFSC must be in the format ABCD0123456.')
        return value


class EmployeeCreateSerializer(StatutoryFieldsMixin, serializers.ModelSerializer):
    # Optional: link to an existing user account. If omitted on create, a new
    # user account is provisioned automatically from the employee's details.
    user_id = serializers.PrimaryKeyRelatedField(
        source='user', queryset=User.objects.all(),
        required=False, allow_null=True,
    )
    # Write-only account-provisioning fields (ignored when user_id is given).
    role = serializers.ChoiceField(
        choices=ROLE_CHOICES, write_only=True, required=False, default='EMPLOYEE',
    )
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, min_length=8,
    )
    # Company-mandated details — required when HR/Admin creates an employee.
    department_id = serializers.PrimaryKeyRelatedField(
        source='department', queryset=Department.objects.all(),
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        source='designation', queryset=Designation.objects.all(),
    )
    manager_id = serializers.PrimaryKeyRelatedField(
        source='manager', queryset=Employee.objects.all(),
        required=False, allow_null=True,
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'user_id', 'role', 'password',
            'first_name', 'last_name', 'email',
            'phone', 'date_of_birth', 'gender',
            'department_id', 'designation_id', 'manager_id',
            'joining_date', 'employment_type', 'employment_status',
            'location', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
            'aadhaar_number', 'pan_number', 'uan_number', 'esi_number',
            'bank_name', 'bank_account_holder_name',
            'bank_account_number', 'bank_ifsc_code',
        ]
        read_only_fields = ['id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On partial update (HR editing an existing employee), company fields
        # are not mandatory — only enforce them when creating.
        if self.instance is not None or getattr(self, 'partial', False):
            self.fields['department_id'].required = False
            self.fields['designation_id'].required = False

    def validate(self, attrs):
        manager = attrs.get('manager')
        instance = self.instance
        if manager and instance and manager.pk == instance.pk:
            raise serializers.ValidationError({'manager_id': 'An employee cannot be their own manager.'})

        # Account provisioning is only relevant on create without a linked user.
        if instance is None and attrs.get('user') is None:
            email = attrs.get('email')
            employee_id = attrs.get('employee_id')
            if email and User.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError({
                    'email': 'A user account with this email already exists. '
                             'Link it via user_id instead.'
                })
            if employee_id and User.objects.filter(username=employee_id).exists():
                raise serializers.ValidationError({
                    'employee_id': 'A user account with this username already exists.'
                })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data.pop('role', 'EMPLOYEE')
        password = validated_data.pop('password', None) or None
        user = validated_data.get('user')

        generated_password = None
        if user is None:
            if not password:
                password = secrets.token_urlsafe(9)
                generated_password = password
            user = User(
                email=validated_data['email'],
                username=validated_data['employee_id'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                role=role,
            )
            user.set_password(password)
            user.save()
            validated_data['user'] = user

        employee = super().create(validated_data)
        employee._generated_password = generated_password
        return employee

    def update(self, instance, validated_data):
        # role/password are provisioning-only; never applied on update.
        validated_data.pop('role', None)
        validated_data.pop('password', None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = EmployeeSerializer(instance, context=self.context).data
        generated_password = getattr(instance, '_generated_password', None)
        if generated_password:
            data['temporary_password'] = generated_password
        return data


class EmployeeSelfUpdateSerializer(StatutoryFieldsMixin, serializers.ModelSerializer):
    """Lets an employee update their own personal details. Company-controlled
    fields (employee_id, names, email, role, department, designation, manager,
    joining date, employment status/type) are intentionally excluded."""

    class Meta:
        model = Employee
        fields = [
            'phone', 'date_of_birth', 'gender', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
            'aadhaar_number', 'pan_number', 'uan_number', 'esi_number',
            'bank_name', 'bank_account_holder_name',
            'bank_account_number', 'bank_ifsc_code',
        ]

    def to_representation(self, instance):
        return EmployeeSerializer(instance, context=self.context).data
