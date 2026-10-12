import time

import jwt
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsAdmin
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    TokenSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class LoginView(APIView):
    """POST /api/auth/login/ - Authenticate user and return JWT tokens."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /api/auth/logout/ - Logout the authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """GET /api/auth/me/ - Return the currently authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ - Change the authenticated user's password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    """POST /api/auth/register/ - Create a new user (admin only)."""
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


# ─── SSO to JSAN Skills Hub ──────────────────────────────────────────────────

# OffBoarding role (6) → Skills Hub role (3).
SKILLHUB_ROLE_MAP = {
    'ADMIN': 'superadmin',
    'HR': 'manager',
    'MANAGER': 'manager',
    'EMPLOYEE': 'employee',
    'IT': 'employee',
    'FINANCE': 'employee',
}


class SkillHubSSOView(APIView):
    """GET /api/auth/sso/skillhub/ — mint a short-lived handoff token the Skills
    Hub can exchange for its own session. The browser then redirects to
    SKILLHUB_SSO_URL?token=<jwt>. The token is signed with SSO_SHARED_SECRET
    (shared only between the two servers) and carries the JSAN ID — the common
    identity key — never OffBoarding's own JWT."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        secret = getattr(settings, 'SSO_SHARED_SECRET', '')
        target = getattr(settings, 'SKILLHUB_SSO_URL', '')
        if not secret or not target:
            return Response(
                {'detail': 'Skills Hub SSO is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        user = request.user
        jsan_id = (user.email or user.username or '').split('@')[0].strip().lower()
        if not jsan_id:
            return Response({'detail': 'No JSAN ID available for this account.'},
                            status=status.HTTP_400_BAD_REQUEST)

        now = int(time.time())
        payload = {
            'jsanId': jsan_id,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'email': user.email or '',
            'role': SKILLHUB_ROLE_MAP.get(user.role, 'employee'),
            'iss': 'offboarding',
            'aud': 'skillhub',
            'iat': now,
            'exp': now + 60,  # 60-second single-use handoff window
        }
        token = jwt.encode(payload, secret, algorithm='HS256')
        return Response({
            'token': token,
            'redirect_url': f"{target}?token={token}",
        })
