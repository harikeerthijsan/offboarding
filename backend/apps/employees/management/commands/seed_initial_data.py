"""Load the committed initial-data fixture into a fresh database.

Runs on deploy (see start.sh). Guarded so it only loads when the database is
empty — on later redeploys it's a no-op and never overwrites data created in
production. Use --force to load regardless (overwrites rows by primary key).
"""
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.employees.models import Employee

FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))),  # -> backend/
    'seed', 'initial_data.json',
)


class Command(BaseCommand):
    help = 'Load seed/initial_data.json into an empty database (idempotent by default).'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Load even if data already exists (overwrites by pk).')

    def handle(self, *args, **opts):
        if not os.path.exists(FIXTURE):
            self.stdout.write(self.style.WARNING(f'No fixture at {FIXTURE}; skipping seed.'))
            return

        if Employee.objects.exists() and not opts['force']:
            self.stdout.write('Database already has employee data — skipping seed '
                              '(use --force to load anyway).')
            return

        self.stdout.write('Loading initial data fixture…')
        call_command('loaddata', FIXTURE, verbosity=1)
        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {Employee.objects.count()} employees now in the database.'))
