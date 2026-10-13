"""Set the real @jsanconsulting.com email on exited employees (and their logins).

Exited employees were seeded with placeholder emails (jsanNNN@jsan.local). This
command carries the real addresses from the "List of active & exit Employees"
Exit sheet (column "Jsan Email ID"), baked in so the same correction runs on any
database (local and live) without needing the Excel file.

Idempotent & safe:
  - only touches employees whose status is EXITED,
  - skips a row if the email is already set, is blank, or is already owned by a
    different employee/login (reported, never overwritten),
  - updates the Employee and its linked User email together in a transaction.

Usage:
  python manage.py sync_exit_emails [--dry-run]
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.employees.models import Employee

# JSAN ID -> real email (from the Exit sheet). Blank JSAN294 intentionally omitted.
ROSTER = [
    ('JSAN222', 'mdonthireddy@jsanconsulting.com'),
    ('JSAN072', 'mrevu@jsanconsulting.com'),
    ('JSAN191', 'rkapu@jsanconsulting.com'),
    ('JSAN225', 'rmadhyarla@jsanconsulting.com'),
    ('JSAN132', 'lpgoli@jsanconsulting.com'),
    ('JSAN052', 'supriyan@jsanconsulting.com'),
    ('JSAN176', 'pmosharat@jsanconsulting.com'),
    ('JSAN221', 'rdarla@jsanconsulting.com'),
    ('JSAN033', 'krajitha@jsanconsulting.com'),
    ('JSAN157', 'nsmutum@jsanconsulting.com'),
    ('JSAN170', 'bsadanala@jsanconsulting.com'),
    ('JSAN172', 'nbadavath@jsanconsulting.com'),
    ('JSAN233', 'prkoppala@jsanconsulting.com'),
    ('JSAN228', 'kcherukuri@jsanconsulting.com'),
    ('JSAN041', 'sneve@jsanconsulting.com'),
    ('JSAN102', 'suikey@jsanconsulting.com'),
    ('JSAN185', 'vsingh@jsanconsulting.com'),
    ('JSAN240', 'mbag@jsanconsulting.com'),
    ('JSAN065', 'rpbabaria@jsanconsulting.com'),
    ('JSAN209', 'bchalla@jsanconsulting.com'),
    ('JSAN247', 'vshanagonda@jsanconsulting.com'),
    ('JSAN229', 'hryadagiri@jsanconsulting.com'),
    ('JSAN236', 'rchandaluri@jsanconsulting.com'),
    ('JSAN153', 'pkarukola@jsanconsulting.com'),
    ('JSAN213', 'mmyle@jsanconsulting.com'),
    ('JSAN215', 'avelmarthi@jsanconsulting.com'),
    ('JSAN260', 'aahmed@jsanconsulting.com'),
    ('JSAN016', 'dburlagadda@jsanconsulting.com'),
    ('JSAN258', 'rnpalthyavath@jsanconsulting.com'),
    ('JSAN273', 'svineeth@jsanconsulting.com'),
    ('JSAN159', 'ssoma@jsanconsulting.com'),
    ('JSAN201', 'vgdundigal@jsanconsulting.com'),
    ('JSAN218', 'mkatta@jsanconsulting.com'),
    ('JSAN263', 'sedapalapati@jsanconsulting.com'),
    ('JSAN008', 'ssgunti@jsanconsulting.com'),
    ('JSAN279', 'skasturi@jsanconsulting.com'),
    ('JSAN122', 'bharode@jsanconsulting.com'),
    ('JSAN099', 'psadvitha@jsanconsulting.com'),
    ('JSAN297', 'kmadduri@jsanconsulting.com'),
    ('JSAN226', 'hksankranti@jsanconsulting.com'),
    ('JSAN281', 'nraavi@jsanconsulting.com'),
    ('JSAN168', 'sravula@jsanconsulting.com'),
    ('JSAN214', 'rsramanukolanu@jsanconsulting.com'),
    ('JSAN304', 'vchunchannakota@jsanconsulting.com'),
    ('JSAN289', 'rsmunipally@jsanconsulting.com'),
    ('JSAN207', 'beluri@jsanconsulting.com'),
    ('JSAN150', 'vpkunapureddi@jsanconsulting.com'),
    ('JSAN264', 'pjahnavi@jsanconsulting.com'),
    ('JSAN270', 'cdhumale@jsanconsulting.com'),
    ('JSAN282', 'suttarapally@jsanconsulting.com'),
    ('JSAN285', 'ptripuraneni@jsanconsulting.com'),
    ('JSAN017', 'kkgayaru@jsanconsulting.com'),
    ('JSAN223', 'pjain@jsanconsulting.com'),
    ('JSAN283', 'janthati@jsanconsulting.com'),
    ('JSAN211', 'nspinni@jsanconsulting.com'),
    ('JSAN331', 'mkkabothu@jsanconsulting.com'),
    ('JSAN325', 'achaturvedi@jsanconsulting.com'),
    ('JSAN323', 'mpeta@jsanconsulting.com'),
    ('JSAN330', 'mshyamala@jsanconsulting.com'),
    ('JSAN284', 'gmpasala@jsanconsulting.com'),
    ('JSAN276', 'akolla@jsanconsulting.com'),
    ('JSAN227', 'vsmnidumolu@jsanconsulting.com'),
    ('JSAN288', 'sagarwal@jsanconsulting.com'),
    ('JSAN196', 'sbaddam@jsanconsulting.com'),
]


class Command(BaseCommand):
    help = 'Set real emails on exited employees from the baked Exit-sheet roster (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        User = get_user_model()
        dry = opts['dry_run']
        updated = skipped = conflicts = 0

        for jid, email in ROSTER:
            email = (email or '').strip().lower()
            if not email:
                continue
            emp = Employee.objects.filter(employee_id=jid).select_related('user').first()
            if not emp:
                self.stdout.write(f'  skip {jid}: no such employee')
                skipped += 1
                continue
            if emp.employment_status != 'EXITED':
                self.stdout.write(f'  skip {jid}: not EXITED (status {emp.employment_status})')
                skipped += 1
                continue
            user = emp.user
            if emp.email == email and (not user or user.email == email):
                skipped += 1
                continue
            # Email must not already belong to a different record.
            if (Employee.objects.filter(email__iexact=email).exclude(pk=emp.pk).exists()
                    or (user and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists())
                    or (not user and User.objects.filter(email__iexact=email).exists())):
                self.stdout.write(self.style.WARNING(f'  CONFLICT {jid}: {email} already used by another record - left unchanged'))
                conflicts += 1
                continue
            self.stdout.write(f'  {jid}: {emp.email} -> {email}')
            if not dry:
                with transaction.atomic():
                    emp.email = email
                    emp.save(update_fields=['email', 'updated_at'])
                    if user:
                        user.email = email
                        user.username = email
                        user.save(update_fields=['email', 'username'])
            updated += 1

        verb = 'Would update' if dry else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {updated}, skipped {skipped}, conflicts {conflicts}.'))
