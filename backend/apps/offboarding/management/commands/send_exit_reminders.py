"""Send a reminder to the IT team, HR, and the employee's manager a set number of
days (default 7) before the employee's last working day.

Creates in-app notifications and sends email (via the configured EMAIL_BACKEND —
console in dev). Idempotent: each offboarding is reminded once (exit_reminder_sent).

Intended to run once a day via the OS scheduler, e.g.:
  Windows Task Scheduler → daily → `python manage.py send_exit_reminders`
  cron → `0 8 * * *  python manage.py send_exit_reminders`

Usage:
  python manage.py send_exit_reminders [--days 7] [--dry-run]
"""
import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification
from apps.offboarding.models import ResignationRequest

User = get_user_model()


def _one2one(obj, attr):
    try:
        return getattr(obj, attr)
    except ObjectDoesNotExist:
        return None


def _last_working_day(r):
    np = _one2one(r, 'notice_period')
    if np and np.actual_last_working_day:
        return np.actual_last_working_day
    if np and np.expected_last_working_day:
        return np.expected_last_working_day
    return r.last_working_date


class Command(BaseCommand):
    help = 'Notify IT, HR and the manager N days before an employee\'s last working day.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=getattr(settings, 'EXIT_REMINDER_DAYS', 7))
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        days = opts['days']
        dry = opts['dry_run']
        today = timezone.localdate()
        target = today + datetime.timedelta(days=days)

        # Ongoing offboardings that haven't been reminded yet.
        candidates = (ResignationRequest.objects
                      .select_related('employee__user', 'employee__manager__user', 'notice_period')
                      .filter(exit_reminder_sent=False)
                      .exclude(status__in=['DRAFT', 'REJECTED', 'CANCELLED']))

        it_users = list(User.objects.filter(role__in=['IT', 'ADMIN'], is_active=True))
        hr_users = list(User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True))

        sent = 0
        for r in candidates:
            lwd = _last_working_day(r)
            if lwd != target:
                continue

            emp = r.employee
            name = f"{emp.first_name} {emp.last_name}"
            title = 'Upcoming employee exit'
            msg = (f"{name} ({emp.employee_id})'s last working day is {lwd} "
                   f"— {days} day(s) away. Please ensure asset return/IT clearance, "
                   f"knowledge transfer and finance clearance are on track.")

            # recipients: IT team + HR + the employee's manager
            recipients = {u.id: u for u in it_users + hr_users}
            mgr = emp.manager
            if mgr and mgr.user:
                recipients[mgr.user.id] = mgr.user

            self.stdout.write(f"[{lwd}] {name} -> {len(recipients)} recipient(s)")
            if dry:
                continue

            with transaction.atomic():
                for u in recipients.values():
                    Notification.objects.create(
                        recipient=u, notification_type='EXIT_REMINDER',
                        title=title, message=msg,
                        related_object_type='ResignationRequest', related_object_id=r.pk,
                        related_offboarding=r,
                    )
                emails = [u.email for u in recipients.values() if u.email]
                if emails:
                    try:
                        send_mail(
                            subject=f"[JSAN PEOPLE360] {title}: {name}",
                            message=msg,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=emails,
                            fail_silently=True,
                        )
                    except Exception as e:  # noqa: BLE001
                        self.stderr.write(self.style.WARNING(f"  email failed: {e}"))
                r.exit_reminder_sent = True
                r.save(update_fields=['exit_reminder_sent', 'updated_at'])
            sent += 1

        verb = 'Would send' if dry else 'Sent'
        self.stdout.write(self.style.SUCCESS(
            f"{verb} exit reminders for {sent} employee(s) with last working day on {target} "
            f"({days} days from {today})."))
