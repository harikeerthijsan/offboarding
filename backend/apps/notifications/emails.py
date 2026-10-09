"""Mirror in-app notifications to email (production-grade).

Every in-app Notification is also emailed to the recipient via
``send_notification_email``. Design goals:

* Reliable: only sends what was asked; never raises into the request.
* Non-blocking: against a real SMTP server the send runs in a background thread
  so a slow mail server can't add latency to API responses. Against the
  console/locmem backends (dev + tests) it sends synchronously so output is
  visible immediately and tests stay deterministic.
* Branded: sends a multipart plain-text + HTML message, with an optional
  "View in app" button when FRONTEND_URL is configured.

Controlled by the NOTIFICATION_EMAILS_ENABLED setting.
"""
import logging
import threading
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def _html_body(title, message, link):
    safe_title = escape(title)
    safe_msg = escape(message).replace('\n', '<br>')
    button = ''
    if link:
        button = (
            f'<tr><td style="padding-top:20px">'
            f'<a href="{escape(link)}" '
            f'style="display:inline-block;background:#0d5aa7;color:#ffffff;'
            f'text-decoration:none;padding:10px 20px;border-radius:8px;'
            f'font-weight:600;font-size:14px">View in app</a></td></tr>'
        )
    return f"""\
<!DOCTYPE html>
<html><body style="margin:0;background:#f4f6fb;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#101828">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:24px">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border:1px solid #e6e9f0;border-radius:12px;overflow:hidden;max-width:560px;width:100%">
        <tr><td style="height:6px;background:linear-gradient(90deg,#1e85d8,#4f46e5,#06b6d4)"></td></tr>
        <tr><td style="padding:28px 28px 8px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.08em;color:#98a2b3;text-transform:uppercase">JSAN PEOPLE360</div>
          <h1 style="margin:10px 0 0;font-size:19px;color:#101828">{safe_title}</h1>
        </td></tr>
        <tr><td style="padding:8px 28px 4px;font-size:14px;line-height:1.6;color:#566072">{safe_msg}</td></tr>
        <tr><td style="padding:0 28px 28px">
          <table role="presentation" cellpadding="0" cellspacing="0">{button}</table>
        </td></tr>
        <tr><td style="padding:16px 28px;background:#f8fafd;border-top:1px solid #e6e9f0;font-size:12px;color:#98a2b3">
          This is an automated message from JSAN PEOPLE360. Please do not reply.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _deliver(msg, email):
    try:
        msg.send(fail_silently=False)
        logger.info('Notification email sent to %s', email)
    except Exception as e:  # noqa: BLE001
        logger.warning('Notification email to %s failed: %s', email, e)


def send_notification_email(recipient_user, title, message, link=None):
    if not getattr(settings, 'NOTIFICATION_EMAILS_ENABLED', True):
        return
    email = getattr(recipient_user, 'email', '')
    if not email:
        return

    # Resolve an action link: explicit link wins, else fall back to FRONTEND_URL.
    frontend = getattr(settings, 'FRONTEND_URL', '')
    action_link = link or (frontend or None)

    msg = EmailMultiAlternatives(
        subject=f"[JSAN PEOPLE360] {title}",
        body=message,  # plain-text part
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(_html_body(title, message, action_link), 'text/html')

    # Only offload to a thread for a real SMTP server; console/locmem (dev + tests)
    # send synchronously so output is immediate and test assertions are deterministic.
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if 'smtp' in backend:
        threading.Thread(target=_deliver, args=(msg, email), daemon=True).start()
    else:
        _deliver(msg, email)
