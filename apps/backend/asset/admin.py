from django.contrib import admin

from .models import Asset, AssetDependency, AssetGroup, AssetStatus, AssetType, BusinessUnit, CostCenter, Section


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "business_unit")
    search_fields = ("code", "name")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "cost_center")
    search_fields = ("code", "name")


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(AssetStatus)
class AssetStatusAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(AssetGroup)
class AssetGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "asset_name", "asset_type", "asset_status", "parent_asset")
    search_fields = ("asset_code", "asset_name")
    list_filter = ("asset_type", "asset_status", "asset_group")


@admin.register(AssetDependency)
class AssetDependencyAdmin(admin.ModelAdmin):
    list_display = ("source_asset", "target_asset", "dependency_type", "strength")
    list_filter = ("dependency_type",)
