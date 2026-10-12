import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.policies.models import Policy

# Isolate uploaded files in a throwaway dir so tests never touch real media/.
_TMP_MEDIA = tempfile.mkdtemp(prefix='policy_test_media_')


def auth(client, user):
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


def pdf(name='policy.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test content', content_type='application/pdf')


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class PolicySetup(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(email='hr@test.com', username='hr', password='p', role='HR')
        self.admin = User.objects.create_user(email='admin@test.com', username='admin', password='p', role='ADMIN')
        self.emp = User.objects.create_user(email='emp@test.com', username='emp', password='p', role='EMPLOYEE')
        self.url = '/api/policies/'

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Best-effort: Windows may hold a brief lock from FileResponse handles.
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)


class PolicyUploadTest(PolicySetup):
    def test_hr_can_upload(self):
        auth(self.client, self.hr)
        r = self.client.post(self.url, {'title': 'Leave Policy', 'category': 'LEAVE', 'file': pdf()}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['title'], 'Leave Policy')
        self.assertTrue(Policy.objects.get(pk=r.data['id']).is_active)  # active by default

    def test_employee_cannot_upload(self):
        auth(self.client, self.emp)
        r = self.client.post(self.url, {'title': 'x', 'file': pdf()}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_bad_file_type_rejected(self):
        auth(self.client, self.hr)
        bad = SimpleUploadedFile('note.txt', b'hi', content_type='text/plain')
        r = self.client.post(self.url, {'title': 'x', 'file': bad}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', r.data)

    def test_unauthenticated_denied(self):
        r = self.client.post(self.url, {'title': 'x', 'file': pdf()}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class PolicyViewTest(PolicySetup):
    def _upload(self):
        auth(self.client, self.hr)
        return self.client.post(self.url, {'title': 'Code of Conduct', 'category': 'CODE_OF_CONDUCT', 'file': pdf()}, format='multipart').data['id']

    def test_employee_sees_and_downloads_active_policy(self):
        pid = self._upload()
        auth(self.client, self.emp)
        lst = self.client.get(self.url)
        self.assertEqual(lst.status_code, status.HTTP_200_OK)
        self.assertEqual(len(lst.data), 1)
        dl = self.client.get(f'{self.url}{pid}/download/')
        self.assertEqual(dl.status_code, status.HTTP_200_OK)

    def test_archived_policy_hidden_from_employee_visible_to_hr(self):
        pid = self._upload()
        auth(self.client, self.hr)
        self.client.patch(f'{self.url}{pid}/', {'is_active': False}, format='json')
        auth(self.client, self.emp)
        self.assertEqual(len(self.client.get(self.url).data), 0)
        self.assertEqual(self.client.get(f'{self.url}{pid}/download/').status_code, status.HTTP_404_NOT_FOUND)
        auth(self.client, self.hr)
        self.assertEqual(len(self.client.get(self.url).data), 1)

    def test_admin_can_delete(self):
        pid = self._upload()
        auth(self.client, self.admin)
        r = self.client.delete(f'{self.url}{pid}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Policy.objects.filter(pk=pid).exists())

    def test_employee_cannot_delete(self):
        pid = self._upload()
        auth(self.client, self.emp)
        r = self.client.delete(f'{self.url}{pid}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
