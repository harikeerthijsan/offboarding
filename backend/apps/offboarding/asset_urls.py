from django.urls import path
from . import clearance_views

urlpatterns = [
    path('', clearance_views.AssetListCreateView.as_view(), name='asset-list-create'),
    path('<int:pk>/', clearance_views.AssetDetailView.as_view(), name='asset-detail'),
]
