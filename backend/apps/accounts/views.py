from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsAdmin
from .serializers import LoginSerializer, TokenSerializer, UserCreateSerializer, UserSerializer


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


class RegisterView(APIView):
    """POST /api/auth/register/ - Create a new user (admin only)."""
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
