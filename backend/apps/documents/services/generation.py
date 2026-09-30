"""Orchestrates creating a new document version: number → context → PDF → file."""
from django.core.files.base import ContentFile
from django.db import transaction

from ..models import (
    OffboardingDocument, DocumentCounter, CompanyProfile,
    DOCUMENT_TYPE_PREFIX,
)
from . import pdf as pdf_service
from .context import build_context

DEFAULT_TITLES = {
    'RELIEVING_LETTER': 'Relieving Letter',
    'EXPERIENCE_LETTER': 'Experience Certificate',
    'FULL_FINAL_SETTLEMENT': 'Full & Final Settlement',
    'EXIT_CLEARANCE': 'Exit Clearance Certificate',
    'OTHER': 'Document',
}


def _make_number(resignation, document_type):
    prefix = DOCUMENT_TYPE_PREFIX.get(document_type, 'DOC')
    scope = f"{prefix}-{resignation.employee.employee_id}"
    seq = DocumentCounter.next_value(scope)
    return f"{prefix}-{resignation.employee.employee_id}-{seq:03d}", seq


@transaction.atomic
def generate_document(resignation, document_type, document_date, prepared_by, title=None):
    """Create a new GENERATED document version. Raises ValueError on missing data."""
    # Validate + gather stored data (never invents dates).
    ctx = build_context(resignation, document_type)

    number, seq = _make_number(resignation, document_type)
    # Version = number of existing docs of this type for the employee + 1.
    version = OffboardingDocument.objects.filter(
        offboarding_request=resignation, document_type=document_type).count() + 1

    doc = OffboardingDocument(
        offboarding_request=resignation,
        employee=resignation.employee,
        document_type=document_type,
        document_number=number,
        document_title=title or DEFAULT_TITLES.get(document_type, 'Document'),
        status='GENERATED',
        version=version,
        document_date=document_date,   # manual, may be None → renders "Not entered"
        prepared_by=prepared_by,
    )

    company = CompanyProfile.get_solo()
    generator = pdf_service.GENERATORS.get(document_type)
    if generator is None:
        # OTHER — render a minimal relieving-style page
        generator = pdf_service.relieving_letter
    pdf_bytes = generator(doc, ctx, company)

    doc.save()  # need pk/version for upload path
    doc.file.save(f"{number}.pdf", ContentFile(pdf_bytes), save=True)
    return doc


def regenerate_document(document, document_date, prepared_by, title=None):
    """Produce a fresh version from an existing document (does not overwrite it)."""
    return generate_document(
        document.offboarding_request, document.document_type,
        document_date, prepared_by, title or document.document_title,
    )
