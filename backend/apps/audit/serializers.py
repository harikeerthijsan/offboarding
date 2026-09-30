from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source='actor.email', read_only=True, default='System')

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_email', 'action', 'target_type', 'target_id', 'target_repr', 'changes', 'ip_address', 'timestamp']
        read_only_fields = ['id', 'actor', 'actor_email', 'action', 'target_type', 'target_id', 'target_repr', 'changes', 'ip_address', 'timestamp']
