import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
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


class ApprovalFlowTest(SkillsSetup):
    def setUp(self):
        super().setUp()
        from apps.notifications.models import Notification
        self.Notification = Notification
        self.mgr_user = User.objects.create_user(email='m@test.com', username='m', password='p', role='MANAGER')
        self.mgr_emp = Employee.objects.create(
            employee_id='JSAN800', user=self.mgr_user, first_name='Man', last_name='Ager',
            email='m@test.com', department=self.dept, designation=self.desig, joining_date='2023-01-01',
        )
        self.employee.manager = self.mgr_emp
        self.employee.save(update_fields=['manager'])

    def _submit(self):
        auth(self.client, self.emp_user)
        return self.client.post('/api/skills/submissions/',
                                {'submit': True, 'skills': [{'name': 'Python', 'proficiency': 'Advanced'}]},
                                format='json')

    def test_submit_notifies_reporting_manager(self):
        self._submit()
        self.assertTrue(self.Notification.objects.filter(
            recipient=self.mgr_user, notification_type='SKILLS_SUBMITTED').exists())

    def test_no_manager_routes_to_hr(self):
        # JSAN900 employee has no manager initially on the bare_user's side; use emp with manager removed.
        self.employee.manager = None
        self.employee.save(update_fields=['manager'])
        self._submit()
        self.assertTrue(self.Notification.objects.filter(
            recipient=self.hr, notification_type='SKILLS_SUBMITTED').exists())

    def test_manager_sees_and_approves(self):
        self._submit()
        sub = SkillSubmission.objects.get(user=self.emp_user)
        auth(self.client, self.mgr_user)
        appr = self.client.get('/api/skills/approvals/')
        self.assertEqual(appr.status_code, status.HTTP_200_OK)
        self.assertIn(sub.pk, [a['id'] for a in appr.data['approvals']])
        r = self.client.post(f'/api/skills/submissions/{sub.pk}/review/',
                             {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'approved')
        self.assertEqual(sub.reviewed_by, self.mgr_user)
        self.assertTrue(self.Notification.objects.filter(
            recipient=self.emp_user, notification_type='SKILLS_APPROVED').exists())

    def test_reject_requires_note_and_sets_needs_update(self):
        self._submit()
        sub = SkillSubmission.objects.get(user=self.emp_user)
        auth(self.client, self.mgr_user)
        no_note = self.client.post(f'/api/skills/submissions/{sub.pk}/review/',
                                   {'action': 'reject'}, format='json')
        self.assertEqual(no_note.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.client.post(f'/api/skills/submissions/{sub.pk}/review/',
                              {'action': 'reject', 'note': 'Add your tools'}, format='json')
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'rejected')
        self.assertTrue(self.Notification.objects.filter(
            recipient=self.emp_user, notification_type='SKILLS_CHANGES_REQUESTED').exists())

    def test_approved_submission_cannot_be_overwritten(self):
        self._submit()
        sub = SkillSubmission.objects.get(user=self.emp_user)
        auth(self.client, self.mgr_user)
        self.client.post(f'/api/skills/submissions/{sub.pk}/review/', {'action': 'approve'}, format='json')
        # employee tries to revert the recorded submission
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/submissions/',
                             {'submit': False, 'skills': [{'name': 'Overwrite'}]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'approved')
        self.assertEqual([s['name'] for s in sub.skills], ['Python'])

    def test_unrelated_manager_cannot_review(self):
        self._submit()
        sub = SkillSubmission.objects.get(user=self.emp_user)
        other = User.objects.create_user(email='o@test.com', username='o', password='p', role='MANAGER')
        Employee.objects.create(employee_id='JSAN801', user=other, first_name='Oth', last_name='Er',
                                email='o@test.com', department=self.dept, designation=self.desig, joining_date='2023-01-01')
        auth(self.client, other)
        r = self.client.post(f'/api/skills/submissions/{sub.pk}/review/', {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


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


class CalendarImportTest(SkillsSetup):
    CSV = (
        b'Cycle ID,Period Start,Period End,Employee Update Due,Manager Validation Due,Closure Target,Notes\n'
        b'2099-H1,01-Jan-2099,30-Jun-2099,15-Feb-2099,28-Feb-2099,15-Mar-2099,first\n'
        b'2099-H2,2099-07-01,2099-12-31,2099-08-15,2099-08-31,2099-09-15,\n'
        b'BADROW,01-Jan-2099,,15-Feb-2099,28-Feb-2099,15-Mar-2099,missing end\n'
    )

    def _file(self, name='calendar.csv', content=None):
        return SimpleUploadedFile(name, content or self.CSV, content_type='text/csv')

    def test_staff_import_upserts_and_skips_bad_rows(self):
        auth(self.client, self.hr)
        r = self.client.post('/api/skills/cycles/import/', {'file': self._file()}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['imported'], 2)
        self.assertEqual(len(r.data['skipped']), 1)
        c = ReviewCycle.objects.get(cycle_id='2099-H1')
        self.assertEqual(c.period_start, datetime.date(2099, 1, 1))
        self.assertEqual(c.notes, 'first')

    def test_reimport_is_idempotent(self):
        auth(self.client, self.hr)
        self.client.post('/api/skills/cycles/import/', {'file': self._file()}, format='multipart')
        self.client.post('/api/skills/cycles/import/', {'file': self._file()}, format='multipart')
        self.assertEqual(ReviewCycle.objects.filter(cycle_id__startswith='2099').count(), 2)

    def test_employee_cannot_import(self):
        auth(self.client, self.emp_user)
        r = self.client.post('/api/skills/cycles/import/', {'file': self._file()}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_file_without_cycle_id_rejected(self):
        auth(self.client, self.hr)
        bad = self._file('x.csv', b'foo,bar\n1,2\n')
        r = self.client.post('/api/skills/cycles/import/', {'file': bad}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
