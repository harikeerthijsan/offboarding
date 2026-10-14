"""Diagnostic: print the skills review-cycle state as the app computes it.

Read-only. Explains whether the 'Submit' button will be enabled for employees
(it is enabled only when the active cycle's state is open/overdue, or the person
already has a draft/submitted/rejected submission).

Usage (locally or over Railway):
  python manage.py skills_status
  railway ssh "cd backend && python manage.py skills_status"
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.skills.models import ReviewCycle, SkillSubmission
from apps.skills.cycles import active_cycle, cycles_for

EDITABLE = {'open', 'overdue', 'draft', 'submitted', 'rejected'}


class Command(BaseCommand):
    help = "Show review-cycle state and whether employees can submit skills."

    def handle(self, *args, **opts):
        today = timezone.localdate()
        cycles = list(ReviewCycle.objects.all())
        self.stdout.write(f'today = {today}')
        self.stdout.write(f'ReviewCycle count = {len(cycles)}')
        self.stdout.write(f'SkillSubmission count = {SkillSubmission.objects.count()}')

        if not cycles:
            self.stdout.write(self.style.ERROR(
                'NO REVIEW CYCLES configured -> Submit button is disabled for everyone. '
                'Fix: Skills -> Review Cycles -> Create a cycle whose window covers today.'
            ))
            return

        # Per-person state for someone with no submission yet (what a fresh employee sees).
        rows = cycles_for(cycles, {}, today)
        ac = active_cycle(cycles, today)
        self.stdout.write('--- cycles (oldest first) ---')
        for r in rows:
            mark = '  <== ACTIVE' if r['is_active'] else ''
            self.stdout.write(
                f"{r['cycle_id']}: start={r['period_start']} emp_due={r['employee_due']} "
                f"close={r['closure_target']} state={r['state']}{mark}"
            )

        active_state = next((r['state'] for r in rows if r['is_active']), None)
        can = active_state in EDITABLE
        self.stdout.write('--- verdict ---')
        self.stdout.write(f'active cycle = {ac.cycle_id if ac else None}, state = {active_state}')
        if can:
            self.stdout.write(self.style.SUCCESS(
                'Submit ENABLED (active cycle is open/overdue). If the button is still greyed '
                'out for a user, their profile is missing department/designation.'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'Submit DISABLED: active cycle state "{active_state}" is not open/overdue. '
                'Fix: create or edit a cycle so period_start <= today <= employee_due '
                '(or at least <= closure_target).'
            ))
