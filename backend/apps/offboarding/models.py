import calendar
import datetime

from django.db import models
from django.conf import settings


RESIGNATION_STATUS = [
    ('DRAFT', 'Draft'),
    ('SUBMITTED', 'Submitted'),
    ('MANAGER_REVIEW', 'Manager Review'),
    ('HR_REVIEW', 'HR Review'),
    ('APPROVED', 'Approved'),
    ('NOTICE_PERIOD', 'Notice Period'),
    ('COMPLETED', 'Completed'),
    ('REJECTED', 'Rejected'),
    ('CANCELLED', 'Cancelled'),
]

RESIGNATION_REASON = [
    ('BETTER_OPPORTUNITY', 'Better Opportunity'),
    ('PERSONAL_REASONS', 'Personal Reasons'),
    ('HIGHER_EDUCATION', 'Higher Education'),
    ('RELOCATION', 'Relocation'),
    ('HEALTH_REASONS', 'Health Reasons'),
    ('FAMILY_COMMITMENT', 'Family Commitment'),
    ('CAREER_CHANGE', 'Career Change'),
    ('COMPENSATION', 'Compensation'),
    ('WORK_ENVIRONMENT', 'Work Environment'),
    ('OTHER', 'Other'),
]

# Terminal states — no further transitions allowed
TERMINAL_STATUSES = {'COMPLETED', 'REJECTED', 'CANCELLED'}

# Phase 8: Final HR review status (separate layer from the resignation status).
FINAL_REVIEW_STATUS = [
    ('NOT_READY', 'Not Ready'),
    ('READY_FOR_REVIEW', 'Ready for Review'),
    ('UNDER_REVIEW', 'Under Review'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]

FINAL_REVIEW_TRANSITIONS = {
    'NOT_READY': ['READY_FOR_REVIEW'],
    'READY_FOR_REVIEW': ['UNDER_REVIEW'],
    'UNDER_REVIEW': ['APPROVED', 'REJECTED'],
    'REJECTED': ['READY_FOR_REVIEW', 'UNDER_REVIEW'],
    'APPROVED': [],
}

# Valid status transitions (from → [allowed to])
VALID_TRANSITIONS = {
    'DRAFT': ['SUBMITTED', 'CANCELLED'],
    'SUBMITTED': ['MANAGER_REVIEW', 'REJECTED', 'CANCELLED'],
    'MANAGER_REVIEW': ['HR_REVIEW', 'REJECTED'],
    'HR_REVIEW': ['APPROVED', 'REJECTED'],
    'APPROVED': ['NOTICE_PERIOD'],
    'NOTICE_PERIOD': ['COMPLETED'],
    'COMPLETED': [],
    'REJECTED': [],
    'CANCELLED': [],
}


def add_months(d, months):
    """Add whole months to a date, clamping the day to the target month's length."""
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def notice_months(joining_date, on_date):
    """Notice period rule: 1 month for tenure under 6 months, else 2 months."""
    if not joining_date:
        return 2
    tenure_months = (on_date.year - joining_date.year) * 12 + (on_date.month - joining_date.month)
    if on_date.day < joining_date.day:
        tenure_months -= 1
    return 1 if tenure_months < 6 else 2


class ResignationRequest(models.Model):
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='resignation_requests',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_resignations',
    )
    status = models.CharField(max_length=20, choices=RESIGNATION_STATUS, default='DRAFT')
    reason = models.CharField(max_length=50, choices=RESIGNATION_REASON)
    resignation_date = models.DateField()
    last_working_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Manager review fields
    manager_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='manager_reviewed_resignations',
    )
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)
    manager_notes = models.TextField(blank=True)

    # HR review fields
    hr_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hr_reviewed_resignations',
    )
    hr_reviewed_at = models.DateTimeField(null=True, blank=True)
    hr_notes = models.TextField(blank=True)

    rejection_reason = models.TextField(blank=True)

    # Phase 5: Knowledge Transfer phase marker (does NOT change the resignation
    # status machine — offboarding is not auto-advanced when KT tasks complete).
    kt_completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kt_phase_completed_resignations',
    )
    kt_completed_at = models.DateTimeField(null=True, blank=True)

    # Phase 6: Clearance phase marker (does NOT change the resignation status
    # machine — offboarding is not auto-advanced when clearances complete).
    clearance_completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clearance_phase_completed_resignations',
    )
    clearance_completed_at = models.DateTimeField(null=True, blank=True)

    # Phase 8: Final HR review & approval. This is a distinct review layer on top
    # of the resignation status machine — it never auto-marks the employee EXITED
    # (that is a later phase). Both dates are manually entered.
    final_review_status = models.CharField(
        max_length=20, choices=FINAL_REVIEW_STATUS, default='NOT_READY',
    )
    final_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='final_reviewed_resignations',
    )
    final_review_date = models.DateField(null=True, blank=True)     # manual only
    final_approval_date = models.DateField(null=True, blank=True)   # manual only
    final_review_comments = models.TextField(blank=True)
    final_rejection_reason = models.TextField(blank=True)

    # Set once the "1 week before last working day" reminder has been sent (dedup).
    exit_reminder_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_resignationrequest'
        ordering = ['-created_at']

    def __str__(self):
        return f"Resignation #{self.pk} - {self.employee} ({self.status})"

    def can_transition_to(self, new_status):
        return new_status in VALID_TRANSITIONS.get(self.status, [])

    def can_final_transition_to(self, new_status):
        return new_status in FINAL_REVIEW_TRANSITIONS.get(self.final_review_status, [])


class NoticePeriod(models.Model):
    NOTICE_STATUS = [
        ('ACTIVE', 'Active'),
        ('EARLY_RELEASE_REQUESTED', 'Early Release Requested'),
        ('COMPLETED', 'Completed'),
    ]

    resignation = models.OneToOneField(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='notice_period',
    )
    status = models.CharField(max_length=30, choices=NOTICE_STATUS, default='ACTIVE')

    # Core fields — null at the model level; never auto-saved. The HR form only
    # pre-fills suggestions (resignation date / policy-derived end date) for review.
    notice_period_start_date = models.DateField(null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    expected_last_working_day = models.DateField(null=True, blank=True)
    actual_last_working_day = models.DateField(null=True, blank=True)
    notice_comments = models.TextField(blank=True)

    # Early release tracking
    early_release_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='early_release_requests',
    )
    early_release_requested_at = models.DateTimeField(null=True, blank=True)
    early_release_request_reason = models.TextField(blank=True)
    early_release_date = models.DateField(null=True, blank=True)
    early_release_approved = models.BooleanField(null=True, blank=True)
    early_release_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='early_release_reviews',
    )
    early_release_reviewed_at = models.DateTimeField(null=True, blank=True)
    early_release_review_notes = models.TextField(blank=True)

    # Extension tracking
    notice_extension_date = models.DateField(null=True, blank=True)
    extension_reason = models.TextField(blank=True)
    extension_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_extensions',
    )
    extension_recorded_at = models.DateTimeField(null=True, blank=True)

    # Completion tracking
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_notice_periods',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_notice_periods',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_noticeperiod'

    def __str__(self):
        return f"Notice Period #{self.pk} - {self.resignation}"


# ─── Phase 5: Knowledge Transfer ─────────────────────────────────────────────

KT_PRIORITY = [
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('CRITICAL', 'Critical'),
]

KT_STATUS = [
    ('PENDING', 'Pending'),
    ('IN_PROGRESS', 'In Progress'),
    ('SUBMITTED', 'Submitted'),
    ('RECEIVER_REVIEW', 'Receiver Review'),
    ('MANAGER_REVIEW', 'Manager Review'),
    ('COMPLETED', 'Completed'),
    ('REJECTED', 'Rejected'),
]

# Terminal KT state — no further transitions
KT_TERMINAL_STATUSES = {'COMPLETED'}

# Valid KT status transitions (from → [allowed to]). Enforced on the backend;
# clients can never set status directly through the update API.
KT_VALID_TRANSITIONS = {
    'PENDING': ['IN_PROGRESS'],
    'IN_PROGRESS': ['SUBMITTED'],
    'SUBMITTED': ['RECEIVER_REVIEW', 'MANAGER_REVIEW', 'REJECTED'],
    'RECEIVER_REVIEW': ['MANAGER_REVIEW', 'REJECTED'],
    'MANAGER_REVIEW': ['COMPLETED', 'REJECTED'],
    'REJECTED': ['IN_PROGRESS'],
    'COMPLETED': [],
}


class Project(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        'employees.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projects',
    )
    manager = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_projects',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_project'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class KnowledgeTransfer(models.Model):
    offboarding_request = models.ForeignKey(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='kt_items',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kt_items',
    )
    responsibility = models.TextField(blank=True)

    # assigned_to is the offboarding employee (handing over). Derived server-side.
    assigned_to = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='kt_assigned',
    )
    # receiver takes over the responsibility.
    receiver = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='kt_receiving',
    )

    priority = models.CharField(max_length=10, choices=KT_PRIORITY, default='MEDIUM')
    status = models.CharField(max_length=20, choices=KT_STATUS, default='PENDING')

    # Business dates — ALL manually entered, never auto-populated/calculated.
    start_date = models.DateField(null=True, blank=True)
    target_completion_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)

    completion_notes = models.TextField(blank=True)
    receiver_comments = models.TextField(blank=True)
    manager_comments = models.TextField(blank=True)

    # Workflow tracking (system timestamps — record-keeping, not business dates)
    submitted_at = models.DateTimeField(null=True, blank=True)
    receiver_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kt_receiver_reviews',
    )
    receiver_reviewed_at = models.DateTimeField(null=True, blank=True)
    manager_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kt_manager_reviews',
    )
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kt_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_knowledgetransfer'
        ordering = ['-created_at']

    def __str__(self):
        return f"KT #{self.pk} - {self.title} ({self.status})"

    def can_transition_to(self, new_status):
        return new_status in KT_VALID_TRANSITIONS.get(self.status, [])


class KTDocument(models.Model):
    knowledge_transfer = models.ForeignKey(
        KnowledgeTransfer,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    url = models.URLField(max_length=500)
    description = models.CharField(max_length=300, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kt_documents_added',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'offboarding_ktdocument'
        ordering = ['created_at']

    def __str__(self):
        return f"KTDoc #{self.pk} - {self.url}"


# ─── Phase 6: Asset & Department Clearance ───────────────────────────────────

ASSET_TYPE = [
    ('LAPTOP', 'Laptop'),
    ('DESKTOP', 'Desktop'),
    ('MONITOR', 'Monitor'),
    ('MOBILE', 'Mobile'),
    ('TABLET', 'Tablet'),
    ('KEYBOARD', 'Keyboard'),
    ('MOUSE', 'Mouse'),
    ('HEADSET', 'Headset'),
    ('ID_CARD', 'ID Card'),
    ('ACCESS_CARD', 'Access Card'),
    ('SIM_CARD', 'SIM Card'),
    ('OTHER', 'Other'),
]

ASSET_STATUS = [
    ('ASSIGNED', 'Assigned'),
    ('RETURN_PENDING', 'Return Pending'),
    ('RETURNED', 'Returned'),
    ('LOST', 'Lost'),
    ('DAMAGED', 'Damaged'),
    ('CLEARED', 'Cleared'),
]

ASSET_CONDITION = [
    ('GOOD', 'Good'),
    ('FAIR', 'Fair'),
    ('DAMAGED', 'Damaged'),
    ('NON_FUNCTIONAL', 'Non Functional'),
]

# AssetClearance status — per-offboarding return lifecycle
ASSET_CLEARANCE_STATUS = [
    ('RETURN_PENDING', 'Return Pending'),
    ('RETURNED', 'Returned'),
    ('CLEARED', 'Cleared'),
    ('DAMAGED', 'Damaged'),
    ('LOST', 'Lost'),
    ('REJECTED', 'Rejected'),
]

ASSET_CLEARANCE_TRANSITIONS = {
    'RETURN_PENDING': ['RETURNED', 'LOST'],
    'RETURNED': ['CLEARED', 'DAMAGED', 'REJECTED'],
    'REJECTED': ['RETURNED'],
    'DAMAGED': ['CLEARED'],
    'LOST': [],
    'CLEARED': [],
}
ASSET_CLEARANCE_FINAL = {'CLEARED', 'LOST', 'DAMAGED'}

# Clearance departments — extensible; add entries here to support more without
# rewriting the workflow.
CLEARANCE_DEPARTMENTS = [
    ('IT', 'IT'),
    ('ADMIN', 'Admin'),
    ('FINANCE', 'Finance'),
    ('HR', 'HR'),
    ('MANAGER', 'Manager'),
]

# Roles authorised to act on each clearance department (ADMIN always allowed;
# MANAGER department additionally requires being the employee's direct manager,
# enforced in the view).
CLEARANCE_DEPARTMENT_ROLES = {
    'IT': {'IT', 'ADMIN'},
    'ADMIN': {'ADMIN'},
    'FINANCE': {'FINANCE', 'HR', 'ADMIN'},
    'HR': {'HR', 'ADMIN'},
    'MANAGER': {'MANAGER', 'ADMIN'},
}

DEPARTMENT_CLEARANCE_STATUS = [
    ('PENDING', 'Pending'),
    ('IN_PROGRESS', 'In Progress'),
    ('CLEARED', 'Cleared'),
    ('REJECTED', 'Rejected'),
    ('NOT_APPLICABLE', 'Not Applicable'),
]

CHECKLIST_STATUS = [
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('NOT_APPLICABLE', 'Not Applicable'),
]


class Asset(models.Model):
    asset_id = models.CharField(max_length=40, unique=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE)
    asset_name = models.CharField(max_length=150)
    serial_number = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assets',
    )
    assigned_date = models.DateField(null=True, blank=True)  # manual only
    status = models.CharField(max_length=20, choices=ASSET_STATUS, default='ASSIGNED')
    condition = models.CharField(max_length=20, choices=ASSET_CONDITION, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_asset'
        ordering = ['asset_id']

    def __str__(self):
        return f"{self.asset_id} - {self.asset_name}"


class AssetClearance(models.Model):
    offboarding_request = models.ForeignKey(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='asset_clearances',
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name='clearances',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='asset_clearances',
    )
    status = models.CharField(max_length=20, choices=ASSET_CLEARANCE_STATUS, default='RETURN_PENDING')
    return_date = models.DateField(null=True, blank=True)  # manual only
    condition_at_return = models.CharField(max_length=20, choices=ASSET_CONDITION, blank=True)
    remarks = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_asset_clearances',
    )
    verified_at = models.DateTimeField(null=True, blank=True)  # system action stamp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_assetclearance'
        ordering = ['-created_at']
        unique_together = [['offboarding_request', 'asset']]

    def __str__(self):
        return f"AssetClearance #{self.pk} - {self.asset} ({self.status})"

    def can_transition_to(self, new_status):
        return new_status in ASSET_CLEARANCE_TRANSITIONS.get(self.status, [])


class DepartmentClearance(models.Model):
    offboarding_request = models.ForeignKey(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='department_clearances',
    )
    department = models.CharField(max_length=20, choices=CLEARANCE_DEPARTMENTS)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_clearances',
    )
    status = models.CharField(max_length=20, choices=DEPARTMENT_CLEARANCE_STATUS, default='PENDING')
    comments = models.TextField(blank=True)
    clearance_date = models.DateField(null=True, blank=True)  # manual only
    cleared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cleared_department_clearances',
    )
    cleared_at = models.DateTimeField(null=True, blank=True)  # system action stamp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_departmentclearance'
        ordering = ['department']
        unique_together = [['offboarding_request', 'department']]

    def __str__(self):
        return f"DeptClearance #{self.pk} - {self.department} ({self.status})"


class ClearanceChecklistItem(models.Model):
    department_clearance = models.ForeignKey(
        DepartmentClearance,
        on_delete=models.CASCADE,
        related_name='checklist_items',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=CHECKLIST_STATUS, default='PENDING')
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_checklist_items',
    )
    completed_at = models.DateTimeField(null=True, blank=True)  # system action stamp
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'offboarding_clearancechecklistitem'
        ordering = ['id']

    def __str__(self):
        return f"ChecklistItem #{self.pk} - {self.title} ({self.status})"


# ─── Phase 7: Final Settlement & Exit Interview ──────────────────────────────

SETTLEMENT_STATUS = [
    ('DRAFT', 'Draft'),
    ('PREPARED', 'Prepared'),
    ('UNDER_REVIEW', 'Under Review'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]

# Valid settlement transitions — enforced backend-side; status never set directly.
SETTLEMENT_TRANSITIONS = {
    'DRAFT': ['PREPARED'],
    'PREPARED': ['UNDER_REVIEW'],
    'UNDER_REVIEW': ['APPROVED', 'REJECTED'],
    'REJECTED': ['DRAFT'],
    'APPROVED': [],
}
SETTLEMENT_TERMINAL = {'APPROVED'}

# Money fields that make up the totals (centralised so totals stay consistent).
SETTLEMENT_ADDITION_FIELDS = [
    'pending_salary', 'leave_encashment', 'bonus', 'incentives', 'other_additions',
]
SETTLEMENT_DEDUCTION_FIELDS = [
    'notice_recovery', 'loan_deduction', 'advance_deduction', 'other_deductions',
]


class FinalSettlement(models.Model):
    offboarding_request = models.OneToOneField(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='final_settlement',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='final_settlements',
    )

    # Additions (manually entered)
    pending_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leave_encashment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    incentives = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_additions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Deductions (manually entered)
    notice_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Totals (calculated & stored by the backend — source of truth)
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_settlement = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    settlement_status = models.CharField(max_length=20, choices=SETTLEMENT_STATUS, default='DRAFT')

    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prepared_settlements',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_settlements',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_settlements',
    )

    settlement_date = models.DateField(null=True, blank=True)  # manual only
    comments = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_finalsettlement'
        ordering = ['-created_at']

    def __str__(self):
        return f"Settlement #{self.pk} - {self.employee} ({self.settlement_status})"

    def can_transition_to(self, new_status):
        return new_status in SETTLEMENT_TRANSITIONS.get(self.settlement_status, [])

    def recompute_totals(self):
        """Backend is the source of truth for financial totals."""
        gross = sum(getattr(self, f) for f in SETTLEMENT_ADDITION_FIELDS)
        deductions = sum(getattr(self, f) for f in SETTLEMENT_DEDUCTION_FIELDS)
        self.gross_amount = gross
        self.total_deductions = deductions
        self.net_settlement = gross - deductions


EXIT_INTERVIEW_REASON = [
    ('CAREER_GROWTH', 'Career Growth'),
    ('NEW_OPPORTUNITY', 'New Opportunity'),
    ('HIGHER_STUDIES', 'Higher Studies'),
    ('PERSONAL_REASONS', 'Personal Reasons'),
    ('RELOCATION', 'Relocation'),
    ('COMPENSATION', 'Compensation'),
    ('WORK_ENVIRONMENT', 'Work Environment'),
    ('MANAGEMENT', 'Management'),
    ('ROLE_CHANGE', 'Role Change'),
    ('OTHER', 'Other'),
]

EXIT_INTERVIEW_STATUS = [
    ('NOT_STARTED', 'Not Started'),
    ('IN_PROGRESS', 'In Progress'),
    ('COMPLETED', 'Completed'),
    ('REVIEWED', 'Reviewed'),
]

EXIT_INTERVIEW_TRANSITIONS = {
    'NOT_STARTED': ['IN_PROGRESS'],
    'IN_PROGRESS': ['COMPLETED'],
    'COMPLETED': ['REVIEWED', 'IN_PROGRESS'],  # HR may reopen COMPLETED → IN_PROGRESS
    'REVIEWED': ['IN_PROGRESS'],               # HR may reopen a reviewed interview
}

# 1–5 rating scale used for feedback fields (0 = not answered)
EXIT_RATING = [(0, 'Not Answered'), (1, 'Very Poor'), (2, 'Poor'), (3, 'Average'),
               (4, 'Good'), (5, 'Excellent')]


class ExitInterview(models.Model):
    offboarding_request = models.OneToOneField(
        ResignationRequest,
        on_delete=models.CASCADE,
        related_name='exit_interview',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='exit_interviews',
    )

    interview_date = models.DateField(null=True, blank=True)  # manual only
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conducted_exit_interviews',
    )

    primary_reason = models.CharField(max_length=30, choices=EXIT_INTERVIEW_REASON, blank=True)
    secondary_reason = models.CharField(max_length=30, choices=EXIT_INTERVIEW_REASON, blank=True)

    # Feedback ratings (employee answers)
    overall_experience = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)
    manager_feedback = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)
    work_environment_feedback = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)
    role_feedback = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)
    growth_feedback = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)
    compensation_feedback = models.PositiveSmallIntegerField(choices=EXIT_RATING, default=0)

    # Open feedback (employee answers)
    what_went_well = models.TextField(blank=True)
    what_could_improve = models.TextField(blank=True)
    suggestions = models.TextField(blank=True)
    additional_comments = models.TextField(blank=True)

    would_recommend = models.BooleanField(null=True, blank=True)
    would_rejoin = models.BooleanField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=EXIT_INTERVIEW_STATUS, default='NOT_STARTED')

    # HR review — kept separate from employee answers
    hr_review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_exit_interviews',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)  # system action stamp
    submitted_at = models.DateTimeField(null=True, blank=True)  # system action stamp

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offboarding_exitinterview'
        ordering = ['-created_at']

    def __str__(self):
        return f"ExitInterview #{self.pk} - {self.employee} ({self.status})"

    def can_transition_to(self, new_status):
        return new_status in EXIT_INTERVIEW_TRANSITIONS.get(self.status, [])
