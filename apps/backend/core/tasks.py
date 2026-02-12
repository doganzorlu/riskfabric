from celery import shared_task
from django.conf import settings
from django.core.management import call_command


@shared_task(name="core.tasks.purge_old_audit_events")
def purge_old_audit_events() -> None:
    call_command("purge_audit_events", days=settings.AUDIT_RETENTION_DAYS)
