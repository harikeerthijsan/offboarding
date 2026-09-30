import datetime
from django.db.models import Model
from .models import AuditLog


def _make_serializable(obj):
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, Model):
        # Store a stable reference (pk) rather than the object itself.
        return obj.pk
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # Fallback for any other non-JSON-native type (Decimal, UUID, etc.)
    return str(obj)


def log_action(actor, action, target_obj, changes=None, request=None):
    ip = None
    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        action=action,
        target_type=target_obj.__class__.__name__ if target_obj else '',
        target_id=target_obj.pk if target_obj else None,
        target_repr=str(target_obj) if target_obj else '',
        changes=_make_serializable(changes or {}),
        ip_address=ip,
    )
