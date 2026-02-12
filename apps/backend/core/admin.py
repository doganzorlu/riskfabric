from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "status", "user")
    list_filter = ("status", "action", "entity_type", "created_at")
    search_fields = ("action", "entity_type", "entity_id", "message", "user__username")
    ordering = ("-created_at",)
