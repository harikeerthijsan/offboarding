from django.urls import path
from . import views

urlpatterns = [
    path('me/', views.MySkillsView.as_view(), name='skills-me'),
    path('submissions/', views.MySubmissionsView.as_view(), name='skills-submissions'),
    path('picker/', views.SkillsPickerView.as_view(), name='skills-picker'),
    path('cycles/', views.CyclesView.as_view(), name='skills-cycles'),
    path('catalogue/', views.CatalogueView.as_view(), name='skills-catalogue'),
    path('catalogue/<int:pk>/', views.CatalogueDetailView.as_view(), name='skills-catalogue-detail'),
    path('team/', views.TeamView.as_view(), name='skills-team'),
]
