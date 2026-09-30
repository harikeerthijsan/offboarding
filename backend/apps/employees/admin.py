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
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
