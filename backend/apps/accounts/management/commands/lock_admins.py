"""Lock the ADMIN role down to a fixed set of accounts.

Policy applied (idempotent):
  * The given accounts (default: JSAN202, JSAN252) become ADMIN.
  * Every other account keeps only MANAGER / IT (so managers still receive
    their reports' offboarding requests and IT still gets the clearance
    option); any other role is reset to EMPLOYEE.
  * The Django superuser / staff flags are stripped from every account that
    is not in the admin set, so no break-glass backend login lingers.

Argument-only (no inline Python), so it runs cleanly over
`railway ssh "... manage.py lock_admins"`.

Usage:
  python manage.py lock_admins
  python manage.py lock_admins JSAN202 JSAN252
  python manage.py lock_admins --keep-roles MANAGER,IT,FINANCE
  python manage.py lock_admins --dry-run
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import ROLE_CHOICES
from apps.employees.models import Employee

VALID_ROLES = {r for r, _ in ROLE_CHOICES}
DEFAULT_ADMINS = ['JSAN202', 'JSAN252', 'JSAN350', 'JSAN365']
DEFAULT_KEEP = ['MANAGER', 'IT']


class Command(BaseCommand):
    help = "Restrict the ADMIN role to a fixed set of accounts; reset everyone else."

    def add_arguments(self, parser):
        parser.add_argument(
            'admins', nargs='*', default=DEFAULT_ADMINS,
            help=f'Employee IDs or emails that should be ADMIN (default: {", ".join(DEFAULT_ADMINS)}).',
        )
        parser.add_argument(
            '--keep-roles', default=','.join(DEFAULT_KEEP),
            help=f'Comma-separated roles to preserve on non-admins (default: {",".join(DEFAULT_KEEP)}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would change without writing anything.',
        )

    def _resolve(self, ident):
        User = get_user_model()
        emp = Employee.objects.filter(employee_id__iexact=ident).select_related('user').first()
        if emp and emp.user:
            return emp.user
        return User.objects.filter(email__iexact=ident).first()

    def handle(self, *args, **opts):
        User = get_user_model()
        admins = opts['admins'] or DEFAULT_ADMINS
        keep = {r.strip().upper() for r in opts['keep_roles'].split(',') if r.strip()}
        bad = keep - VALID_ROLES
        if bad:
            raise CommandError(f'Invalid --keep-roles: {", ".join(sorted(bad))}. Valid: {", ".join(sorted(VALID_ROLES))}.')

        admin_ids = set()
        for ident in admins:
            user = self._resolve(ident.strip())
            if user is None:
                raise CommandError(f'No user found for admin "{ident}".')
            admin_ids.add(user.pk)

        dry = opts['dry_run']
        changes = []
        with transaction.atomic():
            for u in User.objects.all():
                is_admin = u.pk in admin_ids
                target = 'ADMIN' if is_admin else (u.role if u.role in keep else 'EMPLOYEE')
                fields = []
                if u.role != target:
                    changes.append(f'{u.email}: role {u.role} -> {target}')
                    u.role = target
                    fields.append('role')
                if not is_admin and (u.is_superuser or u.is_staff):
                    changes.append(f'{u.email}: strip superuser/staff')
                    u.is_superuser = False
                    u.is_staff = False
                    fields += ['is_superuser', 'is_staff']
                if fields and not dry:
                    u.save(update_fields=fields)
            if dry:
                transaction.set_rollback(True)

        for line in changes:
            self.stdout.write(line)
        verb = 'Would change' if dry else 'Changed'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {len(changes)} field-set(s). ADMINs: {", ".join(sorted(admins))}; '
            f'kept roles: {", ".join(sorted(keep)) or "none"}; everyone else EMPLOYEE.'
        ))
