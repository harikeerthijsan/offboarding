from django.contrib import admin
from .models import Department, Designation, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'first_name', 'last_name', 'department', 'employment_status']
    list_filter = ['employment_status', 'employment_type', 'department']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email', 'pan_number', 'uan_number']
    fieldsets = [
        ('Account', {'fields': ['employee_id', 'user']}),
        ('Personal', {'fields': [
            'first_name', 'last_name', 'email', 'phone', 'profile_photo',
            'date_of_birth', 'gender', 'address',
        ]}),
        ('Employment', {'fields': [
            'department', 'designation', 'manager', 'joining_date',
            'employment_status', 'employment_type', 'location',
        ]}),
        ('Emergency Contact', {'fields': ['emergency_contact_name', 'emergency_contact_phone']}),
        ('Statutory Details', {'fields': ['aadhaar_number', 'pan_number', 'uan_number', 'esi_number']}),
        ('Bank Details', {'fields': [
            'bank_name', 'bank_account_holder_name', 'bank_account_number', 'bank_ifsc_code',
        ]}),
    ]
