from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.employees.models import Department, Employee


class RequestedEmployeeImportTests(TestCase):
    def setUp(self):
        for name, code in [('Recruitment-IN', 'IN'), ('Recruitment-UK/EU', 'UK'), ('GIS', 'GIS')]:
            Department.objects.create(name=name, code=code)
        user = get_user_model().objects.create_user(
            username='manager', email='manager@example.com', password='test-only', role='MANAGER')
        Employee.objects.create(employee_id='JSAN005', user=user, first_name='Kalpesh',
                                last_name='Mehta', email=user.email, joining_date='2020-01-01')

    def test_dry_run_does_not_persist(self):
        call_command('seed_requested_employees', dry_run=True, stdout=StringIO())
        self.assertEqual(Employee.objects.count(), 1)
        self.assertFalse(get_user_model().objects.filter(email='ksalian@jsanconsulting.com').exists())

    def test_import_preserves_records_on_repeat(self):
        call_command('seed_requested_employees', stdout=StringIO())
        anjali = Employee.objects.get(employee_id='JSAN083')
        self.assertEqual(anjali.manager.employee_id, 'JSAN005')
        self.assertEqual(anjali.last_name, 'Singh')
        self.assertEqual(anjali.phone, '9011099221')
        self.assertEqual(anjali.department.name, 'Recruitment-IN')
        self.assertEqual(anjali.designation.name, 'Account Manager - IN')
        self.assertEqual(Employee.objects.get(employee_id='JSAN022').manager_id, anjali.pk)
        self.assertEqual(anjali.employment_status, 'ACTIVE')
        self.assertFalse(anjali.user.has_usable_password())
        anjali.employment_status = 'EXITED'
        anjali.save()
        call_command('seed_requested_employees', stdout=StringIO())
        anjali.refresh_from_db()
        self.assertEqual(Employee.objects.count(), 4)
        self.assertEqual(anjali.employment_status, 'EXITED')
