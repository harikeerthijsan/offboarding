from django.urls import path
from . import clearance_views

# Included at /api/ — these are the flat clearance resource routes.
urlpatterns = [
    path('clearances/queue/', clearance_views.MyClearanceQueueView.as_view(), name='clearance-queue'),
    path('asset-clearance/<int:pk>/', clearance_views.AssetClearanceDetailView.as_view(), name='asset-clearance-detail'),
    path('clearances/<int:pk>/', clearance_views.DepartmentClearanceDetailView.as_view(), name='dept-clearance-detail'),
    path('clearances/<int:pk>/checklist/', clearance_views.ChecklistListCreateView.as_view(), name='checklist-list-create'),
    path('checklist/<int:pk>/', clearance_views.ChecklistItemDetailView.as_view(), name='checklist-item-detail'),
]
