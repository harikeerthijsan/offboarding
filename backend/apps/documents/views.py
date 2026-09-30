from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.utils import log_action
from apps.employees.models import Employee
from apps.notifications.models import Notification
from apps.offboarding.models import ResignationRequest

from .models import OffboardingDocument, CompanyProfile
from .serializers import (
    OffboardingDocumentSerializer, CompanyProfileSerializer,
    GenerateDocumentSerializer, DocumentActionSerializer,
)
from .services.generation import generate_document, regenerate_document

User = get_user_model()


# ─── helpers ─────────────────────────────────────────────────────────────────

def _employee_for(user):
    try:
        return Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        return None


def _is_manager_of(employee, user):
    mgr = _employee_for(user)
    return bool(mgr and employee and employee.manager_id == mgr.pk)


def _notify_doc(recipient_user, ntype, title, message, doc):
    if recipient_user:
        Notification.objects.create(
            recipient=recipient_user, notification_type=ntype, title=title, message=message,
            related_object_type='OffboardingDocument', related_object_id=doc.pk,
            related_offboarding=doc.offboarding_request,
        )


def _can_generate(resignation, user, document_type):
    role = user.role
    if role in ('HR', 'ADMIN'):
        return True
    if role == 'FINANCE' and document_type == 'FULL_FINAL_SETTLEMENT':
        return True
    return False


def _can_view_document(doc, user):
    """Metadata visibility."""
    role = user.role
    if role in ('HR', 'ADMIN'):
        return True
    if role == 'FINANCE' and doc.is_financial:
        return True
    is_owner = doc.employee.user_id == user.pk
    if is_owner:
        # Employee only sees released, non-revoked documents.
        return doc.status == 'RELEASED'
    if role == 'MANAGER' and _is_manager_of(doc.employee, user) and not doc.is_financial:
        return doc.status == 'RELEASED'
    return False


def _can_download(doc, user):
    # Download requires a released document with a file, plus view permission.
    if doc.status != 'RELEASED' or not doc.file:
        # HR/Admin may still download non-released for review purposes.
        if user.role in ('HR', 'ADMIN') and doc.file:
            return True
        return False
    return _can_view_document(doc, user)


# ─── Company profile ─────────────────────────────────────────────────────────

class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CompanyProfileSerializer(CompanyProfile.get_solo()).data)

    def put(self, request):
        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can edit the company profile.'},
                            status=status.HTTP_403_FORBIDDEN)
        profile = CompanyProfile.get_solo()
        serializer = CompanyProfileSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        log_action(actor=request.user, action='COMPANY_PROFILE_UPDATED', target_obj=profile,
                   changes=serializer.validated_data, request=request)
        return Response(CompanyProfileSerializer(profile).data)


# ─── Document list / generate ────────────────────────────────────────────────

class DocumentListCreateView(APIView):
    """GET/POST /api/offboarding/{pk}/documents/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        qs = OffboardingDocument.objects.select_related(
            'employee', 'prepared_by', 'reviewed_by', 'released_by').filter(offboarding_request=resignation)
        visible = [d for d in qs if _can_view_document(d, request.user)]
        if not visible and not (
            request.user.role in ('HR', 'ADMIN', 'FINANCE')
            or resignation.employee.user_id == request.user.pk
            or _is_manager_of(resignation.employee, request.user)
        ):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(OffboardingDocumentSerializer(visible, many=True).data)

    def post(self, request, pk):
        serializer = GenerateDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        document_type = serializer.validated_data['document_type']

        try:
            resignation = ResignationRequest.objects.select_related('employee').get(pk=pk)
        except ResignationRequest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_generate(resignation, request.user, document_type):
            return Response({'detail': 'You are not authorised to generate this document.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            doc = generate_document(
                resignation, document_type,
                serializer.validated_data.get('document_date'),
                request.user,
                serializer.validated_data.get('document_title') or None,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        log_action(actor=request.user, action='DOCUMENT_GENERATED', target_obj=doc,
                   changes={'type': document_type, 'number': doc.document_number,
                            'version': doc.version}, request=request)
        return Response(OffboardingDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


# ─── Document detail / action / download ─────────────────────────────────────

class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            doc = OffboardingDocument.objects.select_related(
                'employee', 'offboarding_request', 'prepared_by', 'reviewed_by', 'released_by').get(pk=pk)
        except OffboardingDocument.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_document(doc, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(OffboardingDocumentSerializer(doc).data)


class DocumentActionView(APIView):
    """POST /api/documents/{pk}/action/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = DocumentActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        if request.user.role not in ('HR', 'ADMIN'):
            return Response({'detail': 'Only HR or Admin can manage document workflow.'},
                            status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            try:
                doc = OffboardingDocument.objects.select_for_update().select_related(
                    'employee', 'offboarding_request').get(pk=pk)
            except OffboardingDocument.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

            if action == 'regenerate':
                try:
                    new_doc = regenerate_document(
                        doc, serializer.validated_data.get('document_date'), request.user)
                except ValueError as e:
                    return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                log_action(actor=request.user, action='DOCUMENT_REGENERATED', target_obj=new_doc,
                           changes={'from_version': doc.version, 'new_version': new_doc.version},
                           request=request)
                return Response(OffboardingDocumentSerializer(new_doc).data, status=status.HTTP_201_CREATED)

            old = doc.status
            if action == 'submit_review':
                if not doc.can_transition_to('UNDER_REVIEW'):
                    return Response({'detail': f'Cannot submit for review from {old}.'}, status=status.HTTP_400_BAD_REQUEST)
                doc.status = 'UNDER_REVIEW'
                doc.save(update_fields=['status', 'updated_at'])
                audit = 'DOCUMENT_SUBMITTED_REVIEW'
            elif action == 'approve':
                if not doc.can_transition_to('APPROVED'):
                    return Response({'detail': f'Cannot approve from {old}.'}, status=status.HTTP_400_BAD_REQUEST)
                doc.status = 'APPROVED'
                doc.reviewed_by = request.user
                doc.save(update_fields=['status', 'reviewed_by', 'updated_at'])
                audit = 'DOCUMENT_APPROVED'
                _notify_doc(doc.employee.user, 'DOCUMENT_APPROVED', 'Document approved',
                            f'Your {doc.get_document_type_display()} has been approved.', doc)
            elif action == 'reject':
                # Return to GENERATED with a reason; a fresh version is produced on regenerate.
                if doc.status not in ('GENERATED', 'UNDER_REVIEW'):
                    return Response({'detail': f'Cannot reject from {old}.'}, status=status.HTTP_400_BAD_REQUEST)
                doc.status = 'GENERATED'
                doc.rejection_reason = reason
                doc.reviewed_by = request.user
                doc.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'updated_at'])
                audit = 'DOCUMENT_REJECTED'
            elif action == 'release':
                if not doc.can_transition_to('RELEASED'):
                    return Response({'detail': f'Cannot release from {old}.'}, status=status.HTTP_400_BAD_REQUEST)
                doc.status = 'RELEASED'
                doc.released_by = request.user
                doc.save(update_fields=['status', 'released_by', 'updated_at'])
                audit = 'DOCUMENT_RELEASED'
                _notify_doc(doc.employee.user, 'DOCUMENT_RELEASED', 'Document released',
                            f'Your {doc.get_document_type_display()} has been released and is ready to download.', doc)
            elif action == 'revoke':
                if not doc.can_transition_to('REVOKED'):
                    return Response({'detail': f'Cannot revoke from {old}.'}, status=status.HTTP_400_BAD_REQUEST)
                doc.status = 'REVOKED'
                doc.revocation_reason = reason
                doc.save(update_fields=['status', 'revocation_reason', 'updated_at'])
                audit = 'DOCUMENT_REVOKED'
                _notify_doc(doc.employee.user, 'DOCUMENT_REVOKED', 'Document revoked',
                            f'Your {doc.get_document_type_display()} has been revoked. Reason: {reason}', doc)
            else:
                return Response({'detail': 'Unknown action.'}, status=status.HTTP_400_BAD_REQUEST)

            log_action(actor=request.user, action=audit, target_obj=doc,
                       changes={'status': {'from': old, 'to': doc.status}, 'reason': reason},
                       request=request)

        return Response(OffboardingDocumentSerializer(doc).data)


class DocumentDownloadView(APIView):
    """GET /api/documents/{pk}/download/ — secure, permission-checked file stream."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            doc = OffboardingDocument.objects.select_related('employee').get(pk=pk)
        except OffboardingDocument.DoesNotExist:
            raise Http404
        if not _can_download(doc, request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if not doc.file:
            return Response({'detail': 'No file available.'}, status=status.HTTP_404_NOT_FOUND)

        log_action(actor=request.user, action='DOCUMENT_DOWNLOADED', target_obj=doc,
                   changes={'number': doc.document_number}, request=request)
        try:
            fh = doc.file.open('rb')
        except (FileNotFoundError, ObjectDoesNotExist):
            raise Http404
        resp = FileResponse(fh, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{doc.document_number}.pdf"'
        return resp
