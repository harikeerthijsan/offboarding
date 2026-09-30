from rest_framework import status

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.notifications.models import Notification
from apps.offboarding.models import ResignationRequest, FinalSettlement, ExitInterview

from apps.offboarding.tests import NoticePeriodSetup, auth


# ─── Final Settlement ────────────────────────────────────────────────────────

class SettlementSetup(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()
        self.finance_user = User.objects.create_user(
            email='fin7@test.com', username='fin7', password='pass', role='FINANCE',
            first_name='Fin', last_name='Seven',
        )
        self.money = {
            'pending_salary': '5000.00', 'leave_encashment': '1000.00',
            'bonus': '500.00', 'incentives': '0.00', 'other_additions': '0.00',
            'notice_recovery': '200.00', 'loan_deduction': '0.00',
            'advance_deduction': '0.00', 'other_deductions': '100.00',
        }

    def _create_settlement(self, actor=None, **overrides):
        auth(self.client, actor or self.finance_user)
        payload = dict(self.money, **overrides)
        return self.client.post(f'/api/offboarding/{self.rid}/settlement/', payload, format='json')

    def _submit(self):
        auth(self.client, self.finance_user)
        return self.client.post(f'/api/offboarding/{self.rid}/settlement/submit/')


class SettlementCrudTest(SettlementSetup):
    def test_finance_can_create(self):
        r = self._create_settlement()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['settlement_status'], 'DRAFT')

    def test_employee_cannot_create(self):
        r = self._create_settlement(actor=self.employee_user)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_totals_calculated_by_backend(self):
        r = self._create_settlement()
        self.assertEqual(r.data['gross_amount'], '6500.00')
        self.assertEqual(r.data['total_deductions'], '300.00')
        self.assertEqual(r.data['net_settlement'], '6200.00')

    def test_frontend_cannot_override_totals(self):
        r = self._create_settlement(net_settlement='999999.00', gross_amount='1.00')
        self.assertEqual(r.data['net_settlement'], '6200.00')

    def test_status_cannot_be_set_by_payload(self):
        r = self._create_settlement(settlement_status='APPROVED')
        self.assertEqual(r.data['settlement_status'], 'DRAFT')

    def test_negative_amount_rejected(self):
        r = self._create_settlement(bonus='-100.00')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_settlement_rejected(self):
        self._create_settlement()
        r = self._create_settlement()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_finance_can_edit_draft(self):
        self._create_settlement()
        auth(self.client, self.finance_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/settlement/', {'bonus': '1000.00'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['bonus'], '1000.00')
        self.assertEqual(r.data['net_settlement'], '6700.00')

    def test_employee_cannot_edit(self):
        self._create_settlement()
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/settlement/', {'bonus': '9999.00'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_settlement_date_empty_by_default(self):
        r = self._create_settlement()
        self.assertIsNone(r.data['settlement_date'])

    def test_employee_gets_restricted_view(self):
        self._create_settlement()
        auth(self.client, self.employee_user)
        r = self.client.get(f'/api/offboarding/{self.rid}/settlement/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn('comments', r.data)
        self.assertNotIn('pending_salary', r.data)
        self.assertIn('net_settlement', r.data)


class SettlementWorkflowTest(SettlementSetup):
    def test_submit_moves_to_under_review(self):
        self._create_settlement()
        r = self._submit()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['settlement_status'], 'UNDER_REVIEW')

    def test_cannot_edit_after_submit(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.finance_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/settlement/', {'bonus': '1.00'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hr_can_approve(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                             {'settlement_date': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['settlement_status'], 'APPROVED')
        self.assertEqual(r.data['settlement_date'], '2026-11-01')

    def test_approve_requires_manual_date(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_cannot_approve(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                             {'settlement_date': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_cannot_approve(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.finance_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                             {'settlement_date': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_returns_to_draft(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/reject/',
                             {'comments': 'Recheck bonus.'}, format='json')
        self.assertEqual(r.data['settlement_status'], 'DRAFT')

    def test_reject_requires_comments(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/reject/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_then_resubmit(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/settlement/reject/', {'comments': 'fix'}, format='json')
        auth(self.client, self.finance_user)
        self.client.patch(f'/api/offboarding/{self.rid}/settlement/', {'bonus': '600.00'}, format='json')
        r = self._submit()
        self.assertEqual(r.data['settlement_status'], 'UNDER_REVIEW')

    def test_cannot_submit_from_under_review(self):
        self._create_settlement()
        self._submit()
        r = self._submit()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_approve_before_submit(self):
        self._create_settlement()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                             {'settlement_date': '2026-11-01'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_approve_even_if_preparer(self):
        auth(self.client, self.admin_user)
        self.client.post(f'/api/offboarding/{self.rid}/settlement/', self.money, format='json')
        self.client.post(f'/api/offboarding/{self.rid}/settlement/submit/')
        r = self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                             {'settlement_date': '2026-11-01'}, format='json')
        self.assertEqual(r.data['settlement_status'], 'APPROVED')

    def test_approve_notifies_employee(self):
        self._create_settlement()
        self._submit()
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/settlement/approve/',
                         {'settlement_date': '2026-11-01'}, format='json')
        self.assertTrue(Notification.objects.filter(
            recipient=self.employee_user, title='Final settlement approved').exists())


class SettlementSecurityTest(SettlementSetup):
    def test_employee_cannot_patch_status(self):
        self._create_settlement()
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/settlement/',
                              {'settlement_status': 'APPROVED'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            FinalSettlement.objects.get(offboarding_request_id=self.rid).settlement_status, 'DRAFT')

    def test_net_settlement_not_writable(self):
        self._create_settlement()
        auth(self.client, self.finance_user)
        self.client.patch(f'/api/offboarding/{self.rid}/settlement/',
                          {'net_settlement': '1.00'}, format='json')
        s = FinalSettlement.objects.get(offboarding_request_id=self.rid)
        self.assertEqual(str(s.net_settlement), '6200.00')

    def test_unrelated_employee_cannot_view(self):
        self._create_settlement()
        auth(self.client, self.employee_user2)
        r = self.client.get(f'/api/offboarding/{self.rid}/settlement/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


# ─── Exit Interview ──────────────────────────────────────────────────────────

class ExitInterviewSetup(NoticePeriodSetup):
    def setUp(self):
        super().setUp()
        self.rid = self._get_approved_resignation_id()

    def _start(self, actor=None):
        auth(self.client, actor or self.employee_user)
        return self.client.post(f'/api/offboarding/{self.rid}/exit-interview/')


class ExitInterviewTest(ExitInterviewSetup):
    def test_employee_can_start(self):
        r = self._start()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'IN_PROGRESS')

    def test_duplicate_start_rejected(self):
        self._start()
        r = self._start()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_can_save_draft(self):
        self._start()
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                              {'primary_reason': 'CAREER_GROWTH', 'overall_experience': 4,
                               'what_went_well': 'Great team.'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['primary_reason'], 'CAREER_GROWTH')
        self.assertEqual(r.data['overall_experience'], 4)

    def test_interview_date_empty_by_default(self):
        r = self._start()
        self.assertIsNone(r.data['interview_date'])

    def test_manual_interview_date_preserved(self):
        self._start()
        auth(self.client, self.employee_user)
        r = self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                              {'interview_date': '2026-11-05'}, format='json')
        self.assertEqual(r.data['interview_date'], '2026-11-05')

    def test_employee_can_submit(self):
        self._start()
        auth(self.client, self.employee_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        self.assertEqual(r.data['status'], 'COMPLETED')

    def test_cannot_edit_after_submit(self):
        self._start()
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        r = self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                              {'what_went_well': 'changed'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_employee_cannot_edit(self):
        self._start()
        auth(self.client, self.employee_user2)
        r = self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                              {'what_went_well': 'x'}, format='json')
        self.assertIn(r.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_hr_can_review(self):
        self._start()
        auth(self.client, self.employee_user)
        self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                          {'what_went_well': 'Nice culture.'}, format='json')
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/exit-interview/review/',
                             {'hr_review_notes': 'Noted.'}, format='json')
        self.assertEqual(r.data['status'], 'REVIEWED')
        self.assertEqual(r.data['hr_review_notes'], 'Noted.')

    def test_hr_review_does_not_overwrite_answers(self):
        self._start()
        auth(self.client, self.employee_user)
        self.client.patch(f'/api/offboarding/{self.rid}/exit-interview/',
                          {'what_went_well': 'Original answer.'}, format='json')
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        auth(self.client, self.hr_user)
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/review/',
                         {'hr_review_notes': 'HR note.'}, format='json')
        ei = ExitInterview.objects.get(offboarding_request_id=self.rid)
        self.assertEqual(ei.what_went_well, 'Original answer.')
        self.assertEqual(ei.hr_review_notes, 'HR note.')

    def test_employee_cannot_review(self):
        self._start()
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        r = self.client.post(f'/api/offboarding/{self.rid}/exit-interview/review/',
                             {'hr_review_notes': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_review_before_completed(self):
        self._start()
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/exit-interview/review/',
                             {'hr_review_notes': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hr_can_reopen(self):
        self._start()
        auth(self.client, self.employee_user)
        self.client.post(f'/api/offboarding/{self.rid}/exit-interview/submit/')
        auth(self.client, self.hr_user)
        r = self.client.post(f'/api/offboarding/{self.rid}/exit-interview/review/',
                             {'action': 'reopen'}, format='json')
        self.assertEqual(r.data['status'], 'IN_PROGRESS')

    def test_hr_can_start_for_employee(self):
        r = self._start(actor=self.hr_user)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)


class ExitInterviewAnalyticsTest(ExitInterviewSetup):
    def _completed_interview(self, employee_user, rid, reason, exp, recommend):
        auth(self.client, employee_user)
        self.client.post(f'/api/offboarding/{rid}/exit-interview/')
        self.client.patch(f'/api/offboarding/{rid}/exit-interview/',
                          {'primary_reason': reason, 'overall_experience': exp,
                           'would_recommend': recommend}, format='json')
        self.client.post(f'/api/offboarding/{rid}/exit-interview/submit/')

    def test_analytics_aggregate(self):
        self._completed_interview(self.employee_user, self.rid, 'CAREER_GROWTH', 5, True)
        auth(self.client, self.hr_user)
        r = self.client.get('/api/exit-interviews/analytics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['total_interviews'], 1)
        self.assertEqual(r.data['top_leaving_reasons'].get('CAREER_GROWTH'), 1)
        self.assertEqual(r.data['would_recommend']['yes'], 1)

    def test_employee_cannot_view_analytics(self):
        auth(self.client, self.employee_user)
        r = self.client.get('/api/exit-interviews/analytics/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
