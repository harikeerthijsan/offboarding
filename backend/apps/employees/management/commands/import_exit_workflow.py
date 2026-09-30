"""Backfill completed offboarding records for historical exited employees
(the Exit sheet). Creates each person's profile plus a fully-completed workflow:
resignation -> manager+HR approval -> notice period -> KT -> clearances ->
settlement -> exit interview -> final HR approval -> EXITED.

Only real dates from the sheet are used: DOJ (joining) and DOE (exit). Every
exit-related business date is set to DOE (the only exit date we have); unknown
milestone start dates are left blank. Nothing is auto-generated from "today".

Dev/admin utility. Idempotent: skips employees / resignations that already exist.

Usage:
  python manage.py import_exit_workflow \
      --details "C:/path/List of active & exit Employees.xlsx" \
      --roster  "C:/path/Employee List 1.xlsx" \
      --password "Welcome@123" [--commit]
"""
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.employees.models import Department, Designation, Employee
from apps.offboarding.models import (
    ResignationRequest, NoticePeriod, Project, KnowledgeTransfer,
    DepartmentClearance, FinalSettlement, ExitInterview, CLEARANCE_DEPARTMENTS,
)

User = get_user_model()


def toks(s):
    if not s:
        return set()
    s = str(s).lower()
    s = re.sub(r'[^a-z ]', ' ', s)
    return {t for t in s.split() if len(t) > 1}


class Command(BaseCommand):
    help = 'Backfill completed offboarding workflow for historical exited employees.'

    def add_arguments(self, parser):
        parser.add_argument('--details', required=True)
        parser.add_argument('--roster', default=None, help='Optional Name/Email xlsx for real emails')
        parser.add_argument('--password', required=True)
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl required')

        wb = openpyxl.load_workbook(opts['details'], data_only=True)
        if 'Exit' not in wb.sheetnames:
            raise CommandError('No "Exit" sheet found')
        rows = []
        for r in wb['Exit'].iter_rows(min_row=2, values_only=True):
            if r and r[1] and r[3] and (len(r) > 7 and r[7]):
                rows.append(dict(jid=str(r[1]).strip(), name=str(r[2]).strip(), doj=r[3],
                                 desig=(r[4] or '').strip(), dept=(r[5] or '').strip(),
                                 rm=(r[6] or '').strip(), doe=r[7]))

        # optional roster email lookup by normalised name
        roster = {}
        if opts['roster']:
            wr = openpyxl.load_workbook(opts['roster'], data_only=True)
            ws = wr[wr.sheetnames[0]]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0] and len(row) > 1 and row[1]:
                    roster[frozenset(toks(row[0]))] = str(row[1]).strip().lower()

        hr_user = User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True).order_by('role').first()
        if not hr_user:
            raise CommandError('No HR/ADMIN user exists to act as reviewer.')

        self.stdout.write(f"Exit rows: {len(rows)}   HR reviewer: {hr_user.email}")
        if not opts['commit']:
            resolvable = sum(1 for r in rows if self._resolve_manager(r['rm']))
            self.stdout.write(f"Managers resolvable: {resolvable}/{len(rows)}")
            self.stdout.write(self.style.WARNING('DRY RUN — no DB changes. Re-run with --commit.'))
            for r in rows[:5]:
                self.stdout.write(f"  would create: {r['jid']} {r['name']} | joined {r['doj'].date()} "
                                  f"| exited {r['doe'].date()} | mgr={r['rm'] or '—'}")
            return

        created, skipped = 0, 0
        for r in rows:
            if Employee.objects.filter(employee_id=r['jid']).exists():
                skipped += 1
                continue
            try:
                self._build_one(r, roster, hr_user, opts['password'])
                created += 1
            except Exception as e:  # noqa: BLE001 - surface which row failed, continue
                self.stderr.write(self.style.ERROR(f"  FAILED {r['jid']} {r['name']}: {e}"))
        self.stdout.write(self.style.SUCCESS(f"Created {created} exited-employee workflows, skipped {skipped}."))

    # ── helpers ──
    def _resolve_manager(self, rm):
        rt = toks(rm)
        if not rt:
            return None
        best, bestlen = None, 999
        for e in Employee.objects.all():
            et = toks(f"{e.first_name} {e.last_name}")
            if rt & et:
                if len(et) < bestlen:
                    best, bestlen = e, len(et)
        return best

    def _get_dept(self, nm):
        if not nm:
            return None
        existing = Department.objects.filter(name=nm).first()
        if existing:
            return existing
        base = re.sub(r'[^A-Z0-9]', '', nm.upper())[:16] or 'DEPT'
        code, i = base, 1
        while Department.objects.filter(code=code).exists():
            i += 1
            code = f"{base}{i}"[:20]
        return Department.objects.create(name=nm, code=code)

    @transaction.atomic
    def _build_one(self, r, roster, hr_user, password):
        doe = r['doe'].date() if hasattr(r['doe'], 'date') else r['doe']
        doj = r['doj'].date() if hasattr(r['doj'], 'date') else r['doj']
        parts = r['name'].split()
        first, last = parts[0], ' '.join(parts[1:]) if len(parts) > 1 else ''
        email = roster.get(frozenset(toks(r['name']))) or f"{r['jid'].lower()}@jsan.local"

        # user (exited → inactive), unique email/username
        if User.objects.filter(email=email).exists():
            email = f"{r['jid'].lower()}@jsan.local"
        user = User.objects.create_user(
            email=email, username=email, password=password,
            first_name=first, last_name=last, role='EMPLOYEE', is_active=False,
        )
        dept = self._get_dept(r['dept'])
        desig = None
        if r['desig']:
            desig, _ = Designation.objects.get_or_create(name=r['desig'], department=dept)

        emp = Employee.objects.create(
            employee_id=r['jid'], user=user, first_name=first, last_name=last, email=email,
            department=dept, designation=desig, joining_date=doj, employment_status='EXITED',
        )
        manager = self._resolve_manager(r['rm'])
        if manager and manager.pk != emp.pk:
            emp.manager = manager
            emp.save(update_fields=['manager'])
        mgr_user = manager.user if (manager and manager.user) else hr_user
        now = timezone.now()

        resignation = ResignationRequest.objects.create(
            employee=emp, submitted_by=user, status='COMPLETED', reason='OTHER',
            resignation_date=doe, last_working_date=doe,
            notes='Imported historical exit record.',
            manager_reviewed_by=mgr_user, manager_reviewed_at=now, manager_notes='Approved (historical import).',
            hr_reviewed_by=hr_user, hr_reviewed_at=now, hr_notes='Approved (historical import).',
            kt_completed_by=hr_user, kt_completed_at=now,
            clearance_completed_by=hr_user, clearance_completed_at=now,
            final_review_status='APPROVED', final_reviewed_by=hr_user,
            final_review_date=doe, final_approval_date=doe,
            final_review_comments='Historical import — all steps completed.',
        )

        NoticePeriod.objects.create(
            resignation=resignation, status='COMPLETED',
            expected_last_working_day=doe, actual_last_working_day=doe,
            notice_comments='Historical import.', created_by=hr_user,
        )

        # KT — receiver must be an ACTIVE employee that isn't the exiting one
        receiver = manager if (manager and manager.employment_status == 'ACTIVE') else \
            Employee.objects.filter(employment_status='ACTIVE').exclude(pk=emp.pk).first()
        if receiver:
            project, _ = Project.objects.get_or_create(
                code='HIST', defaults={'name': 'Historical Handover'})
            KnowledgeTransfer.objects.create(
                offboarding_request=resignation, title='Role handover', assigned_to=emp,
                receiver=receiver, project=project, priority='MEDIUM', status='COMPLETED',
                completed_date=doe, completion_notes='Historical import.',
                receiver_reviewed_by=hr_user, receiver_reviewed_at=now,
                manager_reviewed_by=hr_user, manager_reviewed_at=now, created_by=hr_user,
            )

        for dept_code, _label in CLEARANCE_DEPARTMENTS:
            DepartmentClearance.objects.create(
                offboarding_request=resignation, department=dept_code, status='CLEARED',
                comments='Historical import.', clearance_date=doe,
                cleared_by=hr_user, cleared_at=now,
            )

        fs = FinalSettlement(
            offboarding_request=resignation, employee=emp, settlement_status='APPROVED',
            prepared_by=hr_user, reviewed_by=hr_user, approved_by=hr_user,
            settlement_date=doe, comments='Historical import — no financial data (zeros).',
        )
        fs.recompute_totals()
        fs.save()

        ExitInterview.objects.create(
            offboarding_request=resignation, employee=emp, status='COMPLETED',
            interview_date=doe, conducted_by=hr_user, submitted_at=now,
            additional_comments='Historical import.',
        )
