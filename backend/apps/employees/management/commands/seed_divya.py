"""Create the JSAN407 (Divya S B) active employee + login account.

Idempotent and argument-free so it runs cleanly over `railway ssh` with no
quoting or multi-line paste issues:

  python manage.py seed_divya

Details:
  JSAN407 · Divya S B · divyasb@jsanconsulting.com
  GIS / Pre-sales Executive · manager JSAN369 (Chandrika B R)
  DOJ 2026-10-12 · ACTIVE · role EMPLOYEE · password Welcome@123
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.employees.models import Department, Designation, Employee

PASSWORD = 'Welcome@123'


class Command(BaseCommand):
    help = "Create the JSAN407 (Divya S B) employee and login account (idempotent)."

    def handle(self, *args, **opts):
        with transaction.atomic():
            gis = Department.objects.filter(name__iexact='GIS').first()
            if not gis:
                raise CommandError('GIS department not found.')
            mgr = Employee.objects.filter(employee_id='JSAN369').first()
            if not mgr:
                raise CommandError('Manager JSAN369 not found.')

            desig, _ = Designation.objects.get_or_create(
                name='Pre-sales Executive', department=gis, defaults={'is_active': True},
            )
            user, user_created = User.objects.get_or_create(
                email='divyasb@jsanconsulting.com',
                defaults={'username': 'JSAN407', 'first_name': 'Divya',
                          'last_name': 'S B', 'role': 'EMPLOYEE'},
            )
            user.set_password(PASSWORD)
            user.is_active = True
            user.save()

            emp, emp_created = Employee.objects.get_or_create(
                employee_id='JSAN407',
                defaults={
                    'user': user, 'first_name': 'Divya', 'last_name': 'S B',
                    'email': 'divyasb@jsanconsulting.com', 'department': gis,
                    'designation': desig, 'manager': mgr, 'joining_date': '2026-10-12',
                    'employment_status': 'ACTIVE', 'employment_type': 'FULL_TIME',
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'JSAN407 {emp.first_name} {emp.last_name} | user_created={user_created} '
            f'emp_created={emp_created} | {emp.designation.name} | mgr {emp.manager.employee_id} '
            f'| DOJ {emp.joining_date} | login divyasb@jsanconsulting.com / {PASSWORD}'
        ))
