import os

from rest_framework import serializers

from .models import Policy

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class PolicySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'is_active', 'uploaded_by_name', 'file_name', 'file_size',
            'download_url', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'uploaded_by_name', 'created_at', 'updated_at']

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        if not u:
            return None
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def get_file_name(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None

    def get_file_size(self, obj):
        try:
            return obj.file.size if obj.file else None
        except (FileNotFoundError, ValueError):
            return None

    def get_download_url(self, obj):
        request = self.context.get('request')
        path = f"/api/policies/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path


class PolicyCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = Policy
        # is_active intentionally omitted: new uploads are active by default (model
        # default). DRF coerces a missing BooleanField to False on multipart, which
        # would wrongly hide the policy. Archiving is done via the PATCH endpoint.
        fields = ['id', 'title', 'description', 'category', 'file']
        read_only_fields = ['id']

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f'Unsupported file type "{ext}". Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
            )
        if value.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError('File is too large (max 20 MB).')
        return value

    def to_representation(self, instance):
        return PolicySerializer(instance, context=self.context).data
