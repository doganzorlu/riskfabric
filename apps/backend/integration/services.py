from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import IntegrationSyncRun
from .registry import get_plugin


def execute_eam_sync(
    *,
    direction: str = IntegrationSyncRun.DIRECTION_INBOUND,
    plugin_name: str | None = None,
    plugin_version: str | None = None,
    context: dict[str, Any] | None = None,
    raise_on_error: bool = False,
) -> IntegrationSyncRun:
    selected_plugin_name = plugin_name or settings.EAM_PLUGIN_NAME
    selected_plugin_version = plugin_version or settings.EAM_PLUGIN_VERSION

    sync_run = IntegrationSyncRun.objects.create(
        external_system="eam",
        direction=direction,
        status=IntegrationSyncRun.STATUS_RUNNING,
        plugin_name=selected_plugin_name,
        plugin_version=selected_plugin_version,
        started_at=timezone.now(),
    )

    try:
        plugin = get_plugin(selected_plugin_name, selected_plugin_version)
        result = plugin.run(direction=direction, context=context)
        sync_run.status = IntegrationSyncRun.STATUS_SUCCESS
        sync_run.message = str(result)
    except Exception as exc:  # noqa: BLE001
        sync_run.status = IntegrationSyncRun.STATUS_FAILED
        sync_run.message = str(exc)
        if raise_on_error:
            raise
    finally:
        sync_run.finished_at = timezone.now()
        sync_run.save(update_fields=["status", "message", "finished_at"])

    return sync_run
