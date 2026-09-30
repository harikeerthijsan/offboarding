from django.core.management.base import BaseCommand
from apps.employees.models import Department, Designation


class Command(BaseCommand):
    help = 'Seed initial departments and designations'

    def handle(self, *args, **options):
        departments_data = [
            {'name': 'Engineering', 'code': 'ENG', 'description': 'Software Engineering department'},
            {'name': 'Human Resources', 'code': 'HR', 'description': 'HR and People operations'},
            {'name': 'Finance', 'code': 'FIN', 'description': 'Finance and Accounting'},
            {'name': 'Information Technology', 'code': 'IT', 'description': 'IT Infrastructure and Support'},
            {'name': 'Operations', 'code': 'OPS', 'description': 'Business Operations'},
            {'name': 'Marketing', 'code': 'MKT', 'description': 'Marketing and Communications'},
        ]
        designations_data = [
            ('Engineering', [
                ('Software Engineer', 'SWE'),
                ('Senior Software Engineer', 'SWE-SR'),
                ('Lead Software Engineer', 'SWE-LEAD'),
                ('Engineering Manager', 'ENG-MGR'),
                ('DevOps Engineer', 'DEVOPS'),
            ]),
            ('Human Resources', [
                ('HR Executive', 'HR-EXEC'),
                ('HR Manager', 'HR-MGR'),
                ('Talent Acquisition Specialist', 'TA-SPEC'),
                ('HR Business Partner', 'HRBP'),
            ]),
            ('Finance', [
                ('Finance Executive', 'FIN-EXEC'),
                ('Finance Manager', 'FIN-MGR'),
                ('Accountant', 'ACCT'),
                ('Financial Analyst', 'FA'),
            ]),
            ('Information Technology', [
                ('IT Administrator', 'IT-ADMIN'),
                ('IT Manager', 'IT-MGR'),
                ('Systems Engineer', 'SYS-ENG'),
                ('Network Engineer', 'NET-ENG'),
            ]),
            ('Operations', [
                ('Operations Executive', 'OPS-EXEC'),
                ('Operations Manager', 'OPS-MGR'),
                ('Project Manager', 'PM'),
            ]),
            ('Marketing', [
                ('Marketing Executive', 'MKT-EXEC'),
                ('Marketing Manager', 'MKT-MGR'),
                ('Digital Marketing Specialist', 'DMS'),
            ]),
        ]
        for d in departments_data:
            dept, created = Department.objects.get_or_create(
                name=d['name'],
                defaults={'code': d['code'], 'description': d['description']},
            )
            if created:
                self.stdout.write(f'Created department: {dept.name}')
        for dept_name, desigs in designations_data:
            try:
                dept = Department.objects.get(name=dept_name)
                for name, code in desigs:
                    des, created = Designation.objects.get_or_create(
                        name=name,
                        department=dept,
                        defaults={'code': code},
                    )
                    if created:
                        self.stdout.write(f'  Created designation: {des.name} ({dept_name})')
            except Department.DoesNotExist:
                pass
        self.stdout.write(self.style.SUCCESS('Seed data complete.'))
