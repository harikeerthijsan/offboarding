import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.employees.models import Employee, Department, Designation
from apps.skills.models import ReviewCycle, SkillDefinition, SkillSubmission


def auth(client, user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(user).access_token)}')


class SkillsSetup(APITestCase):
    def setUp(self):
        self.dept = Department.objects.create(name='GIS', code='GIS')
        self.desig = Designation.objects.create(name='GIS Analyst', department=self.dept)

        self.emp_user = User.objects.create_user(email='e@test.com', username='e', password='p', role='EMPLOYEE')
        self.employee = Employee.objects.create(
            employee_id='JSAN900', user=self.emp_user, first_name='Em', last_name='Ployee',
            email='e@test.com', department=self.dept, designation=self.desig, joining_date='2024-01-01',
        )
        # employee with incomplete profile (no dept/designation)
        self.bare_user = User.objects.create_user(email='b@test.com', username='b', password='p', role='EMPLOYEE')
        Employee.objects.create(employee_id='JSAN901', user=self.bare_user, first_name='Bare', last_name='User',
                                email='b@test.com', joining_date='2024-01-01')

        self.hr = User.objects.create_user(email='hr@test.com', username='hr', password='p', role='HR')

        today = timezone.localdate()
        self.cycle = ReviewCycle.objects.create(
            cycle_id='2026-H2', period_start=today - datetime.timedelta(days=5),
            period_end=today + datetime.timedelta(days=80), employee_due=today + datetime.timedelta(days=20),
            manager_due=today + datetime.timedelta(days=30), closure_target=today + datetime.timedelta(days=40),
        )
        SkillDefinition.objects.create(name='Python', tools=['Django'])


class SubmissionTest(SkillsSetup):
    def test_submit_dedupes_and_normalizes_years(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/submissions/', {
            'submit': True,
            'skills': [
                {'name': 'Python', 'years': 3.2, 'proficiency': 'Advanced'},
                {'name': 'python', 'years': 1},   # case-dup -> dropped
                {'name': 'GIS', 'years': 'bad'},   # invalid years -> null
            ],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        sk = r.data['submission']['skills']
        self.assertEqual(r.data['submission']['status'], 'submitted')
        self.assertEqual(len(sk), 2)             # dup dropped
        self.assertEqual(sk[0]['years'], 3.0)    # 3.2 -> nearest 0.5
        self.assertIsNone(sk[1]['years'])

    def test_submit_empty_rejected(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/submissions/', {'submit': True, 'skills': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_draft_allows_empty(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/submissions/', {'submit': False, 'skills': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['submission']['status'], 'draft')

    def test_incomplete_profile_blocked(self):
        auth(self.client, self.bare_user)
        r = self.client.post('/api/skills/submissions/', {'submit': True, 'skills': [{'name': 'X'}]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_412_PRECONDITION_FAILED)

    def test_me_reflects_active_cycle_state(self):
        auth(self.client, self.emp_user)
        self.client.post('/api/skills/submissions/', {'submit': True, 'skills': [{'name': 'Python'}]}, format='json')
        me = self.client.get('/api/skills/me/')
        active = [c for c in me.data['cycles'] if c['is_active']][0]
        self.assertEqual(active['state'], 'submitted')


class CatalogueAndStaffTest(SkillsSetup):
    def test_employee_sees_active_only(self):
        SkillDefinition.objects.create(name='Archived', active=False)
        auth(self.client, self.emp_user)
        names = [s['name'] for s in self.client.get('/api/skills/catalogue/').data['skills']]
        self.assertIn('Python', names)
        self.assertNotIn('Archived', names)

    def test_staff_sees_all_and_can_add(self):
        SkillDefinition.objects.create(name='Archived', active=False)
        auth(self.client, self.hr)
        names = [s['name'] for s in self.client.get('/api/skills/catalogue/').data['skills']]
        self.assertIn('Archived', names)
        r = self.client.post('/api/skills/catalogue/', {'name': 'Telecom', 'tools': 'OSP, ISP'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['skill']['tools'], ['OSP', 'ISP'])

    def test_duplicate_catalogue_rejected(self):
        auth(self.client, self.hr)
        r = self.client.post('/api/skills/catalogue/', {'name': 'python'}, format='json')  # exists (case-insensitive)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_employee_cannot_add_catalogue(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/catalogue/', {'name': 'X'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_team_and_counts(self):
        auth(self.client, self.emp_user)
        self.client.post('/api/skills/submissions/', {'submit': True, 'skills': [{'name': 'Python'}]}, format='json')
        auth(self.client, self.hr)
        team = self.client.get('/api/skills/team/')
        self.assertGreaterEqual(len(team.data['team']), 2)
        counts = self.client.get('/api/skills/cycles/').data['cycles'][0]['counts']
        self.assertEqual(counts['submitted'], 1)

    def test_employee_no_counts(self):
        auth(self.client, self.emp_user)
        self.assertNotIn('counts', self.client.get('/api/skills/cycles/').data['cycles'][0])

    def test_employee_cannot_view_team(self):
        auth(self.client, self.emp_user)
        self.assertEqual(self.client.get('/api/skills/team/').status_code, status.HTTP_403_FORBIDDEN)


class CycleManagementTest(SkillsSetup):
    def test_staff_create_edit_delete_cycle(self):
        auth(self.client, self.hr)
        r = self.client.post('/api/skills/cycles/', {
            'cycle_id': '2027-H1', 'period_start': '2027-01-01', 'period_end': '2027-06-30',
            'employee_due': '2027-02-15', 'manager_due': '2027-02-28', 'closure_target': '2027-03-15',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        cid = r.data['id']
        p = self.client.patch(f'/api/skills/cycles/{cid}/', {'notes': 'go'}, format='json')
        self.assertEqual(p.status_code, status.HTTP_200_OK)
        self.assertEqual(p.data['notes'], 'go')
        d = self.client.delete(f'/api/skills/cycles/{cid}/')
        self.assertEqual(d.status_code, status.HTTP_204_NO_CONTENT)

    def test_employee_cannot_create_cycle(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/cycles/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cycles_list_includes_id(self):
        auth(self.client, self.hr)
        rows = self.client.get('/api/skills/cycles/').data['cycles']
        self.assertTrue(all('id' in c for c in rows))


class ExportTest(SkillsSetup):
    def test_staff_export_returns_xlsx(self):
        auth(self.client, self.emp_user)
        self.client.post('/api/skills/submissions/', {'submit': True, 'skills': [{'name': 'Python', 'years': 2}]}, format='json')
        auth(self.client, self.hr)
        r = self.client.get('/api/skills/export/?status=all')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertGreater(len(r.content), 2000)

    def test_staff_submissions_list_filters(self):
        auth(self.client, self.emp_user)
        self.client.post('/api/skills/submissions/', {'submit': True, 'skills': [{'name': 'Python'}]}, format='json')
        auth(self.client, self.hr)
        self.assertEqual(len(self.client.get('/api/skills/submissions/all/?status=submitted').data['submissions']), 1)
        self.assertEqual(len(self.client.get('/api/skills/submissions/all/?status=draft').data['submissions']), 0)

    def test_employee_cannot_export(self):
        auth(self.client, self.emp_user)
        self.assertEqual(self.client.get('/api/skills/export/').status_code, status.HTTP_403_FORBIDDEN)
