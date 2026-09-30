from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.audit.models import AuditLog
from .models import Department, Designation, Employee


def get_token(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class BaseTestCase(APITestCase):
    """Shared setUp for users and a default department."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            username='adminuser',
            password='testpass123',
            role='ADMIN',
        )
        self.hr_user = User.objects.create_user(
            email='hr@example.com',
            username='hruser',
            password='testpass123',
            role='HR',
        )
        self.manager_user = User.objects.create_user(
            email='manager@example.com',
            username='manageruser',
            password='testpass123',
            role='MANAGER',
        )
        self.employee_user = User.objects.create_user(
            email='employee@example.com',
            username='employeeuser',
            password='testpass123',
            role='EMPLOYEE',
        )
        self.new_user = User.objects.create_user(
            email='new@example.com',
            username='newuser',
            password='testpass123',
            role='EMPLOYEE',
        )
        self.department = Department.objects.create(
            name='Engineering',
            code='ENG',
            description='Software Engineering',
        )

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token(user)}')

    def _create_employee(self, user, employee_id='EMP001', department=None, designation=None, manager=None):
        return Employee.objects.create(
            employee_id=employee_id,
            user=user,
            first_name=user.first_name or 'Test',
            last_name=user.last_name or 'User',
            email=user.email,
            department=department or self.department,
            designation=designation,
            joining_date='2023-01-01',
            manager=manager,
        )


# ---------------------------------------------------------------------------
# Phase 1 – Department (backward-compatible)
# ---------------------------------------------------------------------------

class DepartmentTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.list_url = '/api/employees/departments/'

    def test_create_department_as_hr(self):
        self.auth(self.hr_user)
        response = self.client.post(self.list_url, {'name': 'Finance', 'code': 'FIN'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Department.objects.filter(name='Finance').exists())

    def test_create_department_as_employee_forbidden(self):
        self.auth(self.employee_user)
        response = self.client.post(self.list_url, {'name': 'Finance', 'code': 'FIN'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_department_with_new_fields(self):
        self.auth(self.hr_user)
        data = {'name': 'Marketing', 'code': 'MKT', 'description': 'Marketing dept', 'is_active': True}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dept = Department.objects.get(name='Marketing')
        self.assertEqual(dept.code, 'MKT')
        self.assertEqual(dept.description, 'Marketing dept')
        self.assertTrue(dept.is_active)

    def test_list_departments_authenticated(self):
        self.auth(self.employee_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_departments_unauthenticated_returns_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_departments_by_is_active(self):
        Department.objects.create(name='Archived', code='ARC', is_active=False)
        self.auth(self.hr_user)
        response = self.client.get(self.list_url + '?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d['name'] for d in response.data['results']]
        self.assertIn('Engineering', names)
        self.assertNotIn('Archived', names)

    def test_department_employee_count_in_response(self):
        emp_user = User.objects.create_user(email='ec@example.com', username='ecuser', password='pass', role='EMPLOYEE')
        self._create_employee(emp_user, 'EMP_EC')
        self.auth(self.hr_user)
        response = self.client.get(f'{self.list_url}{self.department.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employee_count'], 1)

    def test_department_employees_endpoint(self):
        emp_user = User.objects.create_user(email='de@example.com', username='deuser', password='pass', role='EMPLOYEE')
        self._create_employee(emp_user, 'EMP_DE')
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}{self.department.id}/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_audit_log_created_on_department_create(self):
        self.auth(self.hr_user)
        self.client.post(self.list_url, {'name': 'Ops', 'code': 'OPS'}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='DEPARTMENT_CREATED').exists())


# ---------------------------------------------------------------------------
# Designation tests
# ---------------------------------------------------------------------------

class DesignationTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.list_url = '/api/employees/designations/'
        self.designation = Designation.objects.create(
            name='Software Engineer',
            code='SWE',
            department=self.department,
        )

    def test_create_designation_as_hr(self):
        self.auth(self.hr_user)
        data = {'name': 'DevOps Engineer', 'code': 'DEVOPS', 'department': self.department.id}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_designation_as_employee_forbidden(self):
        self.auth(self.employee_user)
        data = {'name': 'QA Engineer', 'code': 'QA', 'department': self.department.id}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_designations_authenticated(self):
        self.auth(self.employee_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_designations_by_department(self):
        other_dept = Department.objects.create(name='HR Dept', code='HR')
        Designation.objects.create(name='HR Executive', code='HR-EXEC', department=other_dept)
        self.auth(self.hr_user)
        response = self.client.get(f'{self.list_url}?department={self.department.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d['name'] for d in response.data['results']]
        self.assertIn('Software Engineer', names)
        self.assertNotIn('HR Executive', names)

    def test_filter_designations_by_is_active(self):
        Designation.objects.create(name='Archived Role', code='ARCH', department=self.department, is_active=False)
        self.auth(self.hr_user)
        response = self.client.get(f'{self.list_url}?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d['name'] for d in response.data['results']]
        self.assertNotIn('Archived Role', names)

    def test_designation_department_name_in_response(self):
        self.auth(self.hr_user)
        response = self.client.get(f'{self.list_url}{self.designation.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['department_name'], 'Engineering')

    def test_audit_log_created_on_designation_create(self):
        self.auth(self.hr_user)
        self.client.post(self.list_url, {'name': 'Lead Eng', 'code': 'LEAD', 'department': self.department.id}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='DESIGNATION_CREATED').exists())


# ---------------------------------------------------------------------------
# Phase 1 – Employee (backward-compatible tests kept)
# ---------------------------------------------------------------------------

class EmployeeTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.list_url = '/api/employees/'

    # -- Phase 1 tests --

    def test_create_employee_as_hr(self):
        self.auth(self.hr_user)
        data = {
            'employee_id': 'EMP100',
            'user_id': self.new_user.id,
            'first_name': 'New',
            'last_name': 'Employee',
            'email': self.new_user.email,
            'department_id': self.department.id,
            'joining_date': '2023-06-01',
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_employee_cannot_create_employee(self):
        self.auth(self.employee_user)
        data = {
            'employee_id': 'EMP999',
            'user_id': self.new_user.id,
            'first_name': 'Another',
            'last_name': 'User',
            'email': self.new_user.email,
            'department_id': self.department.id,
            'joining_date': '2023-06-01',
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_employees_authenticated_manager(self):
        self._create_employee(self.employee_user, 'EMP001')
        self.auth(self.manager_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_employees_unauthenticated_returns_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_employee_by_id(self):
        emp = self._create_employee(self.employee_user, 'EMP002')
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}{emp.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employee_id'], 'EMP002')

    def test_employee_cannot_list_employees(self):
        self.auth(self.employee_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -- Phase 2 tests --

    def test_create_employee_with_new_fields(self):
        designation = Designation.objects.create(name='Engineer', code='ENG-R', department=self.department)
        self.auth(self.hr_user)
        data = {
            'employee_id': 'EMP200',
            'user_id': self.new_user.id,
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': self.new_user.email,
            'department_id': self.department.id,
            'designation_id': designation.id,
            'joining_date': '2023-06-01',
            'employment_type': 'CONTRACT',
            'gender': 'FEMALE',
            'date_of_birth': '1990-05-15',
            'location': 'Chennai',
            'emergency_contact_name': 'Parent',
            'emergency_contact_phone': '9999999999',
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        emp = Employee.objects.get(employee_id='EMP200')
        self.assertEqual(emp.employment_type, 'CONTRACT')
        self.assertEqual(emp.gender, 'FEMALE')
        self.assertEqual(emp.location, 'Chennai')
        self.assertEqual(emp.emergency_contact_name, 'Parent')

    def test_employee_default_employment_type_is_full_time(self):
        self.auth(self.hr_user)
        data = {
            'employee_id': 'EMP201',
            'user_id': self.new_user.id,
            'first_name': 'John',
            'last_name': 'Smith',
            'email': self.new_user.email,
            'department_id': self.department.id,
            'joining_date': '2023-06-01',
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['employment_type'], 'FULL_TIME')

    def test_update_employee_as_hr(self):
        emp = self._create_employee(self.employee_user, 'EMP300')
        self.auth(self.hr_user)
        response = self.client.patch(f'{self.list_url}{emp.id}/', {'location': 'Bangalore'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp.refresh_from_db()
        self.assertEqual(emp.location, 'Bangalore')

    def test_destroy_employee_as_admin_deactivates(self):
        emp = self._create_employee(self.employee_user, 'EMP400')
        self.auth(self.admin_user)
        response = self.client.delete(f'{self.list_url}{emp.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp.refresh_from_db()
        self.assertEqual(emp.employment_status, 'EXITED')

    def test_destroy_employee_as_hr_forbidden(self):
        emp = self._create_employee(self.employee_user, 'EMP401')
        self.auth(self.hr_user)
        response = self.client.delete(f'{self.list_url}{emp.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_endpoint_returns_own_profile(self):
        emp = self._create_employee(self.employee_user, 'EMP500')
        self.auth(self.employee_user)
        response = self.client.get(f'{self.list_url}me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employee_id'], 'EMP500')

    def test_me_endpoint_no_profile_returns_404(self):
        self.auth(self.hr_user)
        response = self.client.get(f'{self.list_url}me/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reports_endpoint(self):
        mgr_emp = self._create_employee(self.manager_user, 'MGR001')
        sub_user = User.objects.create_user(email='sub@example.com', username='subuser', password='pass', role='EMPLOYEE')
        self._create_employee(sub_user, 'SUB001', manager=mgr_emp)
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}{mgr_emp.id}/reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data]
        self.assertIn('SUB001', emp_ids)

    def test_manager_info_endpoint(self):
        mgr_emp = self._create_employee(self.manager_user, 'MGR002')
        sub_user = User.objects.create_user(email='sub2@example.com', username='sub2user', password='pass', role='EMPLOYEE')
        sub_emp = self._create_employee(sub_user, 'SUB002', manager=mgr_emp)
        self.auth(self.employee_user)
        response = self.client.get(f'{self.list_url}{sub_emp.id}/manager/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employee_id'], 'MGR002')

    def test_manager_info_no_manager_returns_404(self):
        emp = self._create_employee(self.employee_user, 'EMP600')
        self.auth(self.employee_user)
        response = self.client.get(f'{self.list_url}{emp.id}/manager/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_self_manager_prevented_via_serializer(self):
        emp = self._create_employee(self.employee_user, 'EMP700')
        self.auth(self.hr_user)
        response = self.client.patch(f'{self.list_url}{emp.id}/', {'manager_id': emp.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_department(self):
        other_dept = Department.objects.create(name='Finance', code='FIN')
        fin_user = User.objects.create_user(email='fin@example.com', username='finuser', password='pass', role='EMPLOYEE')
        self._create_employee(fin_user, 'FIN001', department=other_dept)
        self._create_employee(self.employee_user, 'ENG001')
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?department={other_dept.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data['results']]
        self.assertIn('FIN001', emp_ids)
        self.assertNotIn('ENG001', emp_ids)

    def test_filter_by_employment_type(self):
        ct_user = User.objects.create_user(email='ct@example.com', username='ctuser', password='pass', role='EMPLOYEE')
        emp = Employee.objects.create(
            employee_id='CT001', user=ct_user, first_name='CT', last_name='User',
            email=ct_user.email, department=self.department, joining_date='2023-01-01',
            employment_type='CONTRACT',
        )
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?employment_type=CONTRACT')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data['results']]
        self.assertIn('CT001', emp_ids)

    def test_filter_by_status(self):
        self._create_employee(self.employee_user, 'EMP800')
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?status=ACTIVE')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for emp in response.data['results']:
            self.assertEqual(emp['employment_status'], 'ACTIVE')

    def test_search_by_name(self):
        srch_user = User.objects.create_user(email='srch@example.com', username='srchuser', password='pass', role='EMPLOYEE')
        emp = Employee.objects.create(
            employee_id='SRCH001', user=srch_user, first_name='Searchable', last_name='Person',
            email=srch_user.email, department=self.department, joining_date='2023-01-01',
        )
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?search=Searchable')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data['results']]
        self.assertIn('SRCH001', emp_ids)

    def test_search_by_email(self):
        srch_user = User.objects.create_user(email='findme@example.com', username='findmeuser', password='pass', role='EMPLOYEE')
        Employee.objects.create(
            employee_id='FIND001', user=srch_user, first_name='Find', last_name='Me',
            email=srch_user.email, department=self.department, joining_date='2023-01-01',
        )
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?search=findme@example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data['results']]
        self.assertIn('FIND001', emp_ids)

    def test_audit_log_created_on_employee_create(self):
        self.auth(self.hr_user)
        data = {
            'employee_id': 'AUDIT001',
            'user_id': self.new_user.id,
            'first_name': 'Audit',
            'last_name': 'Test',
            'email': self.new_user.email,
            'department_id': self.department.id,
            'joining_date': '2023-06-01',
        }
        self.client.post(self.list_url, data, format='json')
        self.assertTrue(AuditLog.objects.filter(action='EMPLOYEE_CREATED').exists())

    def test_audit_log_created_on_employee_update(self):
        emp = self._create_employee(self.employee_user, 'EMP_UPD')
        self.auth(self.hr_user)
        self.client.patch(f'{self.list_url}{emp.id}/', {'location': 'Mumbai'}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='EMPLOYEE_UPDATED').exists())

    def test_audit_log_created_on_employee_deactivate(self):
        emp = self._create_employee(self.employee_user, 'EMP_DEL')
        self.auth(self.admin_user)
        self.client.delete(f'{self.list_url}{emp.id}/')
        self.assertTrue(AuditLog.objects.filter(action='EMPLOYEE_DEACTIVATED').exists())

    def test_filter_by_designation(self):
        desig = Designation.objects.create(name='Sr Engineer', code='SR-ENG', department=self.department)
        sr_user = User.objects.create_user(email='sr@example.com', username='sruser', password='pass', role='EMPLOYEE')
        Employee.objects.create(
            employee_id='SR001', user=sr_user, first_name='Senior', last_name='Eng',
            email=sr_user.email, department=self.department, designation=desig, joining_date='2023-01-01',
        )
        self._create_employee(self.employee_user, 'JR001')
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}?designation={desig.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emp_ids = [e['employee_id'] for e in response.data['results']]
        self.assertIn('SR001', emp_ids)
        self.assertNotIn('JR001', emp_ids)

    def test_direct_reports_count_in_serializer(self):
        mgr_emp = self._create_employee(self.manager_user, 'MGR_COUNT')
        sub_user = User.objects.create_user(email='sub3@example.com', username='sub3user', password='pass', role='EMPLOYEE')
        self._create_employee(sub_user, 'SUB003', manager=mgr_emp)
        self.auth(self.manager_user)
        response = self.client.get(f'{self.list_url}{mgr_emp.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['direct_reports_count'], 1)
