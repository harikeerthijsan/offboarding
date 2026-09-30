from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User


class UserModelTest(APITestCase):
    """Test User model creation and role assignment."""

    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User',
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'EMPLOYEE')
        self.assertTrue(user.check_password('testpass123'))

    def test_role_assignment(self):
        user = User.objects.create_user(
            email='hr@example.com',
            username='hruser',
            password='testpass123',
            role='HR',
        )
        self.assertEqual(user.role, 'HR')

    def test_email_is_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')


class LoginViewTest(APITestCase):
    """Test login endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com',
            username='loginuser',
            password='testpass123',
            first_name='Login',
            last_name='User',
        )
        self.login_url = reverse('login')

    def test_login_valid_credentials(self):
        data = {'email': 'login@example.com', 'password': 'testpass123'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_login_invalid_credentials(self):
        data = {'email': 'login@example.com', 'password': 'wrongpassword'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        data = {'email': 'nobody@example.com', 'password': 'testpass123'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CurrentUserViewTest(APITestCase):
    """Test /api/auth/me/ endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='me@example.com',
            username='meuser',
            password='testpass123',
            first_name='Me',
            last_name='User',
        )
        self.me_url = reverse('current-user')

    def _get_token(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        return str(refresh.access_token)

    def test_authenticated_access(self):
        token = self._get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'me@example.com')

    def test_unauthenticated_access_returns_401(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RegisterViewTest(APITestCase):
    """Test /api/auth/register/ endpoint (admin only)."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            username='adminuser',
            password='testpass123',
            role='ADMIN',
        )
        self.regular_user = User.objects.create_user(
            email='regular@example.com',
            username='regularuser',
            password='testpass123',
            role='EMPLOYEE',
        )
        self.register_url = reverse('register')

    def _get_token(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    def test_admin_can_register_user(self):
        token = self._get_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'testpass123',
            'role': 'HR',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_admin_cannot_register_user(self):
        token = self._get_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        data = {
            'email': 'another@example.com',
            'username': 'anotheruser',
            'first_name': 'Another',
            'last_name': 'User',
            'password': 'testpass123',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
