from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction

from asset.models import Asset, AssetDependency, AssetGroup, AssetStatus, AssetType, BusinessUnit, CostCenter, Section

from .base import EamIntegrationPlugin


@dataclass
class SheetConfig:
    primary_name: str


class ExcelBootstrapPluginV1(EamIntegrationPlugin):
    plugin_name = "excel_bootstrap"
    plugin_version = "v1"

    SHEETS = {
        "business_unit": SheetConfig(primary_name="İşletme"),
        "cost_center": SheetConfig(primary_name="Sarfyeri"),
        "section": SheetConfig(primary_name="Kısım"),
        "asset_type": SheetConfig(primary_name="Varlık Türleri"),
        "asset_status": SheetConfig(primary_name="Varlık Durumu"),
        "asset_group": SheetConfig(primary_name="Varlık Grupları"),
        "asset": SheetConfig(primary_name="Varlıklar"),
    }

    def run(self, *, direction: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if direction != "inbound":
            return {
                "plugin": f"{self.plugin_name}:{self.plugin_version}",
                "direction": direction,
                "status": "skipped",
                "message": "Excel bootstrap plugin supports inbound direction only.",
            }

        context = context or {}
        workbook_path_value = context.get("excel_file_path") or settings.EAM_EXCEL_FILE_PATH
        if not workbook_path_value:
            raise ValueError("excel_file_path is required for excel_bootstrap plugin.")

        workbook_path = Path(workbook_path_value)
        if not workbook_path.exists():
            raise FileNotFoundError(f"Excel file not found: {workbook_path}")

        import xlrd  # lazy import to avoid hard failure before dependency install

        workbook = xlrd.open_workbook(str(workbook_path))

        with transaction.atomic():
            result = {
                "business_units": self._sync_business_units(workbook),
                "cost_centers": self._sync_cost_centers(workbook),
                "sections": self._sync_sections(workbook),
                "asset_types": self._sync_asset_types(workbook),
                "asset_statuses": self._sync_asset_statuses(workbook),
                "asset_groups": self._sync_asset_groups(workbook),
                "assets": self._sync_assets(workbook),
            }

        return {
            "plugin": f"{self.plugin_name}:{self.plugin_version}",
            "direction": direction,
            "status": "success",
            "message": "Excel bootstrap sync completed.",
            "details": result,
        }

    def _get_sheet(self, workbook: Any, key: str):
        sheet_name = self.SHEETS[key].primary_name
        return workbook.sheet_by_name(sheet_name)

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if raw.endswith(".0") and raw.replace(".", "", 1).isdigit():
            raw = raw[:-2]
        return raw

    def _rows(self, sheet) -> list[dict[str, str]]:
        if sheet.nrows < 1:
            return []
        headers = [self._normalize(sheet.cell_value(0, idx)) for idx in range(sheet.ncols)]
        parsed: list[dict[str, str]] = []
        for row_idx in range(1, sheet.nrows):
            row_values = [self._normalize(sheet.cell_value(row_idx, idx)) for idx in range(sheet.ncols)]
            if not any(row_values):
                continue
            parsed.append(dict(zip(headers, row_values)))
        return parsed

    def _sync_business_units(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "business_unit"))
        count = 0
        for row in rows:
            code = row.get("İşletme Kodu", "")
            name = row.get("İşletme Tanımı", "")
            if not code:
                continue
            BusinessUnit.objects.update_or_create(code=code, defaults={"name": name})
            count += 1
        return count

    def _sync_cost_centers(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "cost_center"))
        count = 0
        for row in rows:
            code = row.get("Sarfyeri Kodu", "")
            name = row.get("Sarfyeri Tanımı", "")
            business_unit_code = row.get("İşletme Kodu", "")
            if not code or not business_unit_code:
                continue
            try:
                business_unit = BusinessUnit.objects.get(code=business_unit_code)
            except BusinessUnit.DoesNotExist:
                continue
            CostCenter.objects.update_or_create(
                code=code,
                defaults={"name": name, "business_unit": business_unit},
            )
            count += 1
        return count

    def _sync_sections(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "section"))
        count = 0
        for row in rows:
            code = row.get("Kısım Kodu", "")
            name = row.get("Kısım Tanımı", "")
            cost_center_code = row.get("Sarfyeri Kodu", "")
            if not code or not cost_center_code:
                continue
            try:
                cost_center = CostCenter.objects.get(code=cost_center_code)
            except CostCenter.DoesNotExist:
                continue
            Section.objects.update_or_create(code=code, defaults={"name": name, "cost_center": cost_center})
            count += 1
        return count

    def _sync_asset_types(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "asset_type"))
        count = 0
        for row in rows:
            code = row.get("Varlık Türü Kodu", "")
            name = row.get("Varlık Türü Tanımı", "")
            if not code:
                continue
            AssetType.objects.update_or_create(code=code, defaults={"name": name})
            count += 1
        return count

    def _sync_asset_statuses(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "asset_status"))
        count = 0
        for row in rows:
            code = row.get("Varlık Durum Kodu", "")
            name = row.get("Varlık Durum Tanımı", "")
            if not code:
                continue
            AssetStatus.objects.update_or_create(code=code, defaults={"name": name})
            count += 1
        return count

    def _sync_asset_groups(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "asset_group"))
        count = 0
        for row in rows:
            code = row.get("Varlık Grubu Kodu", "")
            name = row.get("Varlık Grubu Tanımı", "")
            if not code:
                continue
            AssetGroup.objects.update_or_create(code=code, defaults={"name": name})
            count += 1
        return count

    def _sync_assets(self, workbook: Any) -> int:
        rows = self._rows(self._get_sheet(workbook, "asset"))

        # Pass 1: upsert all assets without parent links.
        for row in rows:
            asset_code = row.get("Varlık Kodu", "")
            asset_name = row.get("Varlık Tanımı", "")
            if not asset_code:
                continue

            asset_type = AssetType.objects.filter(code=row.get("Varlık Türü", "")).first()
            asset_status = AssetStatus.objects.filter(code=row.get("Varlık Durumu", "")).first()
            asset_group = AssetGroup.objects.filter(code=row.get("Varlık Grubu Kodu", "")).first()
            section = Section.objects.filter(code=row.get("Kısım Kodu", "")).first()
            cost_center = CostCenter.objects.filter(code=row.get("Sarfyeri Kodu", "")).first()
            business_unit = BusinessUnit.objects.filter(code=row.get("İşletme Kodu", "")).first()

            mobile_raw = (row.get("Dolaşan Ekipman", "") or "").strip().lower()
            is_mobile = mobile_raw in {"1", "true", "yes", "y", "e", "evet"}

            Asset.objects.update_or_create(
                asset_code=asset_code,
                defaults={
                    "asset_name": asset_name or asset_code,
                    "asset_type": asset_type,
                    "asset_status": asset_status,
                    "asset_group": asset_group,
                    "section": section,
                    "cost_center": cost_center,
                    "business_unit": business_unit,
                    "brand": row.get("Marka", ""),
                    "model": row.get("Model", ""),
                    "serial_number": row.get("Seri No", ""),
                    "is_mobile_equipment": is_mobile,
                    "default_work_type": row.get("Varsayılan İş tipi", ""),
                    "integration_source": "excel_bootstrap",
                },
            )

        # Pass 2: parent links and dependency edges.
        synced_count = 0
        for row in rows:
            asset_code = row.get("Varlık Kodu", "")
            if not asset_code:
                continue
            asset = Asset.objects.filter(asset_code=asset_code).first()
            if not asset:
                continue

            parent_code = row.get("Bağlı olduğu varlık Kodu", "")
            parent_asset = Asset.objects.filter(asset_code=parent_code).first() if parent_code else None

            if asset.parent_asset_id != (parent_asset.id if parent_asset else None):
                asset.parent_asset = parent_asset
                asset.save(update_fields=["parent_asset", "updated_at"])

            if parent_asset:
                AssetDependency.objects.update_or_create(
                    source_asset=asset,
                    target_asset=parent_asset,
                    dependency_type=AssetDependency.DEPENDENCY_TYPE_LOGICAL,
                    defaults={"strength": 3},
                )

            synced_count += 1

        return synced_count
