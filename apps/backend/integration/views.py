from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import create_audit_event
from core.models import AuditEvent
from core.permissions import CanRunSync

from .registry import list_plugins
from .serializers import IntegrationSyncRequestSerializer, IntegrationSyncRunSerializer
from .services import execute_eam_sync


class IntegrationPluginCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"plugins": list_plugins()})


class EamSyncView(APIView):
    permission_classes = [CanRunSync]

    def post(self, request):
        serializer = IntegrationSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sync_run = execute_eam_sync(
            direction=serializer.validated_data.get("direction"),
            plugin_name=serializer.validated_data.get("plugin_name"),
            plugin_version=serializer.validated_data.get("plugin_version"),
            context=serializer.validated_data.get("context"),
        )

        http_status = status.HTTP_201_CREATED
        if sync_run.status == "failed":
            http_status = status.HTTP_400_BAD_REQUEST

        create_audit_event(
            action="eam.sync.execute",
            entity_type="integration_sync",
            entity_id=sync_run.id,
            status=AuditEvent.STATUS_SUCCESS if sync_run.status == "success" else AuditEvent.STATUS_FAILED,
            message=sync_run.message,
            metadata={"plugin_name": sync_run.plugin_name, "plugin_version": sync_run.plugin_version},
            request=request,
        )

        return Response(IntegrationSyncRunSerializer(sync_run).data, status=http_status)
