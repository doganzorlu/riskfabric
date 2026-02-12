from rest_framework import serializers

from .models import IntegrationSyncRun
from .registry import list_plugins


class IntegrationSyncRequestSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(
        choices=IntegrationSyncRun.DIRECTION_CHOICES,
        default=IntegrationSyncRun.DIRECTION_INBOUND,
    )
    plugin_name = serializers.CharField(required=False)
    plugin_version = serializers.CharField(required=False)
    context = serializers.DictField(required=False)


class IntegrationSyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSyncRun
        fields = [
            "id",
            "external_system",
            "direction",
            "status",
            "plugin_name",
            "plugin_version",
            "idempotency_key",
            "correlation_id",
            "message",
            "started_at",
            "finished_at",
            "created_at",
        ]


class PluginCatalogSerializer(serializers.Serializer):
    plugins = serializers.ListField(child=serializers.DictField(), default=list_plugins)
