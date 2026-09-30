"""Phase 10 — cross-cutting production-readiness tests: health, IDOR, negative
security, invalid transitions, and a codebase date-audit guard."""
import os
import re
import glob

from rest_framework import status

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.offboarding.models import ResignationRequest
from apps.offboarding.tests import ResignationWorkflowSetup, NoticePeriodSetup, auth


class HealthCheckTest(ResignationWorkflowSetup):
    def test_health_is_public_and_healthy(self):
        self.client.credentials()  # unauthenticated
        r = self.client.get('/api/health/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'healthy')


class AuthRequiredTest(ResignationWorkflowSetup):
    def test_protected_endpoints_reject_anonymous(self):
        self.client.credentials()
        for url in ['/api/offboarding/', '/api/employees/', '/api/notifications/',
                    '/api/offboarding/dashboard/']:
            r = self.client.get(url)
            self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED, url)

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        r = self.client.get('/api/offboarding/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class IDORTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        # rid owned by employee_user; employee_user2 is unrelated.
        self.rid = self._get_approved_resignation_id()

    def test_unrelated_employee_cannot_read_offboarding(self):
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_employee_cannot_read_summary(self):
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_id_returns_404_not_500(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/99999999/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class StatusPayloadInjectionTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()

    def test_employee_cannot_inject_status_on_create(self):
        # Fresh employee submitting a resignation cannot self-approve via payload.
        u = User.objects.create_user(email='inj@test.com', username='inj', password='pass', role='EMPLOYEE')
        Employee.objects.create(employee_id='INJ001', user=u, first_name='In', last_name='J',
                                email='inj@test.com', department=self.dept, designation=self.desig,
                                manager=self.manager_emp, joining_date='2021-01-01',
                                employment_status='ACTIVE')
        auth(self.client, u)
        r = self.client.post('/api/offboarding/', {
            'reason': 'BETTER_OPPORTUNITY', 'resignation_date': '2026-10-31',
            'status': 'APPROVED',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'DRAFT')  # injected status ignored

    def test_employee_cannot_bypass_to_final_approval(self):
        # Not HR → 403 regardless of prerequisites.
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                             {'final_review_date': '2026-12-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class InvalidTransitionBypassTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()

    def test_cannot_final_approve_with_incomplete_prereqs(self):
        # HR, but prerequisites not met → 400 with pending items (no bypass).
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                             {'final_review_date': '2026-12-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pending_items', r.data)

    def test_manager_action_requires_submitted(self):
        # rid is APPROVED already; manager action must be rejected.
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/manager-action/',
                             {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class DateAuditTest(ResignationWorkflowSetup):
    """Guards against automatic business-date behavior creeping into the codebase."""

    def test_no_business_date_defaults_in_models(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # apps/
        offenders = []
        # auto_now/auto_now_add are only permitted on technical timestamps.
        allowed = {'created_at', 'updated_at', 'timestamp', 'last_login', 'date_joined'}
        pattern = re.compile(r'(\w+)\s*=\s*models\.\w*Field\([^)]*auto_now')
        for path in glob.glob(os.path.join(base, '*', 'models.py')):
            with open(path, encoding='utf-8') as fh:
                for line in fh:
                    m = pattern.search(line)
                    if m and m.group(1) not in allowed:
                        offenders.append(f"{os.path.basename(os.path.dirname(path))}: {m.group(1)}")
        self.assertEqual(offenders, [], f"Unexpected auto date fields: {offenders}")
