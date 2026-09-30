from django.contrib import admin
from .models import ResignationRequest


@admin.register(ResignationRequest)
class ResignationRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'employee', 'status', 'reason', 'resignation_date',
        'manager_reviewed_by', 'hr_reviewed_by', 'created_at',
    ]
    list_filter = ['status', 'reason']
    search_fields = ['employee__employee_id', 'employee__first_name', 'employee__last_name']
    readonly_fields = ['created_at', 'updated_at']
