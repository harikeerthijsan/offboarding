from django.urls import path
from . import views

urlpatterns = [
    path('', views.PolicyListCreateView.as_view(), name='policy-list-create'),
    path('<int:pk>/', views.PolicyDetailView.as_view(), name='policy-detail'),
    path('<int:pk>/download/', views.PolicyDownloadView.as_view(), name='policy-download'),
]
