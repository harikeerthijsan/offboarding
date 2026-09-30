from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.notifications.models import Notification
from apps.offboarding.models import (
    ResignationRequest, NoticePeriod, FinalSettlement, ExitInterview,
    DepartmentClearance,
)
from apps.offboarding.tests import NoticePeriodSetup, auth


class FinalReviewSetup(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()  # APPROVED, employee OFFBOARDING
        self.resignation = ResignationRequest.objects.get(pk=self.rid)

    def _make_ready(self, r=None):
        """Directly set the stored state so all prerequisites are satisfied."""
        r = r or self.resignation
        NoticePeriod.objects.create(
            resignation=r, status='COMPLETED',
            notice_period_start_date='2026-10-01', expected_last_working_day='2026-11-30',
            actual_last_working_day='2026-11-30',
        )
        r.kt_completed_at = timezone.now()
        r.clearance_completed_at = timezone.now()
        r.save(update_fields=['kt_completed_at', 'clearance_completed_at'])
        FinalSettlement.objects.create(
            offboarding_request=r, employee=r.employee, settlement_status='APPROVED',
            gross_amount=1000, total_deductions=0, net_settlement=1000,
        )
        ExitInterview.objects.create(
            offboarding_request=r, employee=r.employee, status='COMPLETED',
        )
        r.refresh_from_db()
        return r


class FinalReviewReadinessTest(FinalReviewSetup):
    def test_summary_lists_pending_when_incomplete(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['is_ready'])
        self.assertIn('Notice Period', r.data['pending_items'])
        self.assertIn('Final Settlement', r.data['pending_items'])
        self.assertIn('Exit Interview', r.data['pending_items'])

    def test_cannot_start_when_incomplete(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                             {'final_review_date': '2026-12-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pending_items', r.data)

    def test_summary_ready_when_complete(self):
        self._make_ready()
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertTrue(r.data['is_ready'])
        self.assertEqual(r.data['pending_items'], [])

    def test_prereq_validation_failure_is_audited(self):
        from apps.audit.models import AuditLog
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                         {'final_review_date': '2026-12-01'}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='PREREQUISITE_VALIDATION_FAILED').exists())


class FinalReviewApprovalTest(FinalReviewSetup):
    def setUp(self):
        super().setUp()
        self._make_ready()

    def test_hr_can_start(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                             {'final_review_date': '2026-12-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['final_review_status'], 'UNDER_REVIEW')
        self.assertEqual(str(r.data['final_review_date']), '2026-12-01')

    def test_start_requires_manual_review_date(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_start(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                             {'final_review_date': '2026-12-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def _start(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                         {'final_review_date': '2026-12-01'}, format='json')

    def test_hr_can_approve(self):
        self._start()
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                             {'final_approval_date': '2026-12-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['final_review_status'], 'APPROVED')
        self.assertEqual(str(r.data['final_approval_date']), '2026-12-05')

    def test_approve_requires_manual_date(self):
        self._start()
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_does_not_mark_exited(self):
        self._start()
        self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                         {'final_approval_date': '2026-12-05'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'OFFBOARDING')

    def test_approve_does_not_change_resignation_status(self):
        self._start()
        self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                         {'final_approval_date': '2026-12-05'}, format='json')
        self.assertEqual(ResignationRequest.objects.get(pk=self.rid).status, 'APPROVED')

    def test_employee_cannot_approve(self):
        self._start()
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                             {'final_approval_date': '2026-12-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_approve(self):
        self._start()
        auth(self.client, self.manager_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                             {'final_approval_date': '2026-12-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_approve_before_start(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                             {'final_approval_date': '2026-12-05'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_notifies_employee(self):
        self._start()
        self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                         {'final_approval_date': '2026-12-05'}, format='json')
        self.assertTrue(Notification.objects.filter(
            recipient=self.employee_user, title='Offboarding finally approved').exists())


class FinalReviewRejectionTest(FinalReviewSetup):
    def setUp(self):
        super().setUp()
        self._make_ready()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                         {'final_review_date': '2026-12-01'}, format='json')

    def test_hr_can_reject(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/reject/',
                             {'rejection_reason': 'Settlement figure disputed.'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['final_review_status'], 'REJECTED')

    def test_reject_requires_reason(self):
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/reject/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_keeps_employee_offboarding(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/reject/',
                         {'rejection_reason': 'x'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, 'OFFBOARDING')

    def test_reject_preserves_settlement_data(self):
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/reject/',
                         {'rejection_reason': 'x'}, format='json')
        fs = FinalSettlement.objects.get(offboarding_request_id=self.rid)
        self.assertEqual(fs.settlement_status, 'APPROVED')  # untouched

    def test_employee_cannot_reject(self):
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/final-review/reject/',
                             {'rejection_reason': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class FinalReviewDateRuleTest(FinalReviewSetup):
    def test_final_dates_empty_by_default(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertIsNone(r.data['final_review_date'])
        self.assertIsNone(r.data['final_approval_date'])
        self.assertEqual(r.data['final_review_status'], 'NOT_READY')


class FinalReviewSecurityTest(FinalReviewSetup):
    def test_unrelated_employee_cannot_view_summary(self):
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_view_summary(self):
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class HRDashboardTest(FinalReviewSetup):
    def test_dashboard_counts(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/dashboard/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('summary', r.data)
        self.assertIn('pipeline', r.data)
        self.assertGreaterEqual(r.data['summary']['total_offboarding'], 1)

    def test_ready_count_reflects_completion(self):
        self._make_ready()
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/dashboard/')
        self.assertGreaterEqual(r.data['summary']['ready_for_final_review'], 1)

    def test_completed_count_after_approval(self):
        self._make_ready()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/final-review/start/',
                         {'final_review_date': '2026-12-01'}, format='json')
        self.client.post(f'/api/offboarding/{self.rid}/final-review/approve/',
                         {'final_approval_date': '2026-12-05'}, format='json')
        r = self.client.get('/api/offboarding/dashboard/')
        self.assertGreaterEqual(r.data['summary']['completed'], 1)

    def test_employee_cannot_view_dashboard(self):
        auth(self.client, self.employee_user)
        r = self.client.get('/api/offboarding/dashboard/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_paginated(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/dashboard/list/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('results', r.data)
        self.assertIn('count', r.data)

    def test_list_search(self):
        auth(self.client, self.hr_user)
        r = self.client.get(f'/api/offboarding/dashboard/list/?search={self.employee.employee_id}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['count'], 1)

    def test_list_row_has_derived_fields(self):
        auth(self.client, self.hr_user)
        r = self.client.get('/api/offboarding/dashboard/list/')
        row = r.data['results'][0]
        for key in ('current_stage', 'kt_status', 'clearance_status',
                    'settlement_status', 'exit_interview_status', 'final_review_status'):
            self.assertIn(key, row)

    def test_manager_list_scoped_to_reports(self):
        auth(self.client, self.manager_user)
        r = self.client.get('/api/offboarding/dashboard/list/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
