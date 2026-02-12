from datetime import timedelta

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import AuditEvent
from core.tasks import purge_old_audit_events


class AuditRetentionCommandTests(TestCase):
    def test_purge_audit_events_deletes_old_rows(self):
        old_event = AuditEvent.objects.create(action="risk.create", entity_type="risk", entity_id="1")
        recent_event = AuditEvent.objects.create(action="risk.update", entity_type="risk", entity_id="2")

        AuditEvent.objects.filter(id=old_event.id).update(created_at=timezone.now() - timedelta(days=200))
        call_command("purge_audit_events", days=180)

        self.assertFalse(AuditEvent.objects.filter(id=old_event.id).exists())
        self.assertTrue(AuditEvent.objects.filter(id=recent_event.id).exists())

    def test_purge_audit_events_dry_run_keeps_rows(self):
        old_event = AuditEvent.objects.create(action="risk.create", entity_type="risk", entity_id="3")
        AuditEvent.objects.filter(id=old_event.id).update(created_at=timezone.now() - timedelta(days=200))

        call_command("purge_audit_events", days=180, dry_run=True)
        self.assertTrue(AuditEvent.objects.filter(id=old_event.id).exists())

    @patch("core.tasks.call_command")
    def test_celery_task_invokes_purge_command(self, mocked_call_command):
        purge_old_audit_events()
        mocked_call_command.assert_called_once_with("purge_audit_events", days=180)
