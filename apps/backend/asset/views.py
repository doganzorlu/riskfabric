from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .access import accessible_assets, can_view_all_assets
from .models import Asset
from .serializers import AssetSerializer


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    search_fields = ("asset_code", "asset_name")
    ordering_fields = ("asset_code", "asset_name", "created_at", "updated_at")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Asset.objects.select_related(
            "parent_asset",
            "asset_type",
            "asset_status",
            "asset_group",
            "section",
            "cost_center",
            "business_unit",
        )
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(id__in=accessible_assets(self.request.user))
        return qs
