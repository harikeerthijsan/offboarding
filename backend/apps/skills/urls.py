from django.urls import path
from . import views

urlpatterns = [
    path('me/', views.MySkillsView.as_view(), name='skills-me'),
    path('submissions/', views.MySubmissionsView.as_view(), name='skills-submissions'),
    path('submissions/all/', views.StaffSubmissionsView.as_view(), name='skills-submissions-all'),
    path('submissions/<int:pk>/review/', views.SubmissionReviewView.as_view(), name='skills-submission-review'),
    path('approvals/', views.ApprovalsView.as_view(), name='skills-approvals'),
    path('picker/', views.SkillsPickerView.as_view(), name='skills-picker'),
    path('cycles/', views.CyclesView.as_view(), name='skills-cycles'),
    path('cycles/import/', views.CalendarImportView.as_view(), name='skills-cycles-import'),
    path('cycles/<int:pk>/', views.CycleDetailView.as_view(), name='skills-cycle-detail'),
    path('catalogue/', views.CatalogueView.as_view(), name='skills-catalogue'),
    path('catalogue/<int:pk>/', views.CatalogueDetailView.as_view(), name='skills-catalogue-detail'),
    path('team/', views.TeamView.as_view(), name='skills-team'),
    path('export/', views.ExportView.as_view(), name='skills-export'),
]
