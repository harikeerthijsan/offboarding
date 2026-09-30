from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'target_type', 'target_repr', 'timestamp']
    list_filter = ['action', 'target_type']
    readonly_fields = ['actor', 'action', 'target_type', 'target_id', 'target_repr', 'changes', 'ip_address', 'timestamp']
    ordering = ['-timestamp']
