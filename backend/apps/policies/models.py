from django.conf import settings
from django.db import models


POLICY_CATEGORY = [
    ('HR', 'HR'),
    ('IT', 'IT'),
    ('FINANCE', 'Finance'),
    ('SECURITY', 'Security'),
    ('CODE_OF_CONDUCT', 'Code of Conduct'),
    ('LEAVE', 'Leave & Attendance'),
    ('OTHER', 'Other'),
]


def policy_upload_path(instance, filename):
    # Stored under MEDIA_ROOT; served only through the authenticated download endpoint.
    return f"policies/{filename}"


class Policy(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=POLICY_CATEGORY, default='OTHER')
    file = models.FileField(upload_to=policy_upload_path)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'policies_policy'
        ordering = ['-created_at']
        verbose_name_plural = 'policies'

    def __str__(self):
        return self.title
