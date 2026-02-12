from __future__ import annotations

from typing import Any

from .models import AuditEvent


def create_audit_event(
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    status: str = AuditEvent.STATUS_SUCCESS,
    message: str = "",
    metadata: dict[str, Any] | None = None,
    user=None,
    request=None,
) -> AuditEvent:
    request_user = getattr(request, "user", None)
    actor = user or request_user
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    path = getattr(request, "path", "") if request else ""
    method = getattr(request, "method", "") if request else ""
    ip_address = ""
    user_agent = ""
    if request:
        ip_address = request.META.get("REMOTE_ADDR", "")[:64]
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

    return AuditEvent.objects.create(
        user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        status=status,
        message=message,
        metadata=metadata or {},
        path=path,
        method=method,
        ip_address=ip_address,
        user_agent=user_agent,
    )
