from django.contrib import admin
from .models import SkillDefinition, ReviewCycle, SkillSubmission


@admin.register(SkillDefinition)
class SkillDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'active', 'updated_at']
    list_filter = ['active']
    search_fields = ['name']


@admin.register(ReviewCycle)
class ReviewCycleAdmin(admin.ModelAdmin):
    list_display = ['cycle_id', 'period_start', 'period_end', 'employee_due', 'closure_target']
    search_fields = ['cycle_id']


@admin.register(SkillSubmission)
class SkillSubmissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'cycle', 'status', 'submitted_at', 'updated_at']
    list_filter = ['status', 'cycle']
    search_fields = ['user__email', 'user__username']
