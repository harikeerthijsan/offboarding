"""Reset (re-onboard) one or more employees by removing their offboarding data.

Intended for TEST employees that were offboarded for a trial run. It deletes the
full offboarding chain (resignation, notice period, knowledge transfer, clearances,
settlement, exit interview, generated documents and related notifications), restores
the employee's assets to ASSIGNED, and sets the employee back to ACTIVE.

Usage:
  python manage.py reset_offboarding JSAN010 JSAN049 JSAN321
  python manage.py reset_offboarding --email kvoore@jsanconsulting.com
  python manage.py reset_offboarding JSAN010 --dry-run

Safe to run repeatedly (idempotent). Use --dry-run first to preview.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.employees.models import Employee
from apps.offboarding.models import (
    ResignationRequest, NoticePeriod, KnowledgeTransfer, KTDocument,
    AssetClearance, DepartmentClearance, ClearanceChecklistItem,
    FinalSettlement, ExitInterview, Asset,
)
from apps.documents.models import OffboardingDocument
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = 'Reset (re-onboard) test employees: remove their offboarding data and set them ACTIVE.'

    def add_arguments(self, parser):
        parser.add_argument('employee_ids', nargs='*', help='Employee IDs, e.g. JSAN010 JSAN049')
        parser.add_argument('--email', action='append', default=[],
                            help='Match by login/employee email instead of employee_id (repeatable)')
        parser.add_argument('--dry-run', action='store_true', help='Preview without changing anything')

    def _resolve(self, employee_ids, emails):
        employees = []
        for eid in employee_ids:
            try:
                employees.append(Employee.objects.get(employee_id=eid))
            except Employee.DoesNotExist:
                raise CommandError(f'No employee with employee_id "{eid}".')
        for em in emails:
            try:
                employees.append(Employee.objects.get(email__iexact=em))
            except Employee.DoesNotExist:
                raise CommandError(f'No employee with email "{em}".')
        # de-dupe preserving order
        seen, unique = set(), []
        for e in employees:
            if e.pk not in seen:
                seen.add(e.pk); unique.append(e)
        return unique

    def handle(self, *args, **opts):
        employees = self._resolve(opts['employee_ids'], opts['email'])
        if not employees:
            raise CommandError('Provide at least one employee_id or --email.')
        dry = opts['dry_run']

        for e in employees:
            reqs = list(ResignationRequest.objects.filter(employee=e))
            assets = list(Asset.objects.filter(assigned_to=e).exclude(status='ASSIGNED'))
            self.stdout.write(
                f'{e.employee_id} {e.first_name} {e.last_name} '
                f'(status={e.employment_status}): {len(reqs)} resignation(s), '
                f'{len(assets)} asset(s) to restore'
            )
            if dry:
                continue

            with transaction.atomic():
                for r in reqs:
                    for dc in DepartmentClearance.objects.filter(offboarding_request=r):
                        ClearanceChecklistItem.objects.filter(department_clearance=dc).delete()
                    DepartmentClearance.objects.filter(offboarding_request=r).delete()
                    for kt in KnowledgeTransfer.objects.filter(offboarding_request=r):
                        KTDocument.objects.filter(knowledge_transfer=kt).delete()
                    KnowledgeTransfer.objects.filter(offboarding_request=r).delete()
                    AssetClearance.objects.filter(offboarding_request=r).delete()
                    FinalSettlement.objects.filter(offboarding_request=r).delete()
                    ExitInterview.objects.filter(offboarding_request=r).delete()
                    OffboardingDocument.objects.filter(offboarding_request=r).delete()
                    Notification.objects.filter(related_offboarding=r).delete()
                    NoticePeriod.objects.filter(resignation=r).delete()
                    r.delete()
                Asset.objects.filter(assigned_to=e).exclude(status='ASSIGNED').update(status='ASSIGNED')
                if e.employment_status != 'ACTIVE':
                    e.employment_status = 'ACTIVE'
                    e.save(update_fields=['employment_status', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(f'  -> reset to ACTIVE, offboarding data removed'))

        verb = 'Would reset' if dry else 'Reset'
        self.stdout.write(self.style.SUCCESS(f'{verb} {len(employees)} employee(s).'))
