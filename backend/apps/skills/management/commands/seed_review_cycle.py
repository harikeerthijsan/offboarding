"""Create (or correct) the current review cycle so employees can submit skills.

Idempotent. Defaults to the 2026-H2 cycle with a window that is open on today's
date; pass flags to set different dates. One-word invocation so it runs cleanly
over `railway ssh` with no quoting.

Usage:
  python manage.py seed_review_cycle
  python manage.py seed_review_cycle --cycle-id 2027-H1 --period-start 2027-01-10 \
      --period-end 2027-06-30 --employee-due 2027-02-09 --manager-due 2027-02-23 \
      --closure-target 2027-03-11
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.skills.models import ReviewCycle

DEFAULTS = {
    'cycle_id': '2026-H2',
    'period_start': '2026-07-01',
    'period_end': '2026-12-31',
    'employee_due': '2026-11-06',
    'manager_due': '2026-11-20',
    'closure_target': '2026-12-01',
}


class Command(BaseCommand):
    help = "Create or update a review cycle (defaults to an open 2026-H2 cycle)."

    def add_arguments(self, parser):
        parser.add_argument('--cycle-id', default=DEFAULTS['cycle_id'])
        parser.add_argument('--period-start', default=DEFAULTS['period_start'])
        parser.add_argument('--period-end', default=DEFAULTS['period_end'])
        parser.add_argument('--employee-due', default=DEFAULTS['employee_due'])
        parser.add_argument('--manager-due', default=DEFAULTS['manager_due'])
        parser.add_argument('--closure-target', default=DEFAULTS['closure_target'])

    def _date(self, s):
        try:
            return datetime.date.fromisoformat(s)
        except ValueError:
            raise CommandError(f'Bad date "{s}"; use YYYY-MM-DD.')

    def handle(self, *args, **o):
        fields = dict(
            period_start=self._date(o['period_start']),
            period_end=self._date(o['period_end']),
            employee_due=self._date(o['employee_due']),
            manager_due=self._date(o['manager_due']),
            closure_target=self._date(o['closure_target']),
        )
        cycle, created = ReviewCycle.objects.update_or_create(
            cycle_id=o['cycle_id'], defaults=fields,
        )
        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} cycle {cycle.cycle_id}: {cycle.period_start} .. {cycle.period_end}, '
            f'employee_due {cycle.employee_due}, closes {cycle.closure_target}.'
        ))
        self.stdout.write('Run "python manage.py skills_status" to confirm Submit is enabled.')
