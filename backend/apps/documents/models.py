from django.conf import settings
from django.db import models, transaction


DOCUMENT_TYPE = [
    ('RELIEVING_LETTER', 'Relieving Letter'),
    ('EXPERIENCE_LETTER', 'Experience Letter'),
    ('FULL_FINAL_SETTLEMENT', 'Full & Final Settlement'),
    ('EXIT_CLEARANCE', 'Exit Clearance Certificate'),
    ('OTHER', 'Other'),
]

# Short prefixes for document numbering (extensible).
DOCUMENT_TYPE_PREFIX = {
    'RELIEVING_LETTER': 'REL',
    'EXPERIENCE_LETTER': 'EXP',
    'FULL_FINAL_SETTLEMENT': 'FNF',
    'EXIT_CLEARANCE': 'CLR',
    'OTHER': 'DOC',
}

# Documents that contain confidential financial information.
FINANCIAL_DOCUMENT_TYPES = {'FULL_FINAL_SETTLEMENT'}

DOCUMENT_STATUS = [
    ('DRAFT', 'Draft'),
    ('GENERATED', 'Generated'),
    ('UNDER_REVIEW', 'Under Review'),
    ('APPROVED', 'Approved'),
    ('RELEASED', 'Released'),
    ('REVOKED', 'Revoked'),
]

# Enforced backend-side; clients never set status directly.
DOCUMENT_TRANSITIONS = {
    'DRAFT': ['GENERATED'],
    'GENERATED': ['UNDER_REVIEW', 'APPROVED'],
    'UNDER_REVIEW': ['APPROVED', 'REJECTED'],
    'APPROVED': ['RELEASED'],
    'RELEASED': ['REVOKED'],
    'REJECTED': [],
    'REVOKED': [],
}
# 'REJECTED' isn't a stored status value in DOCUMENT_STATUS choices intentionally;
# rejection is represented by returning to GENERATED with a rejection_reason, and a
# fresh version is produced on regenerate. We keep the transition table simple.


def document_upload_path(instance, filename):
    # Stored under MEDIA_ROOT but never served via a public URL — access is only
    # through the permission-checked download endpoint.
    return f"exit_documents/{instance.offboarding_request_id}/{instance.document_type}_v{instance.version}_{filename}"


class CompanyProfile(models.Model):
    """Singleton-style company profile used to render documents."""
    name = models.CharField(max_length=200, default='Company')
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    logo = models.ImageField(upload_to='company/', null=True, blank=True)
    signatory_name = models.CharField(max_length=150, blank=True)
    signatory_designation = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents_companyprofile'

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class DocumentCounter(models.Model):
    """Backend-safe monotonic counter per numbering scope (prevents duplicates)."""
    scope = models.CharField(max_length=100, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'documents_documentcounter'

    @classmethod
    def next_value(cls, scope):
        with transaction.atomic():
            counter = cls.objects.select_for_update().filter(scope=scope).first()
            if counter is None:
                cls.objects.create(scope=scope, last_value=0)
                counter = cls.objects.select_for_update().get(scope=scope)
            counter.last_value += 1
            counter.save(update_fields=['last_value'])
            return counter.last_value


class OffboardingDocument(models.Model):
    offboarding_request = models.ForeignKey(
        'offboarding.ResignationRequest',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='exit_documents',
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE)
    document_number = models.CharField(max_length=60, unique=True)
    document_title = models.CharField(max_length=200)
    file = models.FileField(upload_to=document_upload_path, null=True, blank=True)
    status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='GENERATED')
    version = models.PositiveIntegerField(default=1)
    document_date = models.DateField(null=True, blank=True)  # manual only

    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prepared_documents',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_documents',
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='released_documents',
    )
    rejection_reason = models.TextField(blank=True)
    revocation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents_offboardingdocument'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.document_number} ({self.status})"

    @property
    def is_financial(self):
        return self.document_type in FINANCIAL_DOCUMENT_TYPES

    def can_transition_to(self, new_status):
        return new_status in DOCUMENT_TRANSITIONS.get(self.status, [])
