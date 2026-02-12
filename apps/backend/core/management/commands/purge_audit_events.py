from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AuditEvent


class Command(BaseCommand):
    help = "Purge old audit events older than N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=180, help="Retention window in days (default: 180).")
        parser.add_argument("--dry-run", action="store_true", help="Only show how many rows would be deleted.")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        dry_run = bool(options["dry_run"])

        cutoff = timezone.now() - timedelta(days=days)
        queryset = AuditEvent.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if dry_run:
            self.stdout.write(f"[dry-run] {count} audit events older than {days} days would be deleted.")
            return

        deleted_count, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} audit events older than {days} days."))
