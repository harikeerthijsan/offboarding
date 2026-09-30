from django.db import models
from django.conf import settings


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        # Legacy / generic (kept for backward compatibility)
        ('RESIGNATION_SUBMITTED', 'Resignation Submitted'),
        ('RESIGNATION_APPROVED', 'Resignation Approved'),
        ('RESIGNATION_REJECTED', 'Resignation Rejected'),
        ('RESIGNATION_CANCELLED', 'Resignation Cancelled'),
        ('ACTION_REQUIRED', 'Action Required'),
        ('STATUS_UPDATE', 'Status Update'),
        # Resignation
        ('MANAGER_APPROVAL_REQUIRED', 'Manager Approval Required'),
        ('HR_REVIEW_REQUIRED', 'HR Review Required'),
        # Notice period
        ('NOTICE_UPDATED', 'Notice Updated'),
        ('EARLY_RELEASE_REQUESTED', 'Early Release Requested'),
        ('EARLY_RELEASE_DECISION', 'Early Release Decision'),
        ('NOTICE_COMPLETED', 'Notice Completed'),
        # Knowledge transfer
        ('KT_ASSIGNED', 'KT Assigned'),
        ('KT_SUBMITTED', 'KT Submitted'),
        ('KT_CHANGES_REQUESTED', 'KT Changes Requested'),
        ('KT_APPROVED', 'KT Approved'),
        ('KT_COMPLETED', 'KT Completed'),
        # Clearance
        ('ASSET_RETURN_REQUIRED', 'Asset Return Required'),
        ('ASSET_RETURNED', 'Asset Returned'),
        ('ASSET_VERIFICATION_REQUIRED', 'Asset Verification Required'),
        ('CLEARANCE_ACTION_REQUIRED', 'Clearance Action Required'),
        ('CLEARANCE_COMPLETED', 'Clearance Completed'),
        # Settlement
        ('SETTLEMENT_PREPARED', 'Settlement Prepared'),
        ('SETTLEMENT_REVIEW_REQUIRED', 'Settlement Review Required'),
        ('SETTLEMENT_APPROVED', 'Settlement Approved'),
        ('SETTLEMENT_REJECTED', 'Settlement Rejected'),
        # Exit interview
        ('EXIT_INTERVIEW_REQUIRED', 'Exit Interview Required'),
        ('EXIT_INTERVIEW_SUBMITTED', 'Exit Interview Submitted'),
        ('EXIT_INTERVIEW_REVIEWED', 'Exit Interview Reviewed'),
        # Final approval
        ('FINAL_REVIEW_REQUIRED', 'Final Review Required'),
        ('FINAL_APPROVAL', 'Final Approval'),
        ('FINAL_REJECTION', 'Final Rejection'),
        # Documents
        ('DOCUMENT_GENERATED', 'Document Generated'),
        ('DOCUMENT_APPROVED', 'Document Approved'),
        ('DOCUMENT_RELEASED', 'Document Released'),
        ('DOCUMENT_REVOKED', 'Document Revoked'),
        # Reminders
        ('EXIT_REMINDER', 'Exit Reminder'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    # Phase 9: explicit link to the offboarding record for navigation.
    related_offboarding = models.ForeignKey(
        'offboarding.ResignationRequest',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} → {self.recipient}"
