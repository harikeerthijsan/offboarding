from django.contrib import admin
from .models import Policy


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_active', 'uploaded_by', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['title', 'description']
