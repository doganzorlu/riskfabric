from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_code",
            "asset_name",
            "parent_asset",
            "asset_type",
            "asset_status",
            "asset_group",
            "section",
            "cost_center",
            "business_unit",
            "brand",
            "model",
            "serial_number",
            "is_mobile_equipment",
            "default_work_type",
            "integration_source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
