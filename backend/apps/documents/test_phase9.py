import tempfile

from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.notifications.models import Notification
from apps.offboarding.models import (
    ResignationRequest, NoticePeriod, FinalSettlement, DepartmentClearance,
)
from apps.documents.models import OffboardingDocument
from apps.offboarding.tests import NoticePeriodSetup, auth

_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_MEDIA)
class DocumentSetup(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        self.resignation = ResignationRequest.objects.get(pk=self.rid)
        # Manual last working day so relieving/experience can be generated.
        self.resignation.last_working_date = '2026-11-30'
        self.resignation.save(update_fields=['last_working_date'])
        self.finance_user = User.objects.create_user(
            email='fin9@test.com', username='fin9', password='pass', role='FINANCE',
            first_name='Fin', last_name='Nine',
        )

    def _generate(self, dtype='RELIEVING_LETTER', actor=None, date='2026-12-01'):
        auth(self.client, actor or self.hr_user)
        payload = {'document_type': dtype}
        if date is not None:
            payload['document_date'] = date
        return self.client.post(f'/api/offboarding/{self.rid}/documents/', payload, format='json')

    def _approved_settlement(self):
        return FinalSettlement.objects.create(
            offboarding_request=self.resignation, employee=self.employee,
            settlement_status='APPROVED', pending_salary=5000, gross_amount=5000,
            total_deductions=0, net_settlement=5000, settlement_date='2026-12-01',
        )

    def _release(self, doc_id):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'approve'}, format='json')
        return self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'release'}, format='json')


@override_settings(MEDIA_ROOT=_MEDIA)
class DocumentGenerationTest(DocumentSetup):
    def test_hr_generate_relieving(self):
        r = self._generate('RELIEVING_LETTER')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'GENERATED')
        self.assertTrue(r.data['document_number'].startswith('REL-'))

    def test_hr_generate_experience(self):
        r = self._generate('EXPERIENCE_LETTER')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r.data['document_number'].startswith('EXP-'))

    def test_generate_settlement_requires_approved_settlement(self):
        r = self._generate('FULL_FINAL_SETTLEMENT')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_settlement_after_approval(self):
        self._approved_settlement()
        r = self._generate('FULL_FINAL_SETTLEMENT')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_finance_can_generate_settlement(self):
        self._approved_settlement()
        r = self._generate('FULL_FINAL_SETTLEMENT', actor=self.finance_user)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_finance_cannot_generate_relieving(self):
        r = self._generate('RELIEVING_LETTER', actor=self.finance_user)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_generate_clearance(self):
        DepartmentClearance.objects.create(
            offboarding_request=self.resignation, department='IT', status='CLEARED')
        r = self._generate('EXIT_CLEARANCE')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r.data['document_number'].startswith('CLR-'))

    def test_employee_cannot_generate(self):
        r = self._generate('RELIEVING_LETTER', actor=self.employee_user)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_relieving_blocked_without_lwd(self):
        self.resignation.last_working_date = None
        self.resignation.save(update_fields=['last_working_date'])
        r = self._generate('RELIEVING_LETTER')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_date_optional_but_not_auto(self):
        r = self._generate('RELIEVING_LETTER', date=None)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(r.data['document_date'])

    def test_manual_document_date_stored(self):
        r = self._generate('RELIEVING_LETTER', date='2026-12-15')
        self.assertEqual(r.data['document_date'], '2026-12-15')

    def test_generate_creates_pdf_file(self):
        r = self._generate('RELIEVING_LETTER')
        doc = OffboardingDocument.objects.get(pk=r.data['id'])
        self.assertTrue(bool(doc.file))

    def test_document_generated_audited(self):
        from apps.audit.models import AuditLog
        self._generate('RELIEVING_LETTER')
        self.assertTrue(AuditLog.objects.filter(action='DOCUMENT_GENERATED').exists())


@override_settings(MEDIA_ROOT=_MEDIA)
class DocumentWorkflowTest(DocumentSetup):
    def test_full_workflow(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'submit_review'}, format='json')
        self.assertEqual(r.data['status'], 'UNDER_REVIEW')
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'approve'}, format='json')
        self.assertEqual(r.data['status'], 'APPROVED')
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'release'}, format='json')
        self.assertEqual(r.data['status'], 'RELEASED')

    def test_approve_directly_from_generated(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'approve'}, format='json')
        self.assertEqual(r.data['status'], 'APPROVED')

    def test_reject_requires_reason(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'reject'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_release_before_approve(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'release'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_release(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'approve'}, format='json')
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'release'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_release_notifies_employee(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        self.assertTrue(Notification.objects.filter(
            recipient=self.employee_user, notification_type='DOCUMENT_RELEASED').exists())

    def test_revoke_requires_reason(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/', {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke_released_document(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/',
                             {'action': 'revoke', 'reason': 'Error in content'}, format='json')
        self.assertEqual(r.data['status'], 'REVOKED')

    def test_regenerate_creates_new_version(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/documents/{doc_id}/action/',
                             {'action': 'regenerate', 'document_date': '2026-12-20'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['version'], 2)


@override_settings(MEDIA_ROOT=_MEDIA)
class DocumentSecurityTest(DocumentSetup):
    def test_employee_cannot_see_unreleased(self):
        self._generate('RELIEVING_LETTER')
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/documents/')
        self.assertEqual(len(r.data), 0)  # nothing released yet

    def test_employee_sees_released(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/documents/')
        self.assertEqual(len(r.data), 1)

    def test_employee_cannot_download_unreleased(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_can_download_released(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_other_employee_cannot_download(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_download_revoked(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.hr_user)
        self.client.post(f'/api/documents/{doc_id}/action/',
                         {'action': 'revoke', 'reason': 'x'}, format='json')
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_see_financial_document(self):
        self._approved_settlement()
        doc_id = self._generate('FULL_FINAL_SETTLEMENT').data['id']
        self._release(doc_id)
        auth(self.client, self.manager_user)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_can_download_settlement(self):
        self._approved_settlement()
        doc_id = self._generate('FULL_FINAL_SETTLEMENT').data['id']
        self._release(doc_id)
        auth(self.client, self.finance_user)
        r = self.client.get(f'/api/documents/{doc_id}/download/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_serializer_does_not_expose_file_path(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/documents/{doc_id}/')
        self.assertNotIn('file', r.data)


@override_settings(MEDIA_ROOT=_MEDIA)
class DocumentVersioningTest(DocumentSetup):
    def test_versions_increment(self):
        self._generate('EXPERIENCE_LETTER')
        r2 = self._generate('EXPERIENCE_LETTER')
        self.assertEqual(r2.data['version'], 2)

    def test_unique_document_numbers(self):
        n1 = self._generate('EXPERIENCE_LETTER').data['document_number']
        n2 = self._generate('EXPERIENCE_LETTER').data['document_number']
        self.assertNotEqual(n1, n2)


@override_settings(MEDIA_ROOT=_MEDIA)
class CompanyProfileTest(DocumentSetup):
    def test_get_profile(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/company-profile/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_hr_can_update_profile(self):
        auth(self.client, self.hr_user)
        r = self.client.put('/api/company-profile/', {'name': 'Acme Corp'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['name'], 'Acme Corp')

    def test_employee_cannot_update_profile(self):
        auth(self.client, self.employee_user)
        r = self.client.put('/api/company-profile/', {'name': 'Hack'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(MEDIA_ROOT=_MEDIA)
class NotificationCenterTest(DocumentSetup):
    def test_unread_filter(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.employee_user)
        r = self.client.get('/api/notifications/?unread=true')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data['results'] if isinstance(r.data, dict) and 'results' in r.data else r.data
        self.assertTrue(all(not n['is_read'] for n in results))

    def test_mark_read_sets_read_at(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        auth(self.client, self.employee_user)
        notif = Notification.objects.filter(recipient=self.employee_user).first()
        self.client.post(f'/api/notifications/{notif.id}/read/')
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_notification_has_related_offboarding(self):
        doc_id = self._generate('RELIEVING_LETTER').data['id']
        self._release(doc_id)
        notif = Notification.objects.filter(
            recipient=self.employee_user, notification_type='DOCUMENT_RELEASED').first()
        self.assertEqual(notif.related_offboarding_id, self.rid)
