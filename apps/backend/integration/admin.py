from django.contrib import admin

from .models import IntegrationSyncRun


@admin.register(IntegrationSyncRun)
class IntegrationSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "external_system",
        "direction",
        "status",
        "plugin_name",
        "plugin_version",
        "created_at",
    )
    list_filter = ("external_system", "direction", "status", "plugin_name", "plugin_version")
    search_fields = ("idempotency_key", "correlation_id", "message", "plugin_name", "plugin_version")
