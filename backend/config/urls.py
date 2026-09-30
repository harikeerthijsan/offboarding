from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from apps.offboarding.clearance_views import EmployeeAssetsView
from apps.offboarding.settlement_views import ExitInterviewAnalyticsView
from .health import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Phase 6: employee assets (registered before employees include is fine — distinct path)
    path('api/employees/<int:pk>/assets/', EmployeeAssetsView.as_view(), name='employee-assets'),
    path('api/employees/', include('apps.employees.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/offboarding/', include('apps.offboarding.urls')),
    path('api/kt/', include('apps.offboarding.kt_urls')),
    path('api/projects/', include('apps.offboarding.project_urls')),
    path('api/assets/', include('apps.offboarding.asset_urls')),
    path('api/', include('apps.offboarding.clearance_urls')),
    path('api/exit-interviews/analytics/', ExitInterviewAnalyticsView.as_view(), name='exit-interview-analytics'),
    path('api/', include('apps.documents.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
]
