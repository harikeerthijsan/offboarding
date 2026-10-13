"""Add the three requested employees without replacing existing production data."""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.employees.models import Department, Designation, Employee


RECORDS = [
    ('JSAN083', 'Anjali', 'Singh', 'asingh@jsanconsulting.com',
     date(2021, 4, 19), 'Recruitment-IN', 'Account Manager - IN', 'JSAN005'),
    ('JSAN022', 'Kajal', 'Prajwal Mendon', 'ksalian@jsanconsulting.com',
     date(2020, 8, 6), 'Recruitment-IN', 'Domestic Recruiter', 'JSAN083'),
    ('JSAN400', 'Puranapu', 'Shiva Ramakrishna', 'spuranapu@jsanconsulting.com',
     date(2026, 10, 1), 'GIS', 'Trainee', None),
]


class Command(BaseCommand):
    help = 'Add the three requested employee accounts/profiles; preserve existing rows.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        with transaction.atomic():
            for eid, first, last, email, joined, dept, title, manager_id in RECORDS:
                existing = Employee.objects.filter(employee_id=eid).first()
                if existing:
                    if existing.email.lower() != email.lower():
                        raise CommandError(f'{eid}: existing employee email differs; stopping')
                    self.stdout.write(f'{eid}: already exists; preserved')
                    continue
                if Employee.objects.filter(email__iexact=email).exists():
                    raise CommandError(f'{eid}: email belongs to a different employee')
                department = Department.objects.get(name=dept)
                manager = Employee.objects.get(employee_id=manager_id) if manager_id else None
                designation, _ = Designation.objects.get_or_create(name=title, department=department)
                user = User.objects.filter(email__iexact=email).first()
                if user and Employee.objects.filter(user=user).exists():
                    raise CommandError(f'{eid}: account belongs to a different employee')
                if not user:
                    if User.objects.filter(username=email).exists():
                        raise CommandError(f'{eid}: username conflict')
                    user = User(username=email, email=email, first_name=first,
                                last_name=last, role='EMPLOYEE', is_active=True)
                    # HR must provision the password; never seed shared credentials.
                    user.set_unusable_password()
                    user.save()
                Employee.objects.create(
                    employee_id=eid, user=user, first_name=first, last_name=last,
                    email=email, joining_date=joined, department=department,
                    designation=designation, manager=manager, employment_status='ACTIVE',
                    phone='9011099221' if eid == 'JSAN083' else '')
                self.stdout.write(f'{eid}: created ACTIVE' + ('; reporting manager pending' if not manager else ''))
            if options['dry_run']:
                transaction.set_rollback(True)
                self.stdout.write('Preview only; no records saved.')
