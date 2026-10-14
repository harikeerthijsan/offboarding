"""Enable login for employee accounts that were seeded without a usable password.

Sets a password (default Welcome@123) and activates the account, looked up by
employee ID or email. Argument-only so it runs cleanly over `railway ssh`.

Usage:
  python manage.py enable_login JSAN083 JSAN022
  python manage.py enable_login JSAN083 --password 'Secret@123'
  python manage.py enable_login --all-disabled           # every login-disabled account
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.employees.models import Employee

DEFAULT_PASSWORD = 'Welcome@123'


class Command(BaseCommand):
    help = "Set a password and activate accounts (default Welcome@123)."

    def add_arguments(self, parser):
        parser.add_argument('identifiers', nargs='*', help='Employee IDs or emails.')
        parser.add_argument('--password', default=DEFAULT_PASSWORD,
                             help=f'Password to set (default {DEFAULT_PASSWORD}).')
        parser.add_argument('--all-disabled', action='store_true',
                             help='Target every account that currently has no usable password.')

    def _resolve(self, ident):
        User = get_user_model()
        emp = Employee.objects.filter(employee_id__iexact=ident).select_related('user').first()
        if emp and emp.user:
            return emp.user
        return User.objects.filter(email__iexact=ident).first()

    def handle(self, *args, **opts):
        User = get_user_model()
        password = opts['password']

        if opts['all_disabled']:
            users = [u for u in User.objects.all() if not u.has_usable_password()]
        else:
            if not opts['identifiers']:
                raise CommandError('Give employee IDs/emails, or use --all-disabled.')
            users = []
            for ident in opts['identifiers']:
                u = self._resolve(ident.strip())
                if u is None:
                    raise CommandError(f'No account found for "{ident}".')
                users.append(u)

        for u in users:
            u.set_password(password)
            u.is_active = True
            u.save(update_fields=['password', 'is_active'])
            emp = Employee.objects.filter(user=u).first()
            label = emp.employee_id if emp else u.email
            self.stdout.write(self.style.SUCCESS(f'{label} ({u.email}) -> login enabled'))

        self.stdout.write(self.style.SUCCESS(f'Enabled {len(users)} account(s) with the given password.'))
