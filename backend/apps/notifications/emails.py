"""Shared helper to mirror in-app notifications to email.

Every in-app Notification can also be emailed to the recipient via
``send_notification_email``. Best-effort: a mail failure is logged but never
breaks the request. Controlled by the NOTIFICATION_EMAILS_ENABLED setting.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_notification_email(recipient_user, title, message):
    if not getattr(settings, 'NOTIFICATION_EMAILS_ENABLED', True):
        return
    email = getattr(recipient_user, 'email', '')
    if not email:
        return
    try:
        send_mail(
            subject=f"[Offboarding] {title}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('Notification email to %s failed: %s', email, e)
