from django.urls import path
from . import views
from . import kt_views
from . import clearance_views
from . import settlement_views
from . import final_review_views
from . import dashboard_views
from apps.documents.views import DocumentListCreateView

urlpatterns = [
    path('', views.ResignationListCreateView.as_view(), name='resignation-list-create'),
    path('<int:pk>/', views.ResignationDetailView.as_view(), name='resignation-detail'),
    path('<int:pk>/submit/', views.SubmitResignationView.as_view(), name='resignation-submit'),
    path('<int:pk>/manager-action/', views.ManagerActionView.as_view(), name='resignation-manager-action'),
    path('<int:pk>/hr-action/', views.HRActionView.as_view(), name='resignation-hr-action'),
    path('<int:pk>/cancel/', views.CancelResignationView.as_view(), name='resignation-cancel'),
    path('<int:pk>/notice-period/', views.NoticePeriodView.as_view(), name='notice-period'),
    path('<int:pk>/notice-period/complete/', views.CompleteNoticePeriodView.as_view(), name='notice-period-complete'),
    path('<int:pk>/early-release/', views.EarlyReleaseView.as_view(), name='early-release'),
    path('<int:pk>/notice-extension/', views.NoticeExtensionView.as_view(), name='notice-extension'),
    # Phase 5 — Knowledge Transfer (per offboarding)
    path('<int:pk>/kt/', kt_views.KTListCreateView.as_view(), name='kt-list-create'),
    path('<int:pk>/kt/summary/', kt_views.KTSummaryView.as_view(), name='kt-summary'),
    path('<int:pk>/kt/complete/', kt_views.KTPhaseCompleteView.as_view(), name='kt-phase-complete'),
    # Phase 6 — Asset & Department Clearance (per offboarding)
    path('<int:pk>/assets/', clearance_views.AssetClearanceListCreateView.as_view(), name='asset-clearance-list'),
    path('<int:pk>/clearances/', clearance_views.DepartmentClearanceListCreateView.as_view(), name='dept-clearance-list'),
    path('<int:pk>/clearance/summary/', clearance_views.ClearanceSummaryView.as_view(), name='clearance-summary'),
    path('<int:pk>/clearance/complete/', clearance_views.ClearanceCompleteView.as_view(), name='clearance-complete'),
    # Phase 7 — Final Settlement (per offboarding)
    path('<int:pk>/settlement/', settlement_views.SettlementView.as_view(), name='settlement'),
    path('<int:pk>/settlement/submit/', settlement_views.SettlementSubmitView.as_view(), name='settlement-submit'),
    path('<int:pk>/settlement/approve/', settlement_views.SettlementApproveView.as_view(), name='settlement-approve'),
    path('<int:pk>/settlement/reject/', settlement_views.SettlementRejectView.as_view(), name='settlement-reject'),
    # Phase 7 — Exit Interview (per offboarding)
    path('<int:pk>/exit-interview/', settlement_views.ExitInterviewView.as_view(), name='exit-interview'),
    path('<int:pk>/exit-interview/submit/', settlement_views.ExitInterviewSubmitView.as_view(), name='exit-interview-submit'),
    path('<int:pk>/exit-interview/review/', settlement_views.ExitInterviewReviewView.as_view(), name='exit-interview-review'),
    # Phase 8 — HR Dashboard & Final Review
    path('dashboard/', final_review_views.HRDashboardView.as_view(), name='hr-dashboard'),
    path('dashboard/overview/', dashboard_views.DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('dashboard/list/', final_review_views.HROffboardingListView.as_view(), name='hr-dashboard-list'),
    path('<int:pk>/summary/', final_review_views.OffboardingSummaryView.as_view(), name='offboarding-summary'),
    path('<int:pk>/final-review/start/', final_review_views.FinalReviewStartView.as_view(), name='final-review-start'),
    path('<int:pk>/final-review/approve/', final_review_views.FinalReviewApproveView.as_view(), name='final-review-approve'),
    path('<int:pk>/final-review/reject/', final_review_views.FinalReviewRejectView.as_view(), name='final-review-reject'),
    # Phase 9 — Exit documents (per offboarding)
    path('<int:pk>/documents/', DocumentListCreateView.as_view(), name='offboarding-documents'),
]
