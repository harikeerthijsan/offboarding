from rest_framework import serializers

from .models import OffboardingDocument, CompanyProfile, DOCUMENT_TYPE


class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = [
            'id', 'name', 'address', 'email', 'phone', 'logo',
            'signatory_name', 'signatory_designation', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class OffboardingDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    employee_name = serializers.SerializerMethodField()
    prepared_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    released_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = OffboardingDocument
        fields = [
            'id', 'offboarding_request', 'employee', 'employee_name',
            'document_type', 'document_type_display', 'document_number', 'document_title',
            'status', 'status_display', 'version', 'document_date',
            'prepared_by_name', 'reviewed_by_name', 'released_by_name',
            'rejection_reason', 'revocation_reason',
            'download_url', 'created_at', 'updated_at',
        ]
        # NOTE: the raw `file` field is intentionally NOT exposed — downloads go
        # only through the permission-checked download endpoint.
        read_only_fields = fields

    def get_employee_name(self, obj):
        e = obj.employee
        return f"{e.first_name} {e.last_name}" if e else None

    def _uname(self, u):
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_prepared_by_name(self, obj):
        return self._uname(obj.prepared_by)

    def get_reviewed_by_name(self, obj):
        return self._uname(obj.reviewed_by)

    def get_released_by_name(self, obj):
        return self._uname(obj.released_by)

    def get_download_url(self, obj):
        # Only advertise a download link for a released document with a file.
        if obj.status == 'RELEASED' and obj.file:
            return f"/api/documents/{obj.id}/download/"
        return None


class GenerateDocumentSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=[c[0] for c in DOCUMENT_TYPE])
    document_date = serializers.DateField(required=False, allow_null=True)
    document_title = serializers.CharField(required=False, allow_blank=True, default='')


class DocumentActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=['submit_review', 'approve', 'reject', 'release', 'revoke', 'regenerate'])
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    document_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        if data['action'] in ('reject', 'revoke') and not data.get('reason', '').strip():
            raise serializers.ValidationError({'reason': 'A reason is required for this action.'})
        return data
