import mimetypes
import os

from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHR
from apps.audit.utils import log_action

from .models import Policy
from .serializers import PolicySerializer, PolicyCreateSerializer


class PolicyListCreateView(APIView):
    """GET  /api/policies/  — list policies (all authenticated users see active ones).
       POST /api/policies/  — upload a policy document (HR/Admin, multipart)."""
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsHR()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = Policy.objects.select_related('uploaded_by').all()
        # Non-managers only see active policies; HR/Admin see all (incl. archived).
        if request.user.role not in ('HR', 'ADMIN'):
            qs = qs.filter(is_active=True)
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(title__icontains=search)
        return Response(PolicySerializer(qs, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = PolicyCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        policy = serializer.save(uploaded_by=request.user)
        log_action(actor=request.user, action='POLICY_UPLOADED', target_obj=policy,
                   changes={'title': policy.title, 'category': policy.category}, request=request)
        return Response(
            PolicySerializer(policy, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class PolicyDetailView(APIView):
    """GET/PATCH/DELETE /api/policies/{pk}/ — edit/remove (HR/Admin for write)."""

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT', 'DELETE'):
            return [IsHR()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return Policy.objects.select_related('uploaded_by').get(pk=pk)
        except Policy.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        policy = self._get(pk)
        if policy.is_active is False and request.user.role not in ('HR', 'ADMIN'):
            raise Http404
        return Response(PolicySerializer(policy, context={'request': request}).data)

    def patch(self, request, pk):
        policy = self._get(pk)
        # Metadata-only update (title/description/category/is_active); file replace via re-upload.
        for field in ('title', 'description', 'category'):
            if field in request.data:
                setattr(policy, field, request.data[field])
        if 'is_active' in request.data:
            val = request.data['is_active']
            policy.is_active = val in (True, 'true', 'True', '1', 1)
        policy.save()
        log_action(actor=request.user, action='POLICY_UPDATED', target_obj=policy,
                   changes={'title': policy.title}, request=request)
        return Response(PolicySerializer(policy, context={'request': request}).data)

    def delete(self, request, pk):
        policy = self._get(pk)
        title = policy.title
        policy.file.delete(save=False)
        policy.delete()
        log_action(actor=request.user, action='POLICY_DELETED', target_obj=None,
                   changes={'title': title}, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyDownloadView(APIView):
    """GET /api/policies/{pk}/download/ — authenticated file stream for all employees."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            policy = Policy.objects.get(pk=pk)
        except Policy.DoesNotExist:
            raise Http404
        if not policy.is_active and request.user.role not in ('HR', 'ADMIN'):
            raise Http404
        if not policy.file:
            return Response({'detail': 'No file available.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fh = policy.file.open('rb')
        except (FileNotFoundError, ObjectDoesNotExist):
            raise Http404

        filename = os.path.basename(policy.file.name)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        log_action(actor=request.user, action='POLICY_DOWNLOADED', target_obj=policy,
                   changes={'title': policy.title}, request=request)
        resp = FileResponse(fh, content_type=content_type)
        resp['Content-Disposition'] = f'inline; filename="{filename}"'
        return resp
