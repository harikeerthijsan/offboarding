from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.employees.models import Department, Designation, Employee
from apps.notifications.models import Notification
from apps.offboarding.models import ResignationRequest, NoticePeriod


def make_token(user):
    return str(RefreshToken.for_user(user).access_token)


def auth(client, user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {make_token(user)}')


class ResignationWorkflowSetup(APITestCase):
    def setUp(self):
        # Users
        self.admin_user = User.objects.create_user(
            email='admin@test.com', username='admin', password='pass',
            role='ADMIN', first_name='Admin', last_name='User',
        )
        self.hr_user = User.objects.create_user(
            email='hr@test.com', username='hr', password='pass',
            role='HR', first_name='HR', last_name='User',
        )
        self.manager_user = User.objects.create_user(
            email='manager@test.com', username='manager', password='pass',
            role='MANAGER', first_name='Mgr', last_name='User',
        )
        self.employee_user = User.objects.create_user(
            email='emp@test.com', username='emp', password='pass',
            role='EMPLOYEE', first_name='Emp', last_name='User',
        )
        self.employee_user2 = User.objects.create_user(
            email='emp2@test.com', username='emp2', password='pass',
            role='EMPLOYEE', first_name='Emp2', last_name='User',
        )

        # Org
        self.dept = Department.objects.create(name='Engineering', code='ENG')
        self.desig = Designation.objects.create(name='Engineer', code='ENG01', department=self.dept)

        # Manager employee record
        self.manager_emp = Employee.objects.create(
            employee_id='MGR001', user=self.manager_user,
            first_name='Mgr', last_name='User',
            email='manager@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2020-01-01', employment_status='ACTIVE',
        )

        # Employee record (with manager)
        self.employee = Employee.objects.create(
            employee_id='EMP001', user=self.employee_user,
            first_name='Emp', last_name='User',
            email='emp@test.com',
            department=self.dept, designation=self.desig,
            manager=self.manager_emp,
            joining_date='2021-01-01', employment_status='ACTIVE',
        )

        # Another employee without manager
        self.employee2 = Employee.objects.create(
            employee_id='EMP002', user=self.employee_user2,
            first_name='Emp2', last_name='User',
            email='emp2@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2021-01-01', employment_status='ACTIVE',
        )

        self.valid_payload = {
            'reason': 'BETTER_OPPORTUNITY',
            'resignation_date': '2026-10-31',
            'notes': 'Moving to a new role.',
        }


class CreateResignationTest(ResignationWorkflowSetup):
    def test_employee_can_create_draft(self):
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'DRAFT')

    def test_invalid_reason_rejected(self):
        auth(self.client, self.employee_user)
        payload = dict(self.valid_payload, reason='NOT_A_REASON')
        r = self.client.post('/api/offboarding/', payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_active_resignation_blocked(self):
        auth(self.client, self.employee_user)
        self.client.post('/api/offboarding/', self.valid_payload, format='json')
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class SubmitResignationTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.resignation_id = r.data['id']

    def test_employee_can_submit(self):
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'SUBMITTED')

    def test_employee_status_becomes_offboarding(self):
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'OFFBOARDING')

    def test_manager_notified_on_submit(self):
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        notif = Notification.objects.filter(
            recipient=self.manager_user, notification_type='ACTION_REQUIRED'
        )
        self.assertTrue(notif.exists())

    def test_cannot_submit_twice(self):
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_employee_cannot_submit(self):
        auth(self.client, self.employee_user2)
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class ManagerActionTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        # Create and submit
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.resignation_id = r.data['id']
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')

    def test_manager_can_approve(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve', 'notes': 'Approved.'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'MANAGER_REVIEW')

    def test_manager_can_reject(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'reject', 'notes': 'Please stay.'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'REJECTED')

    def test_reject_reverts_employee_to_active(self):
        auth(self.client, self.manager_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'reject', 'notes': 'No'},
            format='json',
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'ACTIVE')

    def test_non_manager_cannot_use_manager_endpoint(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_manager_cannot_act(self):
        # Create another manager not linked to this employee
        other_mgr_user = User.objects.create_user(
            email='othermgr@test.com', username='othermgr', password='pass', role='MANAGER',
        )
        Employee.objects.create(
            employee_id='MGR002', user=other_mgr_user,
            first_name='Other', last_name='Mgr',
            email='othermgr@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2020-01-01',
        )
        auth(self.client, other_mgr_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_action_rejected(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'maybe'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_approve_notifies_hr(self):
        auth(self.client, self.manager_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )
        notif = Notification.objects.filter(
            recipient=self.hr_user, notification_type='ACTION_REQUIRED'
        )
        self.assertTrue(notif.exists())


class HRActionTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.resignation_id = r.data['id']
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        auth(self.client, self.manager_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )

    def test_hr_can_approve(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve', 'notes': 'All good.'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'APPROVED')

    def test_hr_can_reject(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'reject', 'notes': 'Not processed.'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'REJECTED')

    def test_hr_reject_reverts_employee_to_active(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'reject', 'notes': 'No'},
            format='json',
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'ACTIVE')

    def test_employee_cannot_use_hr_endpoint(self):
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_use_hr_endpoint(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_approve_notifies_employee(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        notif = Notification.objects.filter(
            recipient=self.employee_user, notification_type='RESIGNATION_APPROVED'
        )
        self.assertTrue(notif.exists())

    def test_wrong_status_for_hr_action(self):
        # Try HR action on a SUBMITTED (not MANAGER_REVIEW) request
        auth(self.client, self.employee_user)
        r2 = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        # Duplicate blocked, so use the existing one - let's create a fresh employee
        emp3_user = User.objects.create_user(
            email='emp3@test.com', username='emp3', password='pass', role='EMPLOYEE',
        )
        emp3 = Employee.objects.create(
            employee_id='EMP003', user=emp3_user,
            first_name='Emp3', last_name='User', email='emp3@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2022-01-01', employment_status='ACTIVE',
        )
        auth(self.client, emp3_user)
        r3 = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        rid3 = r3.data['id']
        self.client.post(f'/api/offboarding/{rid3}/submit/')

        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid3}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class CancelResignationTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.resignation_id = r.data['id']

    def test_employee_can_cancel_draft(self):
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/cancel/',
            {'reason': 'Changed my mind'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'CANCELLED')

    def test_employee_can_cancel_submitted(self):
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/cancel/',
            {'reason': 'Changed my mind'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'CANCELLED')

    def test_cannot_cancel_approved(self):
        # Advance to APPROVED
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        auth(self.client, self.manager_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/cancel/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_employee_cannot_cancel(self):
        auth(self.client, self.employee_user2)
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/cancel/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class ListResignationsTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        auth(self.client, self.employee_user)
        self.client.post('/api/offboarding/', self.valid_payload, format='json')

    def test_employee_sees_own(self):
        auth(self.client, self.employee_user)
        r = self.client.get('/api/offboarding/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_employee2_sees_nothing(self):
        auth(self.client, self.employee_user2)
        r = self.client.get('/api/offboarding/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 0)

    def test_manager_sees_direct_reports(self):
        auth(self.client, self.manager_user)
        r = self.client.get('/api/offboarding/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_hr_sees_all(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.data), 1)

    def test_status_filter(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/?status=DRAFT')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        for item in r.data:
            self.assertEqual(item['status'], 'DRAFT')


class InvalidTransitionTest(ResignationWorkflowSetup):
    def setUp(self):
        super().setUp()
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.resignation_id = r.data['id']

    def test_manager_cannot_act_on_draft(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/manager-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hr_cannot_act_on_submitted(self):
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.resignation_id}/hr-action/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_again_after_submit(self):
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        r = self.client.post(f'/api/offboarding/{self.resignation_id}/submit/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class NotificationTests(ResignationWorkflowSetup):
    def test_unread_count(self):
        auth(self.client, self.employee_user)
        self.client.post('/api/offboarding/', self.valid_payload, format='json')
        auth(self.client, self.manager_user)
        r = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('unread_count', r.data)

    def test_mark_all_read(self):
        auth(self.client, self.employee_user)
        r2 = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        rid = r2.data['id']
        self.client.post(f'/api/offboarding/{rid}/submit/')
        # Manager should have a notification
        auth(self.client, self.manager_user)
        r = self.client.post('/api/notifications/read-all/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # Verify count is 0
        r2 = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(r2.data['unread_count'], 0)


# ─── Phase 4: Notice Period Tests ────────────────────────────────────────────


class NoticePeriodSetup(ResignationWorkflowSetup):
    """Helper base: advances a resignation all the way to APPROVED."""

    def setUp(self):
        super().setUp()
        self._np_counter = 0

    def _get_approved_resignation_id(self, employee_user=None, manager_user=None):
        """Advance a resignation to APPROVED. The first call uses the primary
        self.employee_user (owner) / self.manager_user. Subsequent calls create a
        fresh employee so the same person is never blocked by a duplicate-active check.
        """
        if employee_user is None:
            self._np_counter += 1
            if self._np_counter == 1:
                employee_user = self.employee_user
                manager_user = self.manager_user
            else:
                n = self._np_counter
                employee_user = User.objects.create_user(
                    email=f'npemp{n}@test.com', username=f'npemp{n}', password='pass',
                    role='EMPLOYEE', first_name=f'NP{n}', last_name='User',
                )
                Employee.objects.create(
                    employee_id=f'NPEMP{n:03d}', user=employee_user,
                    first_name=f'NP{n}', last_name='User', email=f'npemp{n}@test.com',
                    department=self.dept, designation=self.desig,
                    manager=self.manager_emp,
                    joining_date='2021-01-01', employment_status='ACTIVE',
                )
                manager_user = self.manager_user

        auth(self.client, employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        rid = r.data['id']
        self.client.post(f'/api/offboarding/{rid}/submit/')
        auth(self.client, manager_user or self.manager_user)
        self.client.post(
            f'/api/offboarding/{rid}/manager-action/',
            {'action': 'approve'}, format='json',
        )
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{rid}/hr-action/',
            {'action': 'approve'}, format='json',
        )
        return rid


class NoticePeriodCreateTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()

    def test_hr_can_create_empty_notice_period(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_create_transitions_resignation_to_notice_period(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        resignation = ResignationRequest.objects.get(pk=self.rid)
        self.assertEqual(resignation.status, 'NOTICE_PERIOD')

    def test_all_date_fields_null_by_default(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertIsNone(r.data['notice_period_start_date'])
        self.assertIsNone(r.data['notice_period_days'])
        self.assertIsNone(r.data['expected_last_working_day'])
        self.assertIsNone(r.data['actual_last_working_day'])
        self.assertIsNone(r.data['early_release_date'])
        self.assertIsNone(r.data['notice_extension_date'])

    def test_hr_can_create_with_manual_dates(self):
        auth(self.client, self.hr_user)
        payload = {
            'notice_period_start_date': '2026-11-01',
            'notice_period_days': 60,
            'expected_last_working_day': '2026-12-31',
        }
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['notice_period_start_date'], '2026-11-01')
        self.assertEqual(r.data['notice_period_days'], 60)
        self.assertEqual(r.data['expected_last_working_day'], '2026-12-31')

    def test_employee_cannot_create_notice_period(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_create_notice_period(self):
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_create_if_not_approved_status(self):
        # Create a DRAFT resignation (a fresh employee)
        emp3_user = User.objects.create_user(
            email='emp3np@test.com', username='emp3np', password='pass', role='EMPLOYEE',
        )
        Employee.objects.create(
            employee_id='EMP3NP', user=emp3_user,
            first_name='Emp3', last_name='NP', email='emp3np@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2022-01-01', employment_status='ACTIVE',
        )
        auth(self.client, emp3_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        draft_rid = r.data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{draft_rid}/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_duplicate_notice_period(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_relationship_rejected(self):
        auth(self.client, self.hr_user)
        payload = {
            'notice_period_start_date': '2026-12-31',
            'expected_last_working_day': '2026-11-01',
        }
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notice_period_days_stored_as_entered_not_calculated(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'expected_last_working_day': '2026-12-31', 'notice_period_days': 99},
            format='json',
        )
        self.assertEqual(r.data['notice_period_days'], 99)

    def test_notice_period_start_status_is_active(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        self.assertEqual(r.data['status'], 'ACTIVE')

    def test_notice_period_notifies_employee(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')
        notif = Notification.objects.filter(
            recipient=self.employee_user, notification_type='STATUS_UPDATE',
        )
        self.assertTrue(notif.exists())


class NoticePeriodUpdateTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')

    def test_hr_can_update_notice_period(self):
        auth(self.client, self.hr_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'notice_period_days': 30},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['notice_period_start_date'], '2026-11-01')
        self.assertEqual(r.data['notice_period_days'], 30)

    def test_employee_cannot_update_notice_period(self):
        auth(self.client, self.employee_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_days': 30},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_date_cross_validation_on_update(self):
        auth(self.client, self.hr_user)
        # Set start date first
        self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-12-01'},
            format='json',
        )
        # Now set expected LWD before start date — should fail
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'expected_last_working_day': '2026-11-01'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notice_period_days_not_auto_calculated_on_update(self):
        auth(self.client, self.hr_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {
                'notice_period_start_date': '2026-11-01',
                'expected_last_working_day': '2026-12-31',
                'notice_period_days': 99,
            },
            format='json',
        )
        self.assertEqual(r.data['notice_period_days'], 99)

    def test_get_notice_period(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('status', r.data)

    def test_get_returns_404_if_no_notice_period(self):
        rid2 = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{rid2}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class EarlyReleaseTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')

    def test_employee_can_request_early_release(self):
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job starts sooner'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'EARLY_RELEASE_REQUESTED')

    def test_request_without_reason_rejected(self):
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': ''},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_request_twice(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'First request'},
            format='json',
        )
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'Second request'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hr_can_approve_with_date(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'},
            format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'approve', 'early_release_date': '2026-11-15', 'notes': 'Approved'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['early_release_approved'])
        self.assertEqual(r.data['early_release_date'], '2026-11-15')
        self.assertEqual(r.data['status'], 'ACTIVE')

    def test_approve_without_date_rejected(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'},
            format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hr_can_reject_early_release(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'},
            format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'reject', 'notes': 'Cannot release early'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['early_release_approved'])
        self.assertEqual(r.data['status'], 'ACTIVE')

    def test_employee_cannot_approve_early_release(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'},
            format='json',
        )
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'approve', 'early_release_date': '2026-11-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_action_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'maybe'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_review_when_no_pending_request_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'approve', 'early_release_date': '2026-11-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_early_release_notifies_hr(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'},
            format='json',
        )
        notif = Notification.objects.filter(
            recipient=self.hr_user, notification_type='ACTION_REQUIRED',
        )
        self.assertTrue(notif.exists())

    def test_manager_cannot_request_early_release(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'On behalf'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_cannot_request_early_release(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'On behalf'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_rerequest_after_approval(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'}, format='json',
        )
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'approve', 'early_release_date': '2026-11-15'}, format='json',
        )
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'Again'}, format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_while_early_release_pending(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'}, format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'}, format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_extend_while_early_release_pending(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job'}, format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31', 'extension_reason': 'x'}, format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class NoticeExtensionTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'expected_last_working_day': '2026-12-15'},
            format='json',
        )

    def test_hr_can_record_extension(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31', 'extension_reason': 'Project handover'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['notice_extension_date'], '2026-12-31')
        self.assertEqual(r.data['extension_reason'], 'Project handover')

    def test_extension_missing_reason_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extension_missing_date_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'extension_reason': 'Needs more time'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_record_extension(self):
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31', 'extension_reason': 'My reason'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_extension_recorded_by_is_set(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31', 'extension_reason': 'Project handover'},
            format='json',
        )
        self.assertIsNotNone(r.data['extension_recorded_by_name'])

    def test_extension_notifies_employee(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-extension/',
            {'notice_extension_date': '2026-12-31', 'extension_reason': 'Project handover'},
            format='json',
        )
        notif = Notification.objects.filter(
            recipient=self.employee_user, notification_type='STATUS_UPDATE',
        )
        self.assertTrue(notif.exists())


class CompleteNoticePeriodTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/notice-period/', {}, format='json')

    def test_hr_can_complete_with_actual_lwd(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'COMPLETED')

    def test_complete_transitions_resignation_to_completed(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        resignation = ResignationRequest.objects.get(pk=self.rid)
        self.assertEqual(resignation.status, 'COMPLETED')

    def test_complete_sets_employee_to_exited(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'EXITED')

    def test_complete_without_actual_lwd_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_twice(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_complete_notice_period(self):
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_complete_notice_period(self):
        auth(self.client, self.manager_user)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_completion_notifies_employee(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        notif = Notification.objects.filter(
            recipient=self.employee_user,
            notification_type='STATUS_UPDATE',
            title='Offboarding complete',
        )
        self.assertTrue(notif.exists())

    def test_notice_period_status_set_to_completed(self):
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-11-30'},
            format='json',
        )
        np = NoticePeriod.objects.get(resignation_id=self.rid)
        self.assertEqual(np.status, 'COMPLETED')
        self.assertEqual(str(np.actual_last_working_day), '2026-11-30')


class NoticePeriodPermissionTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'notice_period_days': 60},
            format='json',
        )

    def test_employee_can_read_own_notice_period(self):
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_manager_can_read_direct_report_notice_period(self):
        auth(self.client, self.manager_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unrelated_employee_cannot_read_notice_period(self):
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_can_read_any_notice_period(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_read(self):
        self.client.credentials()
        r = self.client.get(f'/api/offboarding/{self.rid}/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unrelated_employee_cannot_early_release_request(self):
        auth(self.client, self.employee_user2)
        r = self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'No reason'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class EndToEndFlowTest(NoticePeriodSetup):
    """Full lifecycle in sequence — catches flow breaks unit tests miss."""

    def test_happy_path_draft_to_completed(self):
        # 1. Employee creates DRAFT
        auth(self.client, self.employee_user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rid = r.data['id']
        self.assertEqual(r.data['status'], 'DRAFT')

        # 2. Submit → SUBMITTED, employee OFFBOARDING
        r = self.client.post(f'/api/offboarding/{rid}/submit/')
        self.assertEqual(r.data['status'], 'SUBMITTED')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'OFFBOARDING')

        # 3. Manager approve → MANAGER_REVIEW
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/offboarding/{rid}/manager-action/', {'action': 'approve'}, format='json')
        self.assertEqual(r.data['status'], 'MANAGER_REVIEW')

        # 4. HR approve → APPROVED
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/hr-action/', {'action': 'approve'}, format='json')
        self.assertEqual(r.data['status'], 'APPROVED')

        # 5. HR starts notice period → NOTICE_PERIOD
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/',
            {'notice_period_start_date': '2026-10-01', 'notice_period_days': 60,
             'expected_last_working_day': '2026-11-30'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ResignationRequest.objects.get(pk=rid).status, 'NOTICE_PERIOD')

        # 6. Employee requests early release → EARLY_RELEASE_REQUESTED
        auth(self.client, self.employee_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/early-release/',
            {'action': 'request', 'reason': 'New job starts sooner'},
            format='json',
        )
        self.assertEqual(r.data['status'], 'EARLY_RELEASE_REQUESTED')

        # 7. HR rejects early release → back to ACTIVE, resignation still NOTICE_PERIOD
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/early-release/',
            {'action': 'reject', 'notes': 'Handover incomplete'},
            format='json',
        )
        self.assertEqual(r.data['status'], 'ACTIVE')
        self.assertEqual(ResignationRequest.objects.get(pk=rid).status, 'NOTICE_PERIOD')

        # 8. HR records an extension
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-extension/',
            {'notice_extension_date': '2026-12-15', 'extension_reason': 'Project handover'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        # 9. HR completes → COMPLETED, employee EXITED
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/complete/',
            {'actual_last_working_day': '2026-12-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'COMPLETED')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'EXITED')

        # 10. Post-completion: cannot update, extend, or re-complete
        r = self.client.patch(f'/api/offboarding/{rid}/notice-period/',
                              {'notice_comments': 'late edit'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(f'/api/offboarding/{rid}/notice-extension/',
                            {'notice_extension_date': '2027-01-01', 'extension_reason': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(f'/api/offboarding/{rid}/notice-period/complete/',
                            {'actual_last_working_day': '2026-12-16'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_early_release_approved_then_complete(self):
        rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{rid}/notice-period/', {}, format='json')
        # employee requests
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{rid}/early-release/',
                        {'action': 'request', 'reason': 'sooner'}, format='json')
        # HR approves with date
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/early-release/',
                            {'action': 'approve', 'early_release_date': '2026-10-20'}, format='json')
        self.assertEqual(r.data['status'], 'ACTIVE')
        self.assertTrue(r.data['early_release_approved'])
        # Complete using early release date as actual LWD
        r = self.client.post(f'/api/offboarding/{rid}/notice-period/complete/',
                            {'actual_last_working_day': '2026-10-20'}, format='json')
        self.assertEqual(r.data['status'], 'COMPLETED')

    def test_cannot_start_notice_period_then_cancel(self):
        # Once in NOTICE_PERIOD, cancel should be blocked (not a valid transition)
        rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{rid}/notice-period/', {}, format='json')
        r = self.client.post(f'/api/offboarding/{rid}/cancel/', {'reason': 'oops'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notice_period_endpoints_404_for_missing_resignation(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/999999/notice-period/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        r = self.client.post('/api/offboarding/999999/notice-period/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        r = self.client.post('/api/offboarding/999999/notice-period/complete/',
                            {'actual_last_working_day': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_early_release_before_notice_period_started(self):
        # APPROVED but no notice period yet
        rid = self._get_approved_resignation_id()
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{rid}/early-release/',
                            {'action': 'request', 'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_extend_before_notice_period(self):
        rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/notice-extension/',
                            {'notice_extension_date': '2026-12-01', 'extension_reason': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_before_notice_period(self):
        rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/notice-period/complete/',
                            {'actual_last_working_day': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class NoticePeriodDateValidationTest(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01'},
            format='json',
        )

    def test_actual_lwd_before_start_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'actual_last_working_day': '2026-10-01'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expected_lwd_before_start_rejected_on_create(self):
        rid2 = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid2}/notice-period/',
            {'notice_period_start_date': '2026-12-01', 'expected_last_working_day': '2026-11-01'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dates_are_not_auto_populated(self):
        rid2 = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid2}/notice-period/', {}, format='json')
        self.assertIsNone(r.data['notice_period_start_date'])
        self.assertIsNone(r.data['expected_last_working_day'])
        self.assertIsNone(r.data['actual_last_working_day'])

    def test_backend_never_auto_sets_notice_period_days(self):
        rid2 = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid2}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'expected_last_working_day': '2026-12-31'},
            format='json',
        )
        self.assertIsNone(r.data['notice_period_days'])


class NoticePeriodEarlyReliefDateTest(NoticePeriodSetup):
    """HR-entered optional early relieving date on the notice period form.

    Submitted via the write-only `early_relief_date` API field, which maps to
    the model's early_release_* fields (recorded as an HR-approved early release).
    """

    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        auth(self.client, self.hr_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'expected_last_working_day': '2026-12-31'},
            format='json',
        )

    def _fresh_rid(self):
        return self._get_approved_resignation_id()

    def test_create_with_early_relief_date_records_approved_early_release(self):
        rid = self._fresh_rid()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/',
            {
                'notice_period_start_date': '2026-11-01',
                'expected_last_working_day': '2026-12-31',
                'early_relief_date': '2026-11-15',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['early_release_date'], '2026-11-15')
        self.assertTrue(r.data['early_release_approved'])
        self.assertEqual(r.data['status'], 'ACTIVE')
        self.assertEqual(r.data['early_release_reviewed_by_name'], 'HR User')

    def test_create_without_early_relief_date_leaves_early_release_empty(self):
        rid = self._fresh_rid()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/notice-period/', {}, format='json')
        self.assertIsNone(r.data['early_release_date'])
        self.assertIsNone(r.data['early_release_approved'])

    def test_create_with_explicit_null_early_relief_date_accepted(self):
        # The frontend always sends the key; an empty value must mean "no early release".
        rid = self._fresh_rid()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/',
            {'early_relief_date': None},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(r.data['early_release_date'])

    def test_update_sets_early_relief_date(self):
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-11-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['early_release_date'], '2026-11-15')
        self.assertTrue(r.data['early_release_approved'])
        self.assertEqual(r.data['early_release_reviewed_by_name'], 'HR User')

    def test_update_with_explicit_null_clears_recorded_early_relief(self):
        self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-11-15'},
            format='json',
        )
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': None},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data['early_release_date'])
        self.assertIsNone(r.data['early_release_approved'])

    def test_update_without_key_does_not_touch_early_release(self):
        self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-11-15'},
            format='json',
        )
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'notice_comments': 'Unrelated edit'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['early_release_date'], '2026-11-15')

    def test_update_explicit_null_with_no_early_release_is_noop(self):
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': None},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data['early_release_date'])

    def test_early_relief_before_start_rejected_on_create(self):
        rid = self._fresh_rid()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/',
            {'notice_period_start_date': '2026-11-01', 'early_relief_date': '2026-10-01'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_early_relief_after_expected_lwd_rejected_on_create(self):
        rid = self._fresh_rid()
        auth(self.client, self.hr_user)
        r = self.client.post(
            f'/api/offboarding/{rid}/notice-period/',
            {'expected_last_working_day': '2026-12-31', 'early_relief_date': '2027-01-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_early_relief_before_start_rejected_on_update(self):
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-10-01'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_early_relief_after_expected_lwd_rejected_on_update(self):
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2027-01-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_records_early_relief_resolving_pending_request(self):
        auth(self.client, self.employee_user)
        self.client.post(
            f'/api/offboarding/{self.rid}/early-release/',
            {'action': 'request', 'reason': 'New job starts sooner'},
            format='json',
        )
        auth(self.client, self.hr_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-11-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'ACTIVE')
        self.assertEqual(r.data['early_release_date'], '2026-11-15')
        self.assertTrue(r.data['early_release_approved'])

    def test_employee_cannot_set_early_relief_date(self):
        auth(self.client, self.employee_user)
        r = self.client.patch(
            f'/api/offboarding/{self.rid}/notice-period/',
            {'early_relief_date': '2026-11-15'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_resignation_detail_exposes_policy_months(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # Test employee joined 2021-01-01 → tenure well over 6 months → 2-month policy.
        self.assertEqual(r.data['notice_policy_months'], 2)

    def test_policy_months_is_one_for_under_six_months_tenure(self):
        user = User.objects.create_user(
            email='short@test.com', username='short', password='pass',
            role='EMPLOYEE', first_name='Short', last_name='Tenure',
        )
        Employee.objects.create(
            employee_id='SHORT001', user=user,
            first_name='Short', last_name='Tenure', email='short@test.com',
            department=self.dept, designation=self.desig, manager=self.manager_emp,
            joining_date=(timezone.localdate() - timedelta(days=60)).isoformat(),
            employment_status='ACTIVE',
        )
        auth(self.client, user)
        r = self.client.post('/api/offboarding/', self.valid_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        auth(self.client, self.hr_user)
        r = self.client.get(f"/api/offboarding/{r.data['id']}/")
        self.assertEqual(r.data['notice_policy_months'], 1)


# ─── Phase 5: Knowledge Transfer Tests ───────────────────────────────────────

from apps.offboarding.models import Project, KnowledgeTransfer  # noqa: E402


class KTSetup(NoticePeriodSetup):
    """Approved resignation + a valid active receiver in the same department."""

    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()  # owned by self.employee_user / self.manager_user

        # Receiver — an active employee (not the offboarding employee)
        self.receiver_user = User.objects.create_user(
            email='receiver@test.com', username='receiver', password='pass',
            role='EMPLOYEE', first_name='Rec', last_name='Eiver',
        )
        self.receiver_emp = Employee.objects.create(
            employee_id='RCV001', user=self.receiver_user,
            first_name='Rec', last_name='Eiver', email='receiver@test.com',
            department=self.dept, designation=self.desig,
            manager=self.manager_emp,
            joining_date='2021-06-01', employment_status='ACTIVE',
        )
        # An inactive employee (invalid as receiver)
        self.exited_user = User.objects.create_user(
            email='exited@test.com', username='exited', password='pass', role='EMPLOYEE',
        )
        self.exited_emp = Employee.objects.create(
            employee_id='EXT001', user=self.exited_user,
            first_name='Ex', last_name='Ited', email='exited@test.com',
            department=self.dept, designation=self.desig,
            joining_date='2019-01-01', employment_status='EXITED',
        )
        self.project = Project.objects.create(
            name='Employee Management System', code='EMS', department=self.dept,
        )
        self.kt_payload = {
            'title': 'Handover production deployments',
            'description': 'Transfer deployment knowledge.',
            'project': self.project.id,
            'responsibility': 'Manage production deployments and backend API maintenance.',
            'receiver': self.receiver_emp.id,
            'priority': 'HIGH',
        }

    def _create_kt(self, actor=None, **overrides):
        auth(self.client, actor or self.hr_user)
        payload = dict(self.kt_payload, **overrides)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/', payload, format='json')
        return r

    def _kt_to_manager_review(self):
        """Create a KT and advance it through start→submit→receiver-accept to MANAGER_REVIEW."""
        r = self._create_kt(start_date='2026-10-01', target_completion_date='2026-10-20')
        kt_id = r.data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/submit/')
        auth(self.client, self.receiver_user)
        self.client.post(f'/api/kt/{kt_id}/receiver-action/', {'action': 'accept'}, format='json')
        return kt_id


class ProjectTest(KTSetup):
    def test_manager_can_create_project(self):
        auth(self.client, self.manager_user)
        r = self.client.post('/api/projects/', {'name': 'New Proj', 'code': 'NP1'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_hr_can_create_project(self):
        auth(self.client, self.hr_user)
        r = self.client.post('/api/projects/', {'name': 'HR Proj', 'code': 'HRP'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_employee_cannot_create_project(self):
        auth(self.client, self.employee_user)
        r = self.client.post('/api/projects/', {'name': 'X', 'code': 'X1'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_code_rejected(self):
        auth(self.client, self.hr_user)
        r = self.client.post('/api/projects/', {'name': 'Dup', 'code': 'EMS'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_projects(self):
        auth(self.client, self.employee_user)
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.data), 1)


class KTCreateTest(KTSetup):
    def test_manager_can_create_kt(self):
        r = self._create_kt(actor=self.manager_user)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'PENDING')

    def test_hr_can_create_kt(self):
        r = self._create_kt(actor=self.hr_user)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_employee_cannot_create_kt(self):
        r = self._create_kt(actor=self.employee_user)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_to_is_offboarding_employee(self):
        r = self._create_kt()
        self.assertEqual(r.data['assigned_to'], self.employee.id)

    def test_assigned_to_cannot_be_overridden_by_payload(self):
        # Attempt to inject assigned_to — server must ignore it
        r = self._create_kt(assigned_to=self.receiver_emp.id)
        self.assertEqual(r.data['assigned_to'], self.employee.id)

    def test_status_cannot_be_set_by_payload(self):
        r = self._create_kt(status='COMPLETED')
        self.assertEqual(r.data['status'], 'PENDING')

    def test_receiver_must_be_active(self):
        r = self._create_kt(receiver=self.exited_emp.id)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_be_own_receiver(self):
        r = self._create_kt(receiver=self.employee.id)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_receiver_id_rejected(self):
        r = self._create_kt(receiver=999999)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_target_before_start_rejected(self):
        r = self._create_kt(start_date='2026-10-20', target_completion_date='2026-10-01')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dates_empty_by_default(self):
        r = self._create_kt()
        self.assertIsNone(r.data['start_date'])
        self.assertIsNone(r.data['target_completion_date'])
        self.assertIsNone(r.data['completed_date'])

    def test_kt_created_notifies_employee(self):
        self._create_kt()
        self.assertTrue(Notification.objects.filter(
            recipient=self.employee_user, notification_type='ACTION_REQUIRED',
            title='New knowledge transfer assigned').exists())

    def test_cannot_create_kt_for_draft_resignation(self):
        # fresh DRAFT resignation
        u = User.objects.create_user(email='draftemp@test.com', username='draftemp', password='pass', role='EMPLOYEE')
        Employee.objects.create(employee_id='DRF001', user=u, first_name='D', last_name='R',
                                email='draftemp@test.com', department=self.dept, designation=self.desig,
                                manager=self.manager_emp, joining_date='2021-01-01', employment_status='ACTIVE')
        auth(self.client, u)
        rid = self.client.post('/api/offboarding/', self.valid_payload, format='json').data['id']
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{rid}/kt/', self.kt_payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class KTWorkflowTest(KTSetup):
    def test_full_happy_path(self):
        # create
        r = self._create_kt(start_date='2026-10-01', target_completion_date='2026-10-20')
        kt_id = r.data['id']
        self.assertEqual(r.data['status'], 'PENDING')
        # employee start
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/kt/{kt_id}/start/')
        self.assertEqual(r.data['status'], 'IN_PROGRESS')
        # employee submit
        r = self.client.post(f'/api/kt/{kt_id}/submit/')
        self.assertEqual(r.data['status'], 'SUBMITTED')
        # receiver accept → MANAGER_REVIEW
        auth(self.client, self.receiver_user)
        r = self.client.post(f'/api/kt/{kt_id}/receiver-action/', {'action': 'accept'}, format='json')
        self.assertEqual(r.data['status'], 'MANAGER_REVIEW')
        # manager approve with manual completion date → COMPLETED
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        self.assertEqual(r.data['status'], 'COMPLETED')
        self.assertEqual(r.data['completed_date'], '2026-10-19')

    def test_receiver_request_changes_path(self):
        kt_id = self._create_kt(start_date='2026-10-01').data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/submit/')
        auth(self.client, self.receiver_user)
        r = self.client.post(f'/api/kt/{kt_id}/receiver-action/',
                             {'action': 'request_changes', 'comments': 'Add rollback instructions.'}, format='json')
        self.assertEqual(r.data['status'], 'REJECTED')
        # employee resumes → IN_PROGRESS
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/kt/{kt_id}/start/')
        self.assertEqual(r.data['status'], 'IN_PROGRESS')

    def test_manager_request_changes_path(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'request_changes', 'comments': 'Incomplete handover.'}, format='json')
        self.assertEqual(r.data['status'], 'REJECTED')

    def test_receiver_request_changes_requires_comments(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/submit/')
        auth(self.client, self.receiver_user)
        r = self.client.post(f'/api/kt/{kt_id}/receiver-action/', {'action': 'request_changes'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_approve_requires_completion_date(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/', {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_request_changes_requires_comments(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/', {'action': 'request_changes'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_submit_from_pending(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/kt/{kt_id}/submit/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_completion_date_before_start_rejected(self):
        kt_id = self._kt_to_manager_review()  # start_date 2026-10-01
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'approve', 'completed_date': '2026-09-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_notifies_receiver(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/submit/')
        self.assertTrue(Notification.objects.filter(
            recipient=self.receiver_user, notification_type='ACTION_REQUIRED').exists())


class KTPermissionTest(KTSetup):
    def test_employee_cannot_approve_own_kt(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_receiver_cannot_perform_manager_approval(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.receiver_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_do_receiver_action(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/submit/')
        # employee tries to accept on behalf of receiver
        r = self.client.post(f'/api/kt/{kt_id}/receiver-action/', {'action': 'accept'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_employee_cannot_start(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user2)
        r = self.client.post(f'/api/kt/{kt_id}/start/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_employee_cannot_view_kt(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/kt/{kt_id}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_receiver_can_view_kt(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.receiver_user)
        r = self.client.get(f'/api/kt/{kt_id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_manager_can_approve(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/manager-action/',
                             {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_hr_can_view_all_kt(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/kt/{kt_id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class KTSecurityTest(KTSetup):
    def test_employee_cannot_set_status_via_update(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        r = self.client.patch(f'/api/kt/{kt_id}/', {'status': 'COMPLETED'}, format='json')
        # request may succeed (ignoring status) but status must NOT change
        kt = KnowledgeTransfer.objects.get(pk=kt_id)
        self.assertEqual(kt.status, 'IN_PROGRESS')

    def test_employee_cannot_change_receiver_via_update(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.patch(f'/api/kt/{kt_id}/', {'receiver': self.employee2.id}, format='json')
        kt = KnowledgeTransfer.objects.get(pk=kt_id)
        self.assertEqual(kt.receiver_id, self.receiver_emp.id)

    def test_employee_cannot_change_completed_date_via_update(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.patch(f'/api/kt/{kt_id}/', {'completed_date': '2026-10-19'}, format='json')
        kt = KnowledgeTransfer.objects.get(pk=kt_id)
        self.assertIsNone(kt.completed_date)

    def test_employee_cannot_change_assigned_to_via_update(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.patch(f'/api/kt/{kt_id}/', {'assigned_to': self.receiver_emp.id}, format='json')
        kt = KnowledgeTransfer.objects.get(pk=kt_id)
        self.assertEqual(kt.assigned_to_id, self.employee.id)

    def test_employee_can_update_own_notes(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        r = self.client.patch(f'/api/kt/{kt_id}/', {'completion_notes': 'Done the handover doc.'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['completion_notes'], 'Done the handover doc.')


class KTUpdateAndReassignTest(KTSetup):
    def test_manager_can_reassign_receiver(self):
        kt_id = self._create_kt().data['id']
        new_rcv = Employee.objects.create(
            employee_id='RCV002', user=User.objects.create_user(
                email='rcv2@test.com', username='rcv2', password='pass', role='EMPLOYEE'),
            first_name='New', last_name='Rcv', email='rcv2@test.com',
            department=self.dept, designation=self.desig, joining_date='2021-01-01',
            employment_status='ACTIVE',
        )
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/reassign/', {'receiver': new_rcv.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['receiver'], new_rcv.id)

    def test_reassign_to_offboarding_employee_rejected(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/kt/{kt_id}/reassign/', {'receiver': self.employee.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_reassign(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/kt/{kt_id}/reassign/', {'receiver': self.receiver_emp.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class KTDocumentTest(KTSetup):
    def test_employee_can_add_document(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        r = self.client.post(f'/api/kt/{kt_id}/documents/',
                             {'url': 'https://docs.example.com/handover', 'description': 'Handover doc'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_invalid_url_rejected(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        r = self.client.post(f'/api/kt/{kt_id}/documents/', {'url': 'not-a-url'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_secret_in_url_rejected(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        r = self.client.post(f'/api/kt/{kt_id}/documents/',
                             {'url': 'https://x.com/?password=hunter2'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_appears_in_detail(self):
        kt_id = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt_id}/start/')
        self.client.post(f'/api/kt/{kt_id}/documents/',
                         {'url': 'https://docs.example.com/x'}, format='json')
        r = self.client.get(f'/api/kt/{kt_id}/')
        self.assertEqual(len(r.data['documents']), 1)


class KTSummaryAndPhaseTest(KTSetup):
    def test_summary_counts(self):
        self._create_kt()  # PENDING
        self._create_kt()  # PENDING
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/kt/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['total'], 2)
        self.assertEqual(r.data['pending'], 2)
        self.assertFalse(r.data['kt_phase_completed'])

    def test_cannot_mark_phase_complete_with_incomplete_tasks(self):
        self._create_kt()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_mark_phase_complete_with_no_tasks(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_phase_complete_when_all_completed(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        self.client.post(f'/api/kt/{kt_id}/manager-action/',
                         {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # summary reflects it
        r = self.client.get(f'/api/offboarding/{self.rid}/kt/summary/')
        self.assertTrue(r.data['kt_phase_completed'])

    def test_employee_cannot_mark_phase_complete(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_kt_complete_auto_creates_it_and_finance_clearance(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        self.client.post(f'/api/kt/{kt_id}/manager-action/',
                         {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        depts = set(DepartmentClearance.objects.filter(
            offboarding_request_id=self.rid).values_list('department', flat=True))
        self.assertIn('IT', depts)
        self.assertIn('FINANCE', depts)

    def test_hr_can_clear_finance_clearance(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        self.client.post(f'/api/kt/{kt_id}/manager-action/',
                         {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        fin = DepartmentClearance.objects.get(offboarding_request_id=self.rid, department='FINANCE')
        r = self.client.patch(f'/api/clearances/{fin.id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-20'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'CLEARED')

    def test_phase_complete_does_not_change_resignation_status(self):
        kt_id = self._kt_to_manager_review()
        auth(self.client, self.manager_user)
        self.client.post(f'/api/kt/{kt_id}/manager-action/',
                         {'action': 'approve', 'completed_date': '2026-10-19'}, format='json')
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/kt/complete/')
        resignation = ResignationRequest.objects.get(pk=self.rid)
        self.assertEqual(resignation.status, 'APPROVED')  # unchanged by KT phase


class KTListTest(KTSetup):
    def test_list_and_filter_by_status(self):
        self._create_kt()
        kt2 = self._create_kt().data['id']
        auth(self.client, self.employee_user)
        self.client.post(f'/api/kt/{kt2}/start/')
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/kt/?status=IN_PROGRESS')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_filter_by_priority(self):
        self._create_kt(priority='HIGH')
        self._create_kt(priority='LOW')
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/kt/?priority=LOW')
        self.assertEqual(len(r.data), 1)

    def test_search(self):
        self._create_kt(title='Zebra handover', description='', responsibility='')
        self._create_kt(title='Documentation cleanup', description='', responsibility='')
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/kt/?search=Zebra')
        self.assertEqual(len(r.data), 1)

    def test_mine_as_receiver(self):
        self._create_kt()
        auth(self.client, self.receiver_user)
        r = self.client.get('/api/kt/mine/?role=receiver')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_mine_as_assigned(self):
        self._create_kt()
        auth(self.client, self.employee_user)
        r = self.client.get('/api/kt/mine/?role=assigned')
        self.assertEqual(len(r.data), 1)


# ─── Phase 6: Asset & Department Clearance Tests ─────────────────────────────

from apps.offboarding.models import (  # noqa: E402
    Asset, AssetClearance, DepartmentClearance, ClearanceChecklistItem,
)


class ClearanceSetup(NoticePeriodSetup):
    """Approved resignation + IT/Finance users + an asset assigned to the employee."""

    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()  # owner self.employee_user / mgr self.manager_user

        self.it_user = User.objects.create_user(
            email='it@test.com', username='ituser', password='pass', role='IT',
            first_name='IT', last_name='Person',
        )
        self.finance_user = User.objects.create_user(
            email='fin@test.com', username='finuser', password='pass', role='FINANCE',
            first_name='Fin', last_name='Person',
        )

        # Asset assigned to the offboarding employee
        self.asset = Asset.objects.create(
            asset_id='AST001', asset_type='LAPTOP', asset_name='Dell XPS',
            serial_number='SN12345', assigned_to=self.employee, status='ASSIGNED',
        )
        # Asset assigned to a different employee (for negative tests)
        self.other_asset = Asset.objects.create(
            asset_id='AST002', asset_type='MONITOR', asset_name='LG Monitor',
            serial_number='SN99999', assigned_to=self.employee2, status='ASSIGNED',
        )

    def _add_asset_clearance(self, asset=None):
        auth(self.client, self.it_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/assets/',
                             {'asset': (asset or self.asset).id}, format='json')
        return r

    def _create_dept(self, department='IT', actor=None):
        auth(self.client, actor or self.hr_user)
        return self.client.post(f'/api/offboarding/{self.rid}/clearances/',
                                {'department': department}, format='json')


class AssetCrudTest(ClearanceSetup):
    def test_it_can_create_asset(self):
        auth(self.client, self.it_user)
        r = self.client.post('/api/assets/', {
            'asset_id': 'AST100', 'asset_type': 'MOBILE', 'asset_name': 'iPhone',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_employee_cannot_create_asset(self):
        auth(self.client, self.employee_user)
        r = self.client.post('/api/assets/', {
            'asset_id': 'AST101', 'asset_type': 'MOBILE', 'asset_name': 'x',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_date_optional_and_not_auto(self):
        auth(self.client, self.it_user)
        r = self.client.post('/api/assets/', {
            'asset_id': 'AST102', 'asset_type': 'LAPTOP', 'asset_name': 'y',
        }, format='json')
        self.assertIsNone(r.data['assigned_date'])

    def test_assign_asset_via_patch(self):
        auth(self.client, self.it_user)
        a = Asset.objects.create(asset_id='AST103', asset_type='LAPTOP', asset_name='z', status='ASSIGNED')
        r = self.client.patch(f'/api/assets/{a.id}/', {'assigned_to': self.employee.id, 'assigned_date': '2026-01-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['assigned_to'], self.employee.id)

    def test_employee_sees_own_assets(self):
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/employees/{self.employee.id}/assets/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.data), 1)

    def test_employee_cannot_see_others_assets(self):
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/employees/{self.employee2.id}/assets/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_asset_search_and_filter(self):
        auth(self.client, self.it_user)
        r = self.client.get('/api/assets/?asset_type=LAPTOP&search=SN12345')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class AssetReturnWorkflowTest(ClearanceSetup):
    def test_add_asset_to_clearance(self):
        r = self._add_asset_clearance()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'RETURN_PENDING')

    def test_cannot_add_asset_not_assigned_to_employee(self):
        r = self._add_asset_clearance(asset=self.other_asset)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_add_asset_clearance(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/assets/', {'asset': self.asset.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_record_return_requires_manual_date(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'record_return', 'condition': 'GOOD'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)  # no return_date

    def test_record_return_success(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'RETURNED')
        self.assertEqual(r.data['return_date'], '2026-10-10')
        # asset status synced
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, 'RETURNED')

    def test_employee_cannot_record_return(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_after_return(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'}, format='json')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'verify'}, format='json')
        self.assertEqual(r.data['status'], 'CLEARED')
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, 'CLEARED')

    def test_reject_requires_comments(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'}, format='json')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'reject'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_then_re_return(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'}, format='json')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'reject', 'comments': 'Charger missing.'}, format='json')
        self.assertEqual(r.data['status'], 'REJECTED')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'record_return', 'return_date': '2026-10-12', 'condition': 'GOOD'}, format='json')
        self.assertEqual(r.data['status'], 'RETURNED')

    def test_mark_lost(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'mark_lost'}, format='json')
        self.assertEqual(r.data['status'], 'LOST')

    def test_mark_damaged_after_return(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'DAMAGED'}, format='json')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/',
                              {'action': 'mark_damaged', 'comments': 'Cracked screen.'}, format='json')
        self.assertEqual(r.data['status'], 'DAMAGED')

    def test_cannot_verify_before_return(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'verify'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_return_recorded_notifies_hr_or_employee(self):
        self._add_asset_clearance()
        self.assertTrue(Notification.objects.filter(
            recipient=self.employee_user, title='Asset return required').exists())


class DepartmentClearanceTest(ClearanceSetup):
    def test_hr_can_create_dept_clearance(self):
        r = self._create_dept('IT')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'PENDING')

    def test_employee_cannot_create_dept_clearance(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearances/', {'department': 'IT'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_dept_rejected(self):
        self._create_dept('IT')
        r = self._create_dept('IT')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_can_clear_it_department(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'CLEARED')
        self.assertEqual(r.data['clearance_date'], '2026-10-15')

    def test_finance_cannot_clear_it_department(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.finance_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_can_clear_finance_department(self):
        dc_id = self._create_dept('FINANCE').data['id']
        auth(self.client, self.finance_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.data['status'], 'CLEARED')

    def test_manager_can_clear_manager_department(self):
        dc_id = self._create_dept('MANAGER').data['id']
        auth(self.client, self.manager_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.data['status'], 'CLEARED')

    def test_hr_can_clear_hr_department(self):
        dc_id = self._create_dept('HR').data['id']
        auth(self.client, self.hr_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.data['status'], 'CLEARED')

    def test_clear_requires_manual_date(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/', {'action': 'clear'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_requires_comments(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/', {'action': 'reject'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_clear_department(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class ChecklistTest(ClearanceSetup):
    def setUp(self):
        super().setUp()
        self.dc_id = self._create_dept('IT').data['id']

    def test_hr_can_add_checklist_item(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/clearances/{self.dc_id}/checklist/',
                             {'title': 'Laptop Returned'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'PENDING')

    def test_it_can_complete_checklist_item(self):
        auth(self.client, self.hr_user)
        item_id = self.client.post(f'/api/clearances/{self.dc_id}/checklist/',
                                   {'title': 'Email Access Reviewed'}, format='json').data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/checklist/{item_id}/', {'action': 'complete'}, format='json')
        self.assertEqual(r.data['status'], 'COMPLETED')

    def test_employee_cannot_complete_checklist_item(self):
        auth(self.client, self.hr_user)
        item_id = self.client.post(f'/api/clearances/{self.dc_id}/checklist/',
                                   {'title': 'VPN Access'}, format='json').data['id']
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/checklist/{item_id}/', {'action': 'complete'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_clear_dept_with_pending_checklist(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/clearances/{self.dc_id}/checklist/', {'title': 'Laptop Returned'}, format='json')
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/clearances/{self.dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_clear_dept_after_checklist_complete(self):
        auth(self.client, self.hr_user)
        item_id = self.client.post(f'/api/clearances/{self.dc_id}/checklist/',
                                   {'title': 'Laptop Returned'}, format='json').data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/checklist/{item_id}/', {'action': 'complete'}, format='json')
        r = self.client.patch(f'/api/clearances/{self.dc_id}/',
                              {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        self.assertEqual(r.data['status'], 'CLEARED')

    def test_checklist_item_not_applicable(self):
        auth(self.client, self.hr_user)
        item_id = self.client.post(f'/api/clearances/{self.dc_id}/checklist/',
                                   {'title': 'Desktop Returned'}, format='json').data['id']
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/checklist/{item_id}/', {'action': 'not_applicable'}, format='json')
        self.assertEqual(r.data['status'], 'NOT_APPLICABLE')


class ClearanceCompletionTest(ClearanceSetup):
    def _clear_dept(self, department, actor):
        dc_id = self._create_dept(department).data['id']
        auth(self.client, actor)
        self.client.patch(f'/api/clearances/{dc_id}/',
                          {'action': 'clear', 'clearance_date': '2026-10-15'}, format='json')
        return dc_id

    def test_cannot_complete_with_no_departments(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_with_pending_department(self):
        self._create_dept('IT')  # left PENDING
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_with_rejected(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/clearances/{dc_id}/', {'action': 'reject', 'comments': 'x'}, format='json')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_complete_with_pending_asset(self):
        self._clear_dept('IT', self.it_user)
        self._add_asset_clearance()  # RETURN_PENDING
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_success(self):
        self._clear_dept('IT', self.it_user)
        self._clear_dept('FINANCE', self.finance_user)
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_complete_does_not_change_resignation_status(self):
        self._clear_dept('IT', self.it_user)
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(ResignationRequest.objects.get(pk=self.rid).status, 'APPROVED')

    def test_employee_cannot_complete_clearance(self):
        self._clear_dept('IT', self.it_user)
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_complete_with_cleared_assets(self):
        self._clear_dept('IT', self.it_user)
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'}, format='json')
        self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'verify'}, format='json')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/clearance/complete/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class ClearanceSummaryTest(ClearanceSetup):
    def test_summary_counts(self):
        self._create_dept('IT')
        self._create_dept('FINANCE')
        self._add_asset_clearance()
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/clearance/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['departments']['total'], 2)
        self.assertEqual(r.data['departments']['pending'], 2)
        self.assertEqual(r.data['assets']['total'], 1)
        self.assertEqual(r.data['assets']['pending'], 1)
        self.assertFalse(r.data['clearance_completed'])

    def test_employee_can_view_summary(self):
        self._create_dept('IT')
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/clearance/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unrelated_employee_cannot_view_summary(self):
        self._create_dept('IT')
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/clearance/summary/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class ClearanceSecurityTest(ClearanceSetup):
    def test_employee_cannot_set_asset_status_directly(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.employee_user)
        # Attempt to bypass with a raw status payload
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'status': 'CLEARED'}, format='json')
        # Not authorised to verify → 403; status must remain RETURN_PENDING
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AssetClearance.objects.get(pk=ac_id).status, 'RETURN_PENDING')

    def test_employee_cannot_set_dept_status_directly(self):
        dc_id = self._create_dept('IT').data['id']
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/clearances/{dc_id}/', {'status': 'CLEARED'}, format='json')
        self.assertIn(r.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
        self.assertEqual(DepartmentClearance.objects.get(pk=dc_id).status, 'PENDING')

    def test_asset_status_not_settable_via_asset_patch(self):
        auth(self.client, self.it_user)
        r = self.client.patch(f'/api/assets/{self.asset.id}/', {'status': 'CLEARED'}, format='json')
        # status is read-only on AssetUpdateSerializer — must remain ASSIGNED
        self.assertEqual(Asset.objects.get(pk=self.asset.id).status, 'ASSIGNED')


class ClearanceDateRuleTest(ClearanceSetup):
    def test_asset_clearance_dates_empty_by_default(self):
        r = self._add_asset_clearance()
        self.assertIsNone(r.data['return_date'])
        self.assertIsNone(r.data['verified_at'])

    def test_dept_clearance_date_empty_by_default(self):
        r = self._create_dept('IT')
        self.assertIsNone(r.data['clearance_date'])
        self.assertIsNone(r.data['cleared_at'])

    def test_saved_return_date_unchanged_on_verify(self):
        ac_id = self._add_asset_clearance().data['id']
        auth(self.client, self.it_user)
        self.client.patch(f'/api/asset-clearance/{ac_id}/',
                          {'action': 'record_return', 'return_date': '2026-10-10', 'condition': 'GOOD'}, format='json')
        r = self.client.patch(f'/api/asset-clearance/{ac_id}/', {'action': 'verify'}, format='json')
        self.assertEqual(r.data['return_date'], '2026-10-10')  # unchanged by verify


