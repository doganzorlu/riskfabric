from django.core.management.base import BaseCommand, CommandError

from integration.models import IntegrationSyncRun
from integration.services import execute_eam_sync


class Command(BaseCommand):
    help = "Run EAM sync using configured plugin/version."

    def add_arguments(self, parser):
        parser.add_argument("--direction", default=IntegrationSyncRun.DIRECTION_INBOUND)
        parser.add_argument("--plugin-name", default=None)
        parser.add_argument("--plugin-version", default=None)
        parser.add_argument("--excel-file-path", default=None)

    def handle(self, *args, **options):
        context = {}
        if options.get("excel_file_path"):
            context["excel_file_path"] = options["excel_file_path"]

        sync_run = execute_eam_sync(
            direction=options["direction"],
            plugin_name=options.get("plugin_name"),
            plugin_version=options.get("plugin_version"),
            context=context or None,
        )

        if sync_run.status == IntegrationSyncRun.STATUS_FAILED:
            raise CommandError(
                f"Sync failed: id={sync_run.id}, plugin={sync_run.plugin_name}:{sync_run.plugin_version}, message={sync_run.message}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed: id={sync_run.id}, status={sync_run.status}, plugin={sync_run.plugin_name}:{sync_run.plugin_version}"
            )
        )
