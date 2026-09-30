from django.urls import path
from . import views

# Flat document + company routes (included at /api/).
urlpatterns = [
    path('company-profile/', views.CompanyProfileView.as_view(), name='company-profile'),
    path('documents/<int:pk>/', views.DocumentDetailView.as_view(), name='document-detail'),
    path('documents/<int:pk>/action/', views.DocumentActionView.as_view(), name='document-action'),
    path('documents/<int:pk>/download/', views.DocumentDownloadView.as_view(), name='document-download'),
]
