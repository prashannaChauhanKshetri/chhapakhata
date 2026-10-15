"""Record important business actions in the activity log."""

from __future__ import annotations

from typing import Any

from django.db import models

from .models import ActivityLog


def client_ip(request: Any) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_activity(
    actor: Any,
    action: str,
    target: models.Model | None = None,
    message: str = "",
    metadata: dict[str, Any] | None = None,
    request: Any = None,
) -> ActivityLog:
    """Write one activity entry.

    ``action`` is a dotted verb such as ``"invoice.cancelled"``.
    """
    return ActivityLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target._meta.label_lower if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        target_label=str(target)[:120] if target is not None else "",
        message=message[:255],
        metadata=metadata or {},
        ip_address=client_ip(request),
    )
