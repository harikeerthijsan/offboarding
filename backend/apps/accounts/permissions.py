from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Allow access only to users with the ADMIN role."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'ADMIN'


class IsHR(BasePermission):
    """Allow access to HR and ADMIN roles."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('HR', 'ADMIN')


class IsManager(BasePermission):
    """Allow access to MANAGER, HR, and ADMIN roles."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('MANAGER', 'HR', 'ADMIN')
