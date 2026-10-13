"""Create the GIS active employees that were added after the initial seed.

These 19 employees were onboarded from the "List of active & exit Employees"
roster. This command bakes in their confirmed details (JSAN ID, name, email,
department, designation, DOJ) so the same set can be created on any database
(local and live) and the active-employee counts match.

Idempotent: an employee / login that already exists is skipped. A shared initial
password is set on newly-created logins (change on first login).

Usage:
  python manage.py add_gis_employees [--password Welcome@123] [--dry-run]
"""
import re
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.employees.models import Department, Designation, Employee

ROSTER = [
    ('JSAN254', 'Raghu', 'Darma', 'rdarma@jsanconsulting.com', 'GIS', 'Field Specialist Lead', '2025-02-12'),
    ('JSAN376', 'Sneha Sindhu', 'Rajan', 'srajan@jsanconsulting.com', 'GIS', 'Telecom Operator', '2026-09-08'),
    ('JSAN382', 'Manoj', 'Kasurthi', 'mkasurthi@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN383', 'Sai Tarun', 'Anusuri', 'sanusuri@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN387', 'Navya', 'Chandra Lekha', 'nchandralekha@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN390', 'Ganesh Revanth', 'Juturi', 'gjuturi@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN391', 'Karthik', 'Mudadla', 'kmudadla@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN392', 'Hemanth Kumar', 'Jeripothula', 'hjeripothula@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN393', 'Naga Lokesh', 'Gandham', 'ngandham@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN395', 'Syam Kumar', 'Vallepu', 'svallepu@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN396', 'Mahesh', 'Kasukurthi', 'mkasukurthi@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN397', 'Aneesha', 'Vasamsetti', 'avasamsetti@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN398', 'Suresh', 'Nagula', 'snagula@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN399', 'Vishnu Vardhan', 'Chevuri', 'vchevuri@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN402', 'Venkatesh', 'Kothapally', 'vkothapally@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN403', 'Joga Venkata Bhaskar', 'Mandarapu', 'jmandarapu@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN404', 'Ajay Kumar', 'Ghantasala', 'aghantasala@jsanconsulting.com', 'GIS', 'Telecom Operator', '2026-10-05'),
    ('JSAN405', 'Harish', 'Andluri', 'handluri@jsanconsulting.com', 'GIS', 'Telecom Operator', '2026-10-05'),
    ('JSAN406', 'Harikrishna', 'Islavath', 'hislavath@jsanconsulting.com', 'GIS', 'Telecom Operator', '2026-10-05'),
    # Added 2026-10-13
    ('JSAN385', 'Preethi', 'Kamani', 'pkamani@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN386', 'Prameela', 'Navagani', 'pnavagani@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN388', 'Pujitha', 'Yeluri', 'pyeluri@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN389', 'Manasa', 'Lekkala', 'mlekkala@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN394', 'Naga Nishita', 'Golla', 'ngolla@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN401', 'Thirupathi', 'Beemarapu', 'tbimarapu@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
    ('JSAN380', 'Sai Sanjana', 'Gunda', 'sgunda@jsanconsulting.com', 'GIS', 'Recruiter', '2026-09-23'),
    ('JSAN381', 'Ravinder', 'Ravula', 'rravula@jsanconsulting.com', 'GIS', 'Project Manager', '2026-09-28'),
    ('JSAN384', 'Manikanta Sai Mahesh', 'Vanumu', 'msvanumu@jsanconsulting.com', 'GIS', 'Trainee', '2026-10-01'),
]


class Command(BaseCommand):
    help = 'Create the 19 post-seed GIS active employees (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Welcome@123', help='Initial password for new logins')
        parser.add_argument('--dry-run', action='store_true')

    def _get_dept(self, name):
        e = Department.objects.filter(name=name).first()
        if e:
            return e
        base = re.sub(r'[^A-Z0-9]', '', name.upper())[:16] or 'DEPT'
        code, i = base, 1
        while Department.objects.filter(code=code).exists():
            i += 1
            code = f'{base}{i}'[:20]
        return Department.objects.create(name=name, code=code)

    def handle(self, *args, **opts):
        pw, dry = opts['password'], opts['dry_run']
        created = skipped = 0
        for jid, first, last, email, dept_name, desig_name, doj in ROSTER:
            if Employee.objects.filter(employee_id=jid).exists():
                self.stdout.write(f'  skip (employee exists): {jid} {first} {last}')
                skipped += 1
                continue
            if User.objects.filter(email__iexact=email).exists():
                self.stdout.write(f'  skip (email exists): {email}')
                skipped += 1
                continue
            if dry:
                self.stdout.write(f'  would create: {jid} {first} {last} <{email}> {dept_name}/{desig_name}')
                created += 1
                continue
            with transaction.atomic():
                dept = self._get_dept(dept_name)
                desig = None
                if desig_name:
                    desig, _ = Designation.objects.get_or_create(name=desig_name, department=dept)
                user = User.objects.create_user(
                    email=email, username=email, password=pw,
                    first_name=first, last_name=last, role='EMPLOYEE',
                )
                Employee.objects.create(
                    employee_id=jid, user=user, first_name=first, last_name=last, email=email,
                    department=dept, designation=desig,
                    joining_date=date.fromisoformat(doj), employment_status='ACTIVE',
                )
            self.stdout.write(self.style.SUCCESS(f'  created: {jid} {first} {last} <{email}>'))
            created += 1

        active = Employee.objects.filter(employment_status='ACTIVE').count()
        verb = 'Would create' if dry else 'Created'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {created}, skipped {skipped}. Active employees now: {active}.'))
