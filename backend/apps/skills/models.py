"""Skills Hub — ported from the standalone jsan-skill-hub (Next.js + Mongo).

Employees keep a skill matrix and submit it each company-wide six-month review
cycle. There is no approval gate — a submitted set is on record immediately and
can be updated while its cycle is open. Staff (manager/HR/admin) view & export.

Reuses the existing accounts.User for identity (keyed by employee email / JSAN
ID); department & designation come from the linked employees.Employee profile.
"""
from django.conf import settings
from django.db import models


SKILL_STATUS = [
    ('current', 'Current'),
    ('learned', 'Newly learned'),
    ('in_progress', 'In progress'),
]

SKILL_CATEGORY = [
    ('Technical', 'Technical'),
    ('Domain', 'Domain'),
    ('Tools', 'Tools'),
    ('Soft skills', 'Soft skills'),
    ('Certification', 'Certification'),
    ('Other', 'Other'),
]

PROFICIENCY = [
    ('Beginner', 'Beginner'),
    ('Intermediate', 'Intermediate'),
    ('Advanced', 'Advanced'),
    ('Expert', 'Expert'),
]

SUBMISSION_STATUS = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Recorded'),
    ('rejected', 'Needs update'),
]


class SkillDefinition(models.Model):
    """Skill catalogue entry offered as a picker/filter. Switching `active` off
    hides it from pickers without touching history."""
    name = models.CharField(max_length=80, unique=True)
    tools = models.JSONField(default=list, blank=True)       # list[str]
    customers = models.JSONField(default=list, blank=True)   # list[str]
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skills_definition'
        ordering = ['name']

    def __str__(self):
        return self.name


class ReviewCycle(models.Model):
    """Company-wide six-month review cycle (JSAN/QF/09 calendar), e.g. 2027-H1."""
    cycle_id = models.CharField(max_length=40, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    employee_due = models.DateField()
    manager_due = models.DateField()
    closure_target = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skills_reviewcycle'
        ordering = ['period_start']

    def __str__(self):
        return self.cycle_id


class SkillSubmission(models.Model):
    """One employee's skill set for one cycle. Unique per (user, cycle).

    `skills` mirrors the embedded array from the source app: a list of objects
    { name, category, status, proficiency, tools[], years, company, role,
    customer, note }. Validation lives in the serializer."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_submissions',
    )
    cycle = models.ForeignKey(
        ReviewCycle,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    due_date = models.DateField(null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS, default='draft')
    employee_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_skill_submissions',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    source = models.CharField(max_length=10, default='portal')  # portal | import
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skills_submission'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'cycle'], name='uniq_user_cycle_submission'),
        ]

    def __str__(self):
        return f"{self.user_id} · {self.cycle.cycle_id} ({self.status})"
