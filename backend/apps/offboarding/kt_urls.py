from django.urls import path
from . import kt_views

urlpatterns = [
    path('mine/', kt_views.KTMineView.as_view(), name='kt-mine'),
    path('<int:pk>/', kt_views.KTDetailView.as_view(), name='kt-detail'),
    path('<int:pk>/start/', kt_views.KTStartView.as_view(), name='kt-start'),
    path('<int:pk>/submit/', kt_views.KTSubmitView.as_view(), name='kt-submit'),
    path('<int:pk>/receiver-action/', kt_views.KTReceiverActionView.as_view(), name='kt-receiver-action'),
    path('<int:pk>/manager-action/', kt_views.KTManagerActionView.as_view(), name='kt-manager-action'),
    path('<int:pk>/reassign/', kt_views.KTReassignView.as_view(), name='kt-reassign'),
    path('<int:pk>/documents/', kt_views.KTDocumentListCreateView.as_view(), name='kt-documents'),
    path('<int:pk>/documents/<int:doc_id>/', kt_views.KTDocumentDeleteView.as_view(), name='kt-document-delete'),
]
