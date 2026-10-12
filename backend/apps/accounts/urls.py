from django.urls import path
from .views import (
    ChangePasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RegisterView,
    SkillHubSSOView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('register/', RegisterView.as_view(), name='register'),
    path('sso/skillhub/', SkillHubSSOView.as_view(), name='sso-skillhub'),
]
