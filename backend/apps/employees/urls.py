from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, DesignationViewSet, EmployeeViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('', include(router.urls)),
]
