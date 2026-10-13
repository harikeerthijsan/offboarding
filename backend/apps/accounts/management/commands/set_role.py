"""Set a user's role by employee ID or email.

Simple, argument-only command (no inline Python needed) so it runs cleanly over
`railway ssh "... manage.py set_role JSAN252 ADMIN"`.

Usage:
  python manage.py set_role JSAN252 ADMIN
  python manage.py set_role vsatish@jsanconsulting.com HR
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import ROLE_CHOICES
from apps.employees.models import Employee

VALID_ROLES = {r for r, _ in ROLE_CHOICES}


class Command(BaseCommand):
    help = "Set a user's role, looked up by employee ID or email."

    def add_arguments(self, parser):
        parser.add_argument('identifier', help='Employee ID (e.g. JSAN252) or email')
        parser.add_argument('role', help=f'One of: {", ".join(sorted(VALID_ROLES))}')

    def handle(self, *args, **opts):
        ident = opts['identifier'].strip()
        role = opts['role'].strip().upper()
        if role not in VALID_ROLES:
            raise CommandError(f'Invalid role "{role}". Choose from: {", ".join(sorted(VALID_ROLES))}.')

        User = get_user_model()
        user = None
        emp = Employee.objects.filter(employee_id__iexact=ident).select_related('user').first()
        if emp and emp.user:
            user = emp.user
        if user is None:
            user = User.objects.filter(email__iexact=ident).first()
        if user is None:
            raise CommandError(f'No user found for "{ident}".')

        old = user.role
        if old == role:
            self.stdout.write(f'{ident}: already {role}; no change.')
            return
        user.role = role
        user.save(update_fields=['role'])
        name = f'{user.first_name} {user.last_name}'.strip() or user.username
        self.stdout.write(self.style.SUCCESS(f'{ident} ({name}): role {old} -> {role}.'))
