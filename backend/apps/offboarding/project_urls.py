from django.urls import path
from . import kt_views

urlpatterns = [
    path('', kt_views.ProjectListCreateView.as_view(), name='project-list-create'),
    path('<int:pk>/', kt_views.ProjectDetailView.as_view(), name='project-detail'),
]
