from __future__ import annotations

from datetime import timedelta

import xlrd
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from asset.models import (
    Asset,
    AssetDependency,
    AssetGroup,
    AssetStatus,
    AssetType,
    BusinessUnit,
    CostCenter,
    Section,
)
from django.db.models import Q
from risk.models import (
    Risk,
    RiskApproval,
    RiskAsset,
    RiskCategory,
    RiskControl,
    CriticalService,
    Hazard,
    HazardLink,
    ImpactEscalationCurve,
    RiskException,
    RiskIssue,
    RiskReview,
    RiskScoringMethod,
    RiskScoringSnapshot,
    RiskScoringDread,
    RiskScoringOwasp,
    RiskScoringCvss,
    RiskSource,
    RiskTreatment,
    Scenario,
    ServiceAssetMapping,
    ServiceBIAProfile,
    ServiceProcess,
    Assessment,
    Vulnerability,
    ControlTestPlan,
    ControlTestRun,
    ComplianceFramework,
    ComplianceRequirement,
    ContinuityStrategy,
    GovernanceProgram,
    PolicyStandard,
    PolicyControlMapping,
    PolicyRiskMapping,
)


class Command(BaseCommand):
    help = "Seed OSB asset tree and realistic risks based on inventory.xls"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Skip deleting existing data before re-seeding.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        if not options.get("no_reset"):
            self.stdout.write(self.style.WARNING("Resetting seeded data..."))
            with transaction.atomic():
                # Risk scoring inputs and history
                RiskScoringSnapshot.objects.all().delete()
                RiskScoringDread.objects.all().delete()
                RiskScoringOwasp.objects.all().delete()
                RiskScoringCvss.objects.all().delete()

                # Risk lifecycle
                RiskAsset.objects.all().delete()
                RiskApproval.objects.all().delete()
                RiskReview.objects.all().delete()
                RiskTreatment.objects.all().delete()
                RiskException.objects.all().delete()
                RiskIssue.objects.all().delete()
                Risk.objects.all().delete()

                # Assessments & vulnerabilities
                Vulnerability.objects.all().delete()
                Assessment.objects.all().delete()

                # Control testing & compliance
                ControlTestRun.objects.all().delete()
                ControlTestPlan.objects.all().delete()
                PolicyControlMapping.objects.all().delete()
                PolicyRiskMapping.objects.all().delete()
                PolicyStandard.objects.all().delete()
                GovernanceProgram.objects.all().delete()
                ComplianceRequirement.objects.all().delete()
                ComplianceFramework.objects.all().delete()

                # Resilience objects
                ServiceAssetMapping.objects.all().delete()
                ServiceBIAProfile.objects.all().delete()
                ServiceProcess.objects.all().delete()
                ContinuityStrategy.objects.all().delete()
                CriticalService.objects.all().delete()
                ImpactEscalationCurve.objects.all().delete()
                HazardLink.objects.all().delete()
                Scenario.objects.all().delete()
                Hazard.objects.all().delete()

                # Controls, categories, sources
                RiskControl.objects.all().delete()
                RiskCategory.objects.all().delete()
                RiskSource.objects.all().delete()

                # Assets and hierarchy
                AssetDependency.objects.all().delete()
                Asset.objects.all().delete()
                Section.objects.all().delete()
                CostCenter.objects.all().delete()
                BusinessUnit.objects.all().delete()
                AssetType.objects.all().delete()
                AssetGroup.objects.all().delete()
                AssetStatus.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("Seed reset completed."))

        # Core reference data
        status_active = AssetStatus.objects.filter(code="K").first()
        if not status_active:
            status_active, _ = AssetStatus.objects.get_or_create(code="ACTIVE", defaults={"name": "Aktif"})

        # Risk categories and sources
        for name in [
            "Altyapi",
            "Enerji",
            "Dogalgaz",
            "Su",
            "Tesis",
            "Is Sagligi Guvenligi",
            "Uyumluluk",
            "Operasyonel",
            "Bilgi Teknolojileri",
        ]:
            RiskCategory.objects.get_or_create(
                category_type=RiskCategory.TYPE_RISK,
                name=name,
                defaults={"description": f"{name} riskleri"},
            )

        for name in ["Operasyon", "Bakim", "Dis Kaynak", "Tedarikci", "Hava Kosullari", "Guvenlik"]:
            RiskSource.objects.get_or_create(name=name)

        method_specs = [
            ("CIA_V1", "CIA (Confidentiality/Integrity/Availability)", RiskScoringMethod.METHOD_CIA, 1.0, 1.0, 1.0),
            ("CVSS_V3", "CVSS v3", RiskScoringMethod.METHOD_CVSS, 1.0, 1.0, 1.0),
            ("DREAD_V1", "DREAD", RiskScoringMethod.METHOD_DREAD, 1.0, 1.0, 1.0),
            ("CLASSIC_V1", "Classic", RiskScoringMethod.METHOD_CLASSIC, 1.0, 1.0, 1.0),
            ("OWASP_V1", "OWASP", RiskScoringMethod.METHOD_OWASP, 1.0, 1.0, 1.0),
        ]
        for code, name, method_type, lw, iw, tw in method_specs:
            RiskScoringMethod.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "method_type": method_type,
                    "likelihood_weight": lw,
                    "impact_weight": iw,
                    "treatment_effectiveness_weight": tw,
                    "is_active": True,
                    "is_default": code == "CIA_V1",
                },
            )
        scoring_method = (
            RiskScoringMethod.objects.filter(is_active=True, is_default=True).first()
            or RiskScoringMethod.objects.filter(is_active=True).first()
        )

        User = get_user_model()
        requester = User.objects.filter(is_active=True).order_by("id").first()
        reviewer = User.objects.filter(is_active=True).order_by("-id").first()
        if requester is None:
            requester = User.objects.create_user(username="seed_user", password="pass1234", email="seed@example.com")
            reviewer = requester

        # Inventory data
        inventory_path = "/Users/dogan/Documents/Projects/ownprojects/riskfabric/apps/datasource/inventory.xls"

        def cell_value(value) -> str:
            if value is None:
                return ""
            if isinstance(value, float):
                if value.is_integer():
                    return str(int(value))
            return str(value).strip()

        try:
            book = xlrd.open_workbook(inventory_path)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Failed to load inventory.xls: {exc}"))
            return

        def load_sheet(name: str):
            if name not in book.sheet_names():
                return None
            sheet = book.sheet_by_name(name)
            headers = [cell_value(sheet.cell_value(0, c)) for c in range(sheet.ncols)]
            rows = []
            for r in range(1, sheet.nrows):
                row = {headers[c]: cell_value(sheet.cell_value(r, c)) for c in range(sheet.ncols)}
                rows.append(row)
            return rows

        isletme_rows = load_sheet("Isletme") or []
        if not isletme_rows:
            isletme_rows = load_sheet("İşletme") or []
        sarfyeri_rows = load_sheet("Sarfyeri") or []
        kisim_rows = load_sheet("Kısım") or []
        tur_rows = load_sheet("Varlık Türleri") or []
        durum_rows = load_sheet("Varlık Durumu") or []
        grup_rows = load_sheet("Varlık Grupları") or []
        varlik_rows = load_sheet("Varlıklar") or []

        # Seed Business Units (Isletme)
        bu_map = {}
        for row in isletme_rows:
            code = row.get("İşletme Kodu", "").strip()
            name = row.get("İşletme Tanımı", "").strip()
            if not code:
                continue
            bu, _ = BusinessUnit.objects.get_or_create(code=code, defaults={"name": name or code})
            bu_map[code] = bu

        # Seed Cost Centers (Sarfyeri)
        cc_map = {}
        for row in sarfyeri_rows:
            code = row.get("Sarfyeri Kodu", "").strip()
            name = row.get("Sarfyeri Tanımı", "").strip()
            bu_code = row.get("İşletme Kodu", "").strip()
            if not code or not bu_code or bu_code not in bu_map:
                continue
            cc, _ = CostCenter.objects.get_or_create(
                code=code,
                defaults={"name": name or code, "business_unit": bu_map[bu_code]},
            )
            cc_map[code] = cc

        # Seed Sections (Kisim)
        section_map = {}
        for row in kisim_rows:
            code = row.get("Kısım Kodu", "").strip()
            name = row.get("Kısım Tanımı", "").strip()
            cc_code = row.get("Sarfyeri Kodu", "").strip()
            if not code or not cc_code or cc_code not in cc_map:
                continue
            sec, _ = Section.objects.get_or_create(
                code=code,
                defaults={"name": name or code, "cost_center": cc_map[cc_code]},
            )
            section_map[code] = sec

        # Asset types/status/groups
        for row in tur_rows:
            code = row.get("Varlık Türü Kodu", "").strip()
            name = row.get("Varlık Türü Tanımı", "").strip()
            if code:
                AssetType.objects.get_or_create(code=code, defaults={"name": name or code})

        for row in durum_rows:
            code = row.get("Varlık Durum Kodu", "").strip()
            name = row.get("Varlık Durum Tanımı", "").strip()
            if code:
                AssetStatus.objects.get_or_create(code=code, defaults={"name": name or code})

        for row in grup_rows:
            code = row.get("Varlık Grubu Kodu", "").strip()
            name = row.get("Varlık Grubu Tanımı", "").strip()
            if code:
                AssetGroup.objects.get_or_create(code=code, defaults={"name": name or code})

        # Asset creation from inventory
        asset_map = {}
        pending_parent = []

        def bool_from(value: str) -> bool:
            v = (value or "").strip().upper()
            return v in {"E", "EVET", "1", "TRUE", "VAR"}

        for row in varlik_rows:
            code = row.get("Varlık Kodu", "").strip()
            name = row.get("Varlık Tanımı", "").strip()
            parent_code = row.get("Bağlı olduğu varlık Kodu", "").strip()
            type_code = row.get("Varlık Türü", "").strip()
            status_code = row.get("Varlık Durumu", "").strip()
            group_code = row.get("Varlık Grubu Kodu", "").strip()
            section_code = row.get("Kısım Kodu", "").strip()
            cost_center_code = row.get("Sarfyeri Kodu", "").strip()
            bu_code = row.get("İşletme Kodu", "").strip()

            if not code:
                continue

            asset_type = AssetType.objects.filter(code=type_code).first() if type_code else None
            if type_code and asset_type is None:
                asset_type, _ = AssetType.objects.get_or_create(code=type_code, defaults={"name": type_code})

            asset_status = AssetStatus.objects.filter(code=status_code).first() if status_code else None
            asset_group = AssetGroup.objects.filter(code=group_code).first() if group_code else None

            section = section_map.get(section_code)
            cost_center = cc_map.get(cost_center_code)
            business_unit = bu_map.get(bu_code)

            asset, _ = Asset.objects.get_or_create(
                asset_code=code,
                defaults={
                    "asset_name": name or code,
                    "parent_asset": None,
                    "asset_type": asset_type,
                    "asset_status": asset_status or status_active,
                    "asset_group": asset_group,
                    "section": section,
                    "cost_center": cost_center or (section.cost_center if section else None),
                    "business_unit": business_unit or (cost_center.business_unit if cost_center else None),
                    "brand": row.get("Marka", ""),
                    "model": row.get("Model", ""),
                    "serial_number": row.get("Seri No", ""),
                    "is_mobile_equipment": bool_from(row.get("Dolaşan Ekipman", "")),
                    "default_work_type": row.get("Varsayılan İş tipi", ""),
                    "integration_source": "seed_inventory",
                },
            )
            asset_map[code] = asset
            if parent_code:
                pending_parent.append((asset, parent_code))

        for asset, parent_code in pending_parent:
            parent = asset_map.get(parent_code)
            if parent and asset.parent_asset_id != parent.id:
                asset.parent_asset = parent
                asset.save(update_fields=["parent_asset", "updated_at"])

        # Geo/seismic metadata enrichment (based on inventory codes, no new assets)
        def assign_geo_metadata(asset: Asset) -> None:
            code = asset.asset_code
            name = asset.asset_name.upper()
            if code.startswith(("TM.", "ADM.", "YDM.", "DC.")) or "TM" in name or "ADM" in name or "YDM" in name:
                zone, seismic, criticality = "zone-1", 0.35, 5
            elif code.startswith(("GAS.", "SU.")):
                zone, seismic, criticality = "zone-2", 0.30, 4
            elif code.startswith(("MOBESE.", "VRF.", "LOK.BINA.")):
                zone, seismic, criticality = "zone-3", 0.25, 3
            elif asset.asset_group and asset.asset_group.code in {"ARAC", "ITFAIYE"}:
                zone, seismic, criticality = "zone-4", 0.20, 3
            else:
                zone, seismic, criticality = "zone-3", 0.25, 3

            updates = []
            if asset.geo_zone != zone:
                asset.geo_zone = zone
                updates.append("geo_zone")
            if float(asset.seismic_risk_coefficient) != seismic:
                asset.seismic_risk_coefficient = seismic
                updates.append("seismic_risk_coefficient")
            if asset.infrastructure_criticality != criticality:
                asset.infrastructure_criticality = criticality
                updates.append("infrastructure_criticality")
            if updates:
                updates.append("updated_at")
                asset.save(update_fields=updates)

        for asset in asset_map.values():
            assign_geo_metadata(asset)

        def add_dependency(source_code: str, target_code: str, dependency_type: str = "hard") -> None:
            source = asset_map.get(source_code)
            target = asset_map.get(target_code)
            if not source or not target:
                return
            AssetDependency.objects.get_or_create(
                source_asset=source,
                target_asset=target,
                dependency_type=dependency_type,
            )

        asset_to_service = {}

        def add_risk(asset: Asset, title: str, description: str, category: str, source: str, likelihood: int, impact: int, owner: str, days: int) -> Risk:
            critical_service = asset_to_service.get(asset.id)
            cia_defaults = {}
            if scoring_method and scoring_method.method_type == RiskScoringMethod.METHOD_CIA:
                cia_defaults = {
                    "confidentiality": impact,
                    "integrity": impact,
                    "availability": impact,
                }
            risk, _ = Risk.objects.get_or_create(
                title=f"{asset.asset_code} - {title}",
                defaults={
                    "description": description,
                    "category": category,
                    "source": source,
                    "primary_asset": asset,
                    "likelihood": likelihood,
                    "impact": impact,
                    **cia_defaults,
                    "status": Risk.STATUS_OPEN,
                    "owner": owner,
                    "due_date": today + timedelta(days=days),
                    "scoring_method": scoring_method,
                    "critical_service": critical_service,
                },
            )
            if critical_service and risk.critical_service_id != critical_service.id:
                risk.critical_service = critical_service
                risk.save(update_fields=["critical_service", "updated_at"])
            RiskAsset.objects.update_or_create(
                risk=risk,
                asset=asset,
                defaults={"is_primary": True},
            )
            related_edges = AssetDependency.objects.filter(
                source_asset=asset,
            ).select_related("target_asset")
            for edge in related_edges:
                RiskAsset.objects.update_or_create(
                    risk=risk,
                    asset=edge.target_asset,
                    defaults={"is_primary": edge.target_asset_id == asset.id},
                )
            related_edges = AssetDependency.objects.filter(
                target_asset=asset,
            ).select_related("source_asset")
            for edge in related_edges:
                RiskAsset.objects.update_or_create(
                    risk=risk,
                    asset=edge.source_asset,
                    defaults={"is_primary": edge.source_asset_id == asset.id},
                )

            # Ensure dependency graph has at least one edge for demo risks.
            linked_asset_ids = list(risk.risk_assets.values_list("asset_id", flat=True))
            has_edge = AssetDependency.objects.filter(
                source_asset_id__in=linked_asset_ids,
                target_asset_id__in=linked_asset_ids,
            ).exists()
            if not has_edge:
                candidate = None
                if asset.parent_asset_id:
                    candidate = asset.parent_asset
                if candidate is None:
                    candidate = (
                        Asset.objects.filter(
                            Q(cost_center=asset.cost_center) | Q(asset_group=asset.asset_group)
                        )
                        .exclude(id=asset.id)
                        .order_by("asset_code")
                        .first()
                    )
                if candidate:
                    AssetDependency.objects.get_or_create(
                        source_asset=asset,
                        target_asset=candidate,
                        dependency_type=AssetDependency.DEPENDENCY_TYPE_SOFT,
                    )
                    RiskAsset.objects.update_or_create(
                        risk=risk,
                        asset=candidate,
                        defaults={"is_primary": False},
                    )

            treatment, created = RiskTreatment.objects.get_or_create(
                risk=risk,
                title="Operasyonel iyileştirme planı",
                defaults={
                    "strategy": RiskTreatment.STRATEGY_MITIGATE,
                    "status": RiskTreatment.STATUS_IN_PROGRESS,
                    "owner": owner,
                    "due_date": today + timedelta(days=max(days // 2, 14)),
                    "progress_percent": 40,
                    "notes": "Saha gözlemi ve bakım planına bağlandı.",
                },
            )
            if created or not risk.scoring_history.exists():
                risk.refresh_scores(actor="seed")

            RiskReview.objects.get_or_create(
                risk=risk,
                reviewer=reviewer,
                defaults={
                    "decision": RiskReview.DECISION_REVISIT,
                    "comments": "Gözden geçirme yapıldı, izleme devam edecek.",
                    "next_review_date": today + timedelta(days=60),
                },
            )

            RiskApproval.objects.get_or_create(
                risk=risk,
                requested_by=requester,
                status=RiskApproval.STATUS_APPROVED,
                defaults={
                    "decided_by": reviewer,
                    "decided_at": now,
                    "comments": "Onaylandı, uygulama devam ediyor.",
                },
            )
            RiskApproval.objects.get_or_create(
                risk=risk,
                requested_by=requester,
                status=RiskApproval.STATUS_PENDING,
                defaults={
                    "comments": "Ek onay ihtiyacı: yeni bakım planı.",
                },
            )
            return risk

        # Dependencies based on inventory codes
        tm_assets = sorted([a for a in asset_map.values() if "TM" in a.asset_name], key=lambda a: a.asset_code)
        adm_assets = sorted([a for a in asset_map.values() if "ADM" in a.asset_name], key=lambda a: a.asset_code)
        ydm_assets = sorted([a for a in asset_map.values() if "YDM" in a.asset_name], key=lambda a: a.asset_code)

        if tm_assets:
            for idx, adm in enumerate(adm_assets):
                tm = tm_assets[idx % len(tm_assets)]
                AssetDependency.objects.get_or_create(source_asset=adm, target_asset=tm, dependency_type="hard")

        if adm_assets:
            for idx, ydm in enumerate(ydm_assets):
                adm = adm_assets[idx % len(adm_assets)]
                AssetDependency.objects.get_or_create(source_asset=ydm, target_asset=adm, dependency_type="hard")

        # VRF mapping: indoor -> outdoor -> central controller -> building (use inventory only)
        for asset in list(asset_map.values()):
            if asset.asset_code.startswith("VRF.IC."):
                parts = asset.asset_code.split(".")
                if len(parts) >= 3:
                    suffix = parts[2]
                    outdoor_code = f"VRF.DIS.{suffix}"
                    add_dependency(asset.asset_code, outdoor_code, "hard")
                    controller = asset_map.get(f"VRF.KON.{suffix}")
                    if controller:
                        add_dependency(outdoor_code, controller.asset_code, "hard")
                    building_code = f"LOK.BINA.{suffix}"
                    if building_code in asset_map:
                        if controller:
                            add_dependency(controller.asset_code, building_code, "soft")

        # MOBESE components -> intersection
        for asset in list(asset_map.values()):
            if asset.asset_code.startswith("MOBESE.") and asset.asset_code.count(".") == 2:
                base = asset.asset_code.rsplit(".", 1)[0]
                add_dependency(asset.asset_code, base, "hard")

        # Utility dependencies
        add_dependency("GAS.DAGITIM.01", "GAS.BOTAS.01", "hard")
        for idx in range(1, 5):
            add_dependency(f"SU.DEPO.{idx}", "SU.KUYU.SAHA", "hard")
        add_dependency("SU.HAT.ANA", "SU.DEPO.1", "hard")

        # Critical Services, Processes, BIA, Hazards, and Scenarios (resilience extension)
        def select_assets(prefixes=None, group_codes=None, name_contains=None):
            prefixes = prefixes or []
            group_codes = group_codes or []
            name_contains = name_contains or []
            selected = []
            for asset in asset_map.values():
                if prefixes and any(asset.asset_code.startswith(p) for p in prefixes):
                    selected.append(asset)
                    continue
                if group_codes and asset.asset_group and asset.asset_group.code in group_codes:
                    selected.append(asset)
                    continue
                if name_contains and any(term in asset.asset_name.upper() for term in name_contains):
                    selected.append(asset)
            return selected

        service_specs = [
            ("SERV-ELC", "Elektrik Dağıtımı", "TM/ADM/YDM dağıtımı ve saha altyapısı."),
            ("SERV-GAS", "Doğalgaz Dağıtımı", "BOTAŞ bağlantısı ve OSB içi dağıtım."),
            ("SERV-WTR", "Su Dağıtımı", "Kuyu, depo ve ana hatlarla su tedariki."),
            ("SERV-DC", "Veri Merkezi Operasyonu", "Tier-II+ veri merkezi ve kritik BT altyapısı."),
            ("SERV-SEC", "Güvenlik İzleme (MOBESE)", "Kavşak MOBESE izleme ve kayıt sürekliliği."),
            ("SERV-FLEET", "Saha Operasyon Filosu", "Araç filosu ve saha ekip sürekliliği."),
            ("SERV-FIRE", "İtfaiye ve Acil Müdahale", "Acil müdahale ve yangın hizmetleri."),
            ("SERV-FAC", "Tesis ve Kampüs Yönetimi", "Binalar, VRF ve kampüs altyapısı."),
        ]

        service_map = {}
        for code, name, desc in service_specs:
            service, _ = CriticalService.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": desc, "owner": "kurumsal.dayaniklilik"},
            )
            service_map[code] = service

        process_specs = {
            "SERV-ELC": [
                ("ELC-OPS", "Dağıtım Operasyonları", "TM/ADM/YDM enerji sürekliliği."),
                ("ELC-MNT", "Bakım ve Müdahale", "Kesinti ve arıza müdahalesi."),
            ],
            "SERV-GAS": [
                ("GAS-OPS", "Gaz Basınç ve Hat Yönetimi", "Basınç izleme ve kontrol."),
                ("GAS-MNT", "Hat ve Vana Bakımı", "Saha bakım operasyonları."),
            ],
            "SERV-WTR": [
                ("WTR-OPS", "Su Dağıtım Operasyonları", "Kuyu, depo ve hat akışı."),
                ("WTR-QLT", "Su Kalitesi Kontrolü", "Kalite, dezenfeksiyon, numune."),
            ],
            "SERV-DC": [
                ("DC-OPS", "BT Operasyonları", "Sunucu, storage, network sürekliliği."),
                ("DC-ENV", "Enerji ve Soğutma", "UPS ve soğutma sürekliliği."),
            ],
            "SERV-SEC": [
                ("SEC-OPS", "Kamera İzleme", "Kayıt ve izleme sürekliliği."),
                ("SEC-MNT", "Saha Envanter Bakımı", "Kabin, UPS ve kamera bakımı."),
            ],
            "SERV-FLEET": [
                ("FLT-OPS", "Saha Araç Kullanımı", "Saha ekip ulaşımı."),
                ("FLT-MNT", "Araç Bakım Yönetimi", "Periyodik bakım sürekliliği."),
            ],
            "SERV-FIRE": [
                ("FIRE-OPS", "Acil Müdahale", "Müdahale sürekliliği."),
                ("FIRE-READY", "Hazırlık Kontrolleri", "Ekip ve araç hazırlığı."),
            ],
            "SERV-FAC": [
                ("FAC-OPS", "Kampüs Operasyonları", "Bina ve kampüs hizmetleri."),
                ("FAC-HVAC", "İklimlendirme", "VRF ve iç ünite sürekliliği."),
            ],
        }

        process_map = {}
        for service_code, processes in process_specs.items():
            service = service_map[service_code]
            for proc_code, proc_name, proc_desc in processes:
                proc, _ = ServiceProcess.objects.get_or_create(
                    service=service,
                    code=proc_code,
                    defaults={"name": proc_name, "description": proc_desc},
                )
                process_map[(service_code, proc_code)] = proc

        service_assets = {
            "SERV-ELC": select_assets(name_contains=["TM", "ADM", "YDM", "TRAFO", "ENERJI"]),
            "SERV-GAS": select_assets(name_contains=["GAZ", "DOGALGAZ", "DOĞALGAZ", "BOTAŞ", "REGULATOR", "REGÜLATÖR"]),
            "SERV-WTR": select_assets(name_contains=["SU", "ARITMA", "KUYU", "DEPO", "HAT", "POMPA", "TESISAT"]),
            "SERV-DC": select_assets(name_contains=["SUNUCU", "SERVER", "VERI", "DATA", "STORAGE", "SAN", "UPS", "JENERATOR", "JENERATÖR"]),
            "SERV-SEC": select_assets(name_contains=["MOBESE", "KAMERA", "CCTV", "NVR", "DVR"]),
            "SERV-FLEET": select_assets(name_contains=["ARAC", "ARAÇ", "FILO"], group_codes=["ARAC"]),
            "SERV-FIRE": select_assets(name_contains=["ITFAIYE", "YANGIN", "HIDRANT", "HİDRANT"], group_codes=["ITFAIYE"]),
            "SERV-FAC": select_assets(name_contains=["BINA", "KAMPUS", "KAMPÜS", "LOJISTIK", "LOJİSTİK", "OFIS", "OFİS", "VRF"]),
        }

        for service_code, assets in service_assets.items():
            service = service_map[service_code]
            for asset in assets:
                asset_to_service[asset.id] = service
                process = None
                if service_code == "SERV-ELC":
                    process = process_map[(service_code, "ELC-OPS")]
                elif service_code == "SERV-GAS":
                    process = process_map[(service_code, "GAS-OPS")]
                elif service_code == "SERV-WTR":
                    process = process_map[(service_code, "WTR-OPS")]
                elif service_code == "SERV-DC":
                    process = process_map[(service_code, "DC-OPS")]
                elif service_code == "SERV-SEC":
                    process = process_map[(service_code, "SEC-OPS")]
                elif service_code == "SERV-FLEET":
                    process = process_map[(service_code, "FLT-OPS")]
                elif service_code == "SERV-FIRE":
                    process = process_map[(service_code, "FIRE-OPS")]
                elif service_code == "SERV-FAC":
                    process = process_map[(service_code, "FAC-OPS")]

                ServiceAssetMapping.objects.get_or_create(
                    service=service,
                    process=process,
                    asset=asset,
                )

        bia_categories = [
            (ImpactEscalationCurve.CATEGORY_FINANCIAL, "Finansal"),
            (ImpactEscalationCurve.CATEGORY_OPERATIONAL, "Operasyonel"),
            (ImpactEscalationCurve.CATEGORY_LEGAL, "Hukuki"),
            (ImpactEscalationCurve.CATEGORY_REPUTATIONAL, "İtibar"),
            (ImpactEscalationCurve.CATEGORY_ENVIRONMENTAL, "Çevresel"),
            (ImpactEscalationCurve.CATEGORY_HUMAN_SAFETY, "İnsan Güvenliği"),
        ]

        def build_default_curve(mtpd_hours: int):
            mtpd_minutes = max(mtpd_hours * 60, 1)
            steps = [
                (0.25, ServiceBIAProfile.IMPACT_LEVEL_MINOR),
                (0.50, ServiceBIAProfile.IMPACT_LEVEL_DEGRADED),
                (0.75, ServiceBIAProfile.IMPACT_LEVEL_SEVERE),
                (1.00, ServiceBIAProfile.IMPACT_LEVEL_CRITICAL),
            ]
            curve = []
            last_time = 0
            for ratio, level in steps:
                time_value = int(mtpd_minutes * ratio)
                if time_value <= last_time:
                    time_value = last_time + 1
                curve.append({"time_minutes": time_value, "level": level})
                last_time = time_value
            return curve

        bia_defaults = {
            "SERV-ELC": {
                "mao": 8,
                "rto": 2,
                "rpo": 1,
                "notes": "Enerji sürekliliği kritik.",
                "criticality": ServiceBIAProfile.CRITICALITY_INFRASTRUCTURE,
                "impacts": (5, 4, 3, 4, 3, 4),
            },
            "SERV-GAS": {
                "mao": 12,
                "rto": 4,
                "rpo": 2,
                "notes": "Doğalgaz arzı kesintisiz olmalı.",
                "criticality": ServiceBIAProfile.CRITICALITY_INFRASTRUCTURE,
                "impacts": (4, 4, 3, 3, 3, 3),
            },
            "SERV-WTR": {
                "mao": 12,
                "rto": 4,
                "rpo": 2,
                "notes": "Su arzında tolerans sınırlı.",
                "criticality": ServiceBIAProfile.CRITICALITY_INFRASTRUCTURE,
                "impacts": (4, 3, 4, 3, 2, 3),
            },
            "SERV-DC": {
                "mao": 4,
                "rto": 1,
                "rpo": 1,
                "notes": "Veri merkezi sürekliliği kritik.",
                "criticality": ServiceBIAProfile.CRITICALITY_BUSINESS,
                "impacts": (5, 4, 1, 2, 3, 4),
            },
            "SERV-SEC": {
                "mao": 6,
                "rto": 2,
                "rpo": 1,
                "notes": "Güvenlik izleme kesintisi kritik.",
                "criticality": ServiceBIAProfile.CRITICALITY_SUPPORT,
                "impacts": (4, 2, 2, 3, 2, 3),
            },
            "SERV-FLEET": {
                "mao": 24,
                "rto": 8,
                "rpo": 4,
                "notes": "Filo sürekliliği orta kritik.",
                "criticality": ServiceBIAProfile.CRITICALITY_SUPPORT,
                "impacts": (3, 3, 1, 2, 2, 2),
            },
            "SERV-FIRE": {
                "mao": 2,
                "rto": 1,
                "rpo": 1,
                "notes": "Acil müdahale kesintisi kabul edilemez.",
                "criticality": ServiceBIAProfile.CRITICALITY_LIFE,
                "impacts": (5, 3, 3, 5, 3, 4),
            },
            "SERV-FAC": {
                "mao": 24,
                "rto": 8,
                "rpo": 4,
                "notes": "Tesis hizmetleri orta kritik.",
                "criticality": ServiceBIAProfile.CRITICALITY_SUPPORT,
                "impacts": (3, 2, 2, 2, 2, 2),
            },
        }

        for code, service in service_map.items():
            defaults = bia_defaults.get(code)
            if defaults:
                mao = defaults["mao"]
                rto = defaults["rto"]
                rpo = defaults["rpo"]
                notes = defaults["notes"]
                criticality = defaults["criticality"]
                impacts = defaults["impacts"]
            else:
                mao, rto, rpo, notes = (24, 8, 4, "Örnek BİA profili.")
                criticality = ServiceBIAProfile.CRITICALITY_SUPPORT
                impacts = (2, 2, 1, 1, 1, 1)
            bia, _ = ServiceBIAProfile.objects.get_or_create(
                service=service,
                defaults={
                    "mao_hours": mao,
                    "rto_hours": rto,
                    "rpo_hours": rpo,
                    "service_criticality": criticality,
                    "impact_operational": impacts[0],
                    "impact_financial": impacts[1],
                    "impact_environmental": impacts[2],
                    "impact_safety": impacts[3],
                    "impact_legal": impacts[4],
                    "impact_reputation": impacts[5],
                    "impact_escalation_curve": build_default_curve(mao),
                    "crisis_trigger_rules": {
                        "mtpd_percentage_trigger": 0.75,
                        "impact_level_trigger": ServiceBIAProfile.IMPACT_LEVEL_CRITICAL,
                        "environmental_severity_trigger": 4 if impacts[2] >= 4 else None,
                        "safety_severity_trigger": 3 if impacts[3] >= 3 else None,
                    },
                    "notes": notes,
                },
            )
            for category, label in bia_categories:
                ImpactEscalationCurve.objects.get_or_create(
                    bia_profile=bia,
                    impact_category=category,
                    defaults={
                        "t1_hours": 1,
                        "t1_label": f"{label} etki: kısa süreli aksama",
                        "t2_hours": 4,
                        "t2_label": f"{label} etki: hizmet seviyesi düşer",
                        "t3_hours": 8,
                        "t3_label": f"{label} etki: kritik bozulma",
                        "t4_hours": 24,
                        "t4_label": f"{label} etki: regülatif/operasyonel kritik",
                        "t5_hours": 72,
                        "t5_label": f"{label} etki: sürdürülemez seviye",
                    },
                )

        hazards = {
            "HZ-DEP": ("Deprem", Hazard.TYPE_NATURAL, "Deprem kaynaklı altyapı kesintileri."),
            "HZ-SEL": ("Sel/Su Baskını", Hazard.TYPE_NATURAL, "Yağış ve taşkın kaynaklı etkiler."),
            "HZ-KES": ("Enerji Kesintisi", Hazard.TYPE_UTILITY, "Şebeke kaynaklı enerji kesintisi."),
            "HZ-CYB": ("Siber Saldırı", Hazard.TYPE_CYBER, "Kritik sistemlere yönelik siber saldırı."),
            "HZ-EQP": ("Ekipman Arızası", Hazard.TYPE_INDUSTRIAL, "Kritik ekipman arızası."),
        }

        hazard_map = {}
        for code, (name, hazard_type, desc) in hazards.items():
            hazard, _ = Hazard.objects.get_or_create(
                code=code,
                defaults={"name": name, "hazard_type": hazard_type, "description": desc, "default_likelihood": 0.3},
            )
            hazard_map[code] = hazard

        hazard_service_links = {
            "HZ-DEP": ["SERV-ELC", "SERV-GAS", "SERV-WTR", "SERV-FAC", "SERV-DC"],
            "HZ-SEL": ["SERV-WTR", "SERV-FAC"],
            "HZ-KES": ["SERV-DC", "SERV-SEC", "SERV-FAC"],
            "HZ-CYB": ["SERV-DC", "SERV-SEC"],
            "HZ-EQP": ["SERV-ELC", "SERV-GAS", "SERV-WTR", "SERV-FAC"],
        }

        for hazard_code, service_codes in hazard_service_links.items():
            hazard = hazard_map[hazard_code]
            for service_code in service_codes:
                HazardLink.objects.get_or_create(
                    hazard=hazard,
                    service=service_map[service_code],
                )

        hazard_asset_links = {
            "HZ-DEP": select_assets(name_contains=["TM", "ADM", "YDM", "BINA"]),
            "HZ-SEL": select_assets(prefixes=["SU.", "LOK.BINA."]),
            "HZ-KES": select_assets(prefixes=["DC.", "MOBESE.", "VRF."]),
            "HZ-CYB": select_assets(prefixes=["DC.", "MOBESE."]),
            "HZ-EQP": select_assets(prefixes=["VRF.", "GAS.", "SU."]),
        }
        for hazard_code, assets in hazard_asset_links.items():
            hazard = hazard_map[hazard_code]
            for asset in assets:
                HazardLink.objects.get_or_create(
                    hazard=hazard,
                    asset=asset,
                )

        scenario_specs = [
            ("Deprem Sonrası Elektrik Kesintisi", "HZ-DEP", 24, "Deprem sonrası TM/ADM etkileri."),
            ("Deprem Sonrası Su Dağıtım Aksaması", "HZ-DEP", 12, "Kuyu ve depo erişimi kısıtlı."),
            ("Doğalgaz Basınç Düşüşü", "HZ-EQP", 8, "BOTAŞ basınç düşüşü senaryosu."),
            ("Gaz Hat Arızası ve Bölgesel Kesinti", "HZ-EQP", 6, "Hat izolasyonu ve basınç kaybı."),
            ("Su Hattı Sel Baskını", "HZ-SEL", 12, "Depo ve hat etkilenmesi."),
            ("Ana Depo Pompa Arızası", "HZ-EQP", 4, "Ana depo pompa arızası."),
            ("Veri Merkezi Enerji Kaybı", "HZ-KES", 6, "UPS devre dışı kalması."),
            ("Veri Merkezi Soğutma Kaybı", "HZ-EQP", 5, "VRF dış ünite arızası."),
            ("Siber Saldırı - Kamera İzleme", "HZ-CYB", 4, "MOBESE kayıt kesintisi."),
            ("MOBESE UPS Arızası", "HZ-EQP", 3, "Kabin UPS arızası."),
            ("Kavşak İletişim Kabini Su Baskını", "HZ-SEL", 6, "Kabin altyapısı etkilenir."),
        ]
        for name, hazard_code, hours, notes in scenario_specs:
            Scenario.objects.get_or_create(
                name=name,
                hazard=hazard_map[hazard_code],
                defaults={"duration_hours": hours, "notes": notes},
            )

        # Risk templates based on asset codes and groups
        for asset in asset_map.values():
            code = asset.asset_code
            name = asset.asset_name.upper()
            group_code = asset.asset_group.code if asset.asset_group else ""

            if "TM" in name:
                add_risk(asset, "TM Aşırı Yük", "Trafo merkezi pik talepte aşırı yüklenme riski.", "Enerji", "Operasyon", 4, 5, "elektrik.ekibi", 90)
                add_risk(asset, "TM Yağ Sızıntısı", "Trafo yağ sızıntısı nedeniyle arıza riski.", "Altyapi", "Bakim", 3, 4, "bakim.ekibi", 60)
                continue

            if "ADM" in name:
                add_risk(asset, "ADM Kesinti", "ADM dağıtım merkezinde kesinti riski.", "Altyapi", "Bakim", 3, 5, "elektrik.ekibi", 60)
                add_risk(asset, "ADM Baralar Arızalı", "ADM baralarında arıza riski.", "Altyapi", "Bakim", 3, 4, "bakim.ekibi", 60)
                continue

            if "YDM" in name:
                add_risk(asset, "YDM Kesinti", "YDM dağıtım merkezinde kesinti riski.", "Altyapi", "Bakim", 3, 5, "elektrik.ekibi", 60)
                continue

            if "ATIK SU" in name or "ARITMA" in name:
                add_risk(asset, "Arıtma Süreci Durması", "Arıtma prosesinde duruş nedeniyle çevresel risk.", "Cevre", "Operasyon", 3, 5, "cevre.ekibi", 30)
                add_risk(asset, "Deşarj Uygunsuzluğu", "Arıtma çıkış parametrelerinde uyumsuzluk riski.", "Uyumluluk", "Operasyon", 2, 5, "cevre.ekibi", 45)
                continue

            if "DOGALGAZ" in name or ("GAZ" in name and "HAT" in name) or code.startswith("GAS."):
                add_risk(asset, "Gaz Basınç Düşük", "Doğalgaz basınç düşüklüğü nedeniyle üretim etkilenir.", "Dogalgaz", "Dis Kaynak", 3, 4, "gaz.ekibi", 90)
                add_risk(asset, "Gaz Kaçağı", "Doğalgaz hatlarında kaçak ve patlama riski.", "Is Sagligi Guvenligi", "Operasyon", 2, 5, "gaz.ekibi", 45)
                continue

            if "SICAK SU" in name or "BUHAR" in name:
                add_risk(asset, "Buhar Hattı Basınç Kaybı", "Buhar hattında basınç kaybı riski.", "Enerji", "Operasyon", 3, 4, "bakim.ekibi", 60)
                add_risk(asset, "Hat İzolasyon Arızası", "Hat izolasyon arızası nedeniyle enerji kaybı riski.", "Enerji", "Bakim", 2, 3, "bakim.ekibi", 60)
                continue

            if "SU DEPO" in name or "SU DEPOLARI" in name or "KUYU" in name or code.startswith("SU."):
                add_risk(asset, "Su Basınç Dalgalanması", "Su hattında basınç dalgalanması riski.", "Su", "Operasyon", 3, 3, "su.ekibi", 90)
                add_risk(asset, "Pompa Arızası", "Su pompa arızası nedeniyle besleme kesintisi riski.", "Su", "Bakim", 3, 4, "su.ekibi", 45)
                continue

            if code.startswith("DC."):
                add_risk(asset, "DC UPS Arızası", "Veri merkezinde UPS arızası.", "Bilgi Teknolojileri", "Bakim", 3, 5, "it.ekibi", 45)
                add_risk(asset, "DC Soğutma Kaybı", "Veri merkezi soğutma kaybı.", "Bilgi Teknolojileri", "Operasyon", 3, 5, "it.ekibi", 30)
                continue

            if code.startswith("MOBESE.") and code.count(".") == 1:
                add_risk(asset, "Kamera İzleme Kesintisi", "MOBESE görüntü iletimi kesintisi riski.", "Operasyonel", "Operasyon", 3, 4, "guvenlik.ekibi", 30)
                continue

            if code.startswith("VRF.DIS."):
                add_risk(asset, "VRF Soğutma Kaybı", "VRF dış ünite arızası nedeniyle soğutma kaybı.", "Tesis", "Bakim", 3, 4, "bakim.ekibi", 45)
                continue

            if "TRAFO" in name or code.startswith("TESIS.TRF"):
                add_risk(asset, "Trafo Aşırı Yük", "Trafo aşırı yüklenmesi nedeniyle arıza riski.", "Enerji", "Operasyon", 3, 5, "elektrik.ekibi", 45)
                add_risk(asset, "Trafo Yağ Sızıntısı", "Trafo yağ sızıntısı nedeniyle arıza ve çevresel risk.", "Altyapi", "Bakim", 2, 4, "bakim.ekibi", 60)
                continue

            if "JENERATOR" in name or code.startswith("TESIS.JEN"):
                add_risk(asset, "Jeneratör Yakıt Riski", "Yakıt yetersizliği nedeniyle jeneratör devre dışı kalır.", "Enerji", "Operasyon", 3, 4, "elektrik.ekibi", 30)
                add_risk(asset, "Jeneratör Bakımsızlık", "Periyodik bakım eksikliği nedeniyle arıza riski.", "Operasyonel", "Bakim", 3, 3, "elektrik.ekibi", 60)
                continue

            if "UPS" in name or code.startswith("TESIS.UPS"):
                add_risk(asset, "UPS Akü Ömrü", "UPS akülerinin ömrünü doldurması nedeniyle kesinti riski.", "Bilgi Teknolojileri", "Bakim", 3, 4, "elektrik.ekibi", 45)
                continue

            if code.startswith("IT.NET.") or (group_code == "AGC" and "SW" in code):
                add_risk(asset, "Ağ Omurga Kesintisi", "Omurga cihaz arızası nedeniyle servis kesintisi riski.", "Bilgi Teknolojileri", "Operasyon", 3, 5, "it.ekibi", 30)
                add_risk(asset, "Konfigürasyon Hatası", "Yanlış konfigürasyon nedeniyle trafik yönlendirme hatası.", "Bilgi Teknolojileri", "Operasyon", 2, 4, "it.ekibi", 45)
                continue

            if code.startswith("IT.SEC.") or (group_code == "AGC" and "FW" in code):
                add_risk(asset, "Güvenlik Duvarı Kapasite", "Firewall kapasite aşımı nedeniyle güvenlik ve erişim riski.", "Bilgi Teknolojileri", "Operasyon", 3, 4, "guvenlik.ekibi", 45)
                add_risk(asset, "Kural Seti Uyumsuzluğu", "Kural seti revizyonu gecikmesi nedeniyle risk.", "Bilgi Teknolojileri", "Operasyon", 2, 3, "guvenlik.ekibi", 60)
                continue

            if code.startswith("IT.INFO.") or group_code == "BIL":
                add_risk(asset, "Bilgi Gizliliği Riski", "Arşiv ve kayıtların yetkisiz erişim riski.", "Uyumluluk", "Guvenlik", 3, 4, "guvenlik.ekibi", 60)
                add_risk(asset, "Veri Bütünlüğü Riski", "Kayıt bütünlüğünün bozulması riski.", "Uyumluluk", "Operasyon", 2, 4, "it.ekibi", 60)
                continue

            if code.startswith("IT.HW.") or group_code == "DON":
                add_risk(asset, "Donanım Arızası", "Kritik donanım arızası nedeniyle hizmet kesintisi.", "Bilgi Teknolojileri", "Bakim", 3, 4, "it.ekibi", 30)
                add_risk(asset, "Yedek Parça Riskleri", "Yedek parça tedarik gecikmesi riski.", "Operasyonel", "Tedarikci", 2, 3, "satinalma.ekibi", 45)
                continue

            if code.startswith("IT.SW.") or group_code == "YAZ":
                add_risk(asset, "Lisans Sürekliliği", "Lisans süresinin bitmesi ile hizmet kesintisi riski.", "Uyumluluk", "Tedarikci", 2, 4, "it.ekibi", 60)
                add_risk(asset, "Yama Gecikmesi", "Kritik yamaların gecikmesi nedeniyle güvenlik riski.", "Bilgi Teknolojileri", "Operasyon", 3, 4, "it.ekibi", 30)
                continue

            if code.startswith("IT.LIC.") or (group_code == "YAZ" and "LIS" in code):
                add_risk(asset, "Lisans Yenileme Gecikmesi", "Lisans yenileme gecikmesi nedeniyle uyumluluk riski.", "Uyumluluk", "Tedarikci", 2, 3, "satinalma.ekibi", 45)
                continue

            if code.startswith("IT.PROC.") or group_code == "SRH":
                add_risk(asset, "Süreç Kesintisi", "Kritik süreç kesintisi iş hedeflerini etkiler.", "Operasyonel", "Operasyon", 3, 4, "operasyon.ekibi", 45)
                continue

            if code.startswith("IT.SVC.") or (group_code == "SRH" and "HIZ" in code):
                add_risk(asset, "Hizmet Seviyesi Düşüşü", "Hizmet seviyesi hedeflerinin karşılanamaması riski.", "Operasyonel", "Operasyon", 3, 3, "it.ekibi", 30)
                continue

            if code.startswith("IT.ORG.") or group_code == "ORG":
                add_risk(asset, "Sözleşme Uyumsuzluğu", "SLA ve sözleşme şartlarına uyum riski.", "Uyumluluk", "Operasyon", 2, 3, "risk.ekibi", 60)
                continue

            if code.startswith("IT.PERS.") or group_code == "KBP":
                add_risk(asset, "Kritik Rol Riski", "Kritik rolün yedeklenmemesi operasyon riski oluşturur.", "Operasyonel", "Operasyon", 3, 4, "insankaynaklari.ekibi", 60)
                continue

            if group_code == "BINA":
                add_risk(asset, "Yangın Tatbikatı Eksiği", "Bina için yangın tatbikatı kaydı eksik.", "Is Sagligi Guvenligi", "Operasyon", 2, 4, "osg.ekibi", 60)
                continue

            if group_code == "ARAC":
                add_risk(asset, "Periyodik Bakım Gecikmesi", "Araç periyodik bakım gecikmesi.", "Operasyonel", "Bakim", 3, 3, "filo.ekibi", 30)
                continue

            if group_code == "ITFAIYE":
                add_risk(asset, "Hazırlık Kontrol Eksiği", "İtfaiye aracı hazırlık kontrolü eksik.", "Is Sagligi Guvenligi", "Operasyon", 2, 4, "itfaiye.ekibi", 30)
                continue

        # Seed controls and testing
        control_specs = [
            ("CTRL-ADM-001", "ADM Jeneratör Testi", "Enerji", "ADM jeneratörlerinin aylık testleri."),
            ("CTRL-DC-001", "Veri Merkezi UPS Bakımı", "Bilgi Teknolojileri", "UPS sistemleri için periyodik bakım."),
            ("CTRL-GAS-001", "Doğalgaz Kaçak Kontrolü", "Is Sagligi Guvenligi", "Hat ve vana noktalarında kaçak kontrolü."),
            ("CTRL-SU-001", "Su Deposu Seviye Kontrolü", "Altyapi", "Depo seviye sensörlerinin günlük kontrolü."),
            ("CTRL-MOB-001", "MOBESE Kamera Sağlık Kontrolü", "Operasyonel", "Kamera/UPS kabini sağlık kontrolü."),
        ]
        controls = []
        for code, name, category, desc in control_specs:
            control, _ = RiskControl.objects.get_or_create(
                code=code,
                defaults={"name": name, "category": category, "description": desc},
            )
            controls.append(control)

        for control in controls:
            plan, _ = ControlTestPlan.objects.get_or_create(
                control=control,
                defaults={
                    "owner": "kontrol.ekibi",
                    "frequency": ControlTestPlan.FREQUENCY_QUARTERLY,
                    "next_due_date": today + timedelta(days=45),
                    "notes": "Standart kontrol planı.",
                },
            )
            ControlTestRun.objects.get_or_create(
                plan=plan,
                tested_at=today - timedelta(days=14),
                tester="denetim.ekibi",
                defaults={
                    "result": ControlTestRun.RESULT_PASS,
                    "effectiveness_score": 4,
                    "notes": "Örnek test koşusu.",
                },
            )

        # Seed governance programs
        governance_specs = [
            ("Kurumsal Risk Yönetimi Programı", "risk.ekibi", GovernanceProgram.STATUS_ACTIVE, "MOSB genelinde risk iştahı, izleme ve raporlama süreçlerini yürütür.", today + timedelta(days=365)),
            ("Uyum ve Mevzuat Programı (EPDK/KVKK)", "uyum.ekibi", GovernanceProgram.STATUS_ACTIVE, "Enerji sektörü düzenlemeleri ve KVKK uyum gereksinimlerinin takibini sağlar.", today + timedelta(days=180)),
            ("Bilgi Güvenliği ve OT Güvenliği Programı", "bilgi.guvenligi", GovernanceProgram.STATUS_ACTIVE, "BT/OT varlıkları için güvenlik kontrollerini ve izleme süreçlerini yönetir.", today + timedelta(days=270)),
            ("Operasyonel Süreklilik Programı", "süreklilik.ekibi", GovernanceProgram.STATUS_ACTIVE, "Kritik hizmetlerde RTO/RPO hedefleri ve süreklilik stratejilerini takip eder.", today + timedelta(days=270)),
            ("İş Sağlığı ve Güvenliği Programı", "osg.ekibi", GovernanceProgram.STATUS_ACTIVE, "Saha güvenliği, ekipman kontrolleri ve tatbikatları kapsar.", today + timedelta(days=365)),
            ("Altyapı ve Enerji İşletme Programı", "enerji.ekibi", GovernanceProgram.STATUS_ACTIVE, "Arıtma, TM ve enerji tesisleri için işletme ve bakım performansını izler.", today + timedelta(days=365)),
        ]
        for name, owner, status, objective, review_date in governance_specs:
            GovernanceProgram.objects.get_or_create(
                name=name,
                defaults={
                    "owner": owner,
                    "status": status,
                    "objective": objective,
                    "review_date": review_date,
                },
            )

        # Seed policies and mappings
        policy_specs = [
            ("BG-001", "Bilgi Güvenliği Politikası", "Bilgi Güvenliği", "bilgi.guvenligi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=365), today + timedelta(days=365), "Bilgi varlıklarının gizlilik, bütünlük ve erişilebilirliğini güvence altına alır."),
            ("KVKK-001", "Kişisel Veri Koruma Politikası", "Uyumluluk", "hukuk.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=240), today + timedelta(days=365), "Kişisel verilerin işlenmesi ve saklanmasına ilişkin kuralları belirler."),
            ("OPS-001", "Operasyonel Süreklilik Politikası", "Süreklilik", "süreklilik.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=180), today + timedelta(days=365), "Kritik hizmetlerde süreklilik hedeflerini ve sorumlulukları tanımlar."),
            ("ISG-001", "İş Sağlığı ve Güvenliği Politikası", "İSG", "osg.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=300), today + timedelta(days=365), "Saha güvenliği, bakım prosedürleri ve tatbikat standartlarını belirler."),
            ("ENERJI-001", "Enerji ve Elektrik İşletme Politikası", "Enerji", "enerji.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=210), today + timedelta(days=365), "TM, jeneratör ve UPS bakım/işletme standartlarını tanımlar."),
            ("ARITMA-001", "Arıtma ve Su Yönetimi Politikası", "Altyapı", "altyapi.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=150), today + timedelta(days=365), "Arıtma tesisleri ve su altyapısı için işletme ve kalite kriterlerini belirler."),
            ("TED-001", "Tedarikçi Güvenliği Politikası", "Tedarikçi", "satinalma.ekibi", PolicyStandard.STATUS_ACTIVE, today - timedelta(days=120), today + timedelta(days=365), "Üçüncü taraf risk değerlendirmesi ve sözleşme şartlarını kapsar."),
        ]
        policies = {}
        for code, name, category, owner, status, effective_date, review_date, desc in policy_specs:
            policy, _ = PolicyStandard.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "owner": owner,
                    "status": status,
                    "effective_date": effective_date,
                    "review_date": review_date,
                    "description": desc,
                },
            )
            policies[code] = policy

        controls_by_code = {control.code: control for control in controls}
        policy_control_links = [
            ("BG-001", "CTRL-DC-001", "UPS bakım kontrolü ile uyumlu."),
            ("BG-001", "CTRL-MOB-001", "Güvenlik kamera kontrolleri ile ilişkilidir."),
            ("KVKK-001", "CTRL-MOB-001", "Kamera kayıtlarının KVKK uyumunu destekler."),
            ("OPS-001", "CTRL-ADM-001", "Jeneratör testleri süreklilik hedefini destekler."),
            ("ISG-001", "CTRL-GAS-001", "Gaz hattı güvenliği kontrolleri ile uyumludur."),
            ("ENERJI-001", "CTRL-ADM-001", "Jeneratör bakım ve test kayıtlarını içerir."),
            ("ENERJI-001", "CTRL-DC-001", "UPS bakım kontrolleri ile uyumludur."),
            ("ARITMA-001", "CTRL-SU-001", "Su seviyesi ve kalite kontrolleri ile uyumludur."),
            ("TED-001", "CTRL-SU-001", "Tedarikçi bakım planı kayıtlarını içerir."),
        ]
        for policy_code, control_code, notes in policy_control_links:
            policy = policies.get(policy_code)
            control = controls_by_code.get(control_code)
            if not policy or not control:
                continue
            PolicyControlMapping.objects.get_or_create(
                policy=policy,
                control=control,
                defaults={"notes": notes},
            )

        risk_candidates = list(Risk.objects.order_by("-created_at")[:12])
        policy_risk_links = [
            ("BG-001", 0, "Bilgi güvenliği riskleri politika kapsamında izlenir."),
            ("KVKK-001", 1, "Kişisel veri riskleri için kabul kriterleri belirlenir."),
            ("OPS-001", 2, "Süreklilik riskleri için aksiyon planı oluşturulur."),
            ("ISG-001", 3, "İSG riskleri için kontrol listesi ve eğitim şartı vardır."),
            ("ENERJI-001", 4, "Enerji altyapısı riskleri bakım planı ile izlenir."),
            ("ARITMA-001", 5, "Arıtma ve su altyapısı riskleri işletme kriterleri ile yönetilir."),
            ("TED-001", 6, "Tedarikçi riskleri için sözleşme şartları uygulanır."),
        ]
        for policy_code, risk_idx, notes in policy_risk_links:
            if risk_idx >= len(risk_candidates):
                continue
            policy = policies.get(policy_code)
            risk = risk_candidates[risk_idx]
            if not policy or not risk:
                continue
            PolicyRiskMapping.objects.get_or_create(
                policy=policy,
                risk=risk,
                defaults={"notes": notes},
            )

        # Seed compliance frameworks and requirements
        framework_specs = [
            ("ISO27001", "ISO/IEC 27001", "uyum.ekibi", "Bilgi güvenliği yönetim sistemi gereksinimleri."),
            ("KVKK", "KVKK", "hukuk.ekibi", "Kişisel verilerin korunması gereksinimleri."),
            ("NIST-CSF", "NIST Cybersecurity Framework", "risk.ekibi", "Siber güvenlik temel fonksiyonları ve kontrolleri."),
            ("PCI-DSS", "PCI DSS", "uyum.ekibi", "Kart verisi güvenliği gereksinimleri."),
            ("ISO22301", "ISO 22301", "süreklilik.ekibi", "İş sürekliliği yönetim sistemi gereksinimleri."),
            ("ISO27019", "ISO/IEC 27019", "enerji.ekibi", "Enerji endüstrisi için bilgi güvenliği kontrolleri."),
            ("EPDK", "EPDK Düzenlemeleri", "uyum.ekibi", "Enerji sektöründe düzenleyici uyum gereksinimleri."),
        ]
        frameworks = {}
        for code, name, owner, desc in framework_specs:
            framework, _ = ComplianceFramework.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "owner": owner,
                    "status": ComplianceFramework.STATUS_ACTIVE,
                    "description": desc,
                },
            )
            frameworks[code] = framework

        requirement_specs = [
            ("ISO27001", "A.5.1", "Bilgi güvenliği politikaları", controls[0], ComplianceRequirement.STATUS_COMPLIANT),
            ("ISO27001", "A.8.9", "Varlık envanteri yönetimi", None, ComplianceRequirement.STATUS_PARTIAL),
            ("ISO27001", "A.12.3", "Yedekleme ve kurtarma", controls[1], ComplianceRequirement.STATUS_COMPLIANT),
            ("KVKK", "KVKK-12", "Teknik ve idari tedbirler", controls[4], ComplianceRequirement.STATUS_PARTIAL),
            ("KVKK", "KVKK-6", "Özel nitelikli veri güvenliği", None, ComplianceRequirement.STATUS_NONCOMPLIANT),
            ("NIST-CSF", "ID.AM-1", "Varlık envanteri oluşturma", controls[0], ComplianceRequirement.STATUS_COMPLIANT),
            ("NIST-CSF", "PR.MA-1", "Bakım planı ve kayıtları", controls[1], ComplianceRequirement.STATUS_PARTIAL),
            ("NIST-CSF", "DE.CM-7", "Kötü amaçlı faaliyet izleme", controls[4], ComplianceRequirement.STATUS_UNKNOWN),
            ("PCI-DSS", "Req-9", "Fiziksel erişim kontrolü", controls[2], ComplianceRequirement.STATUS_PARTIAL),
            ("PCI-DSS", "Req-10", "İzleme ve loglama", controls[3], ComplianceRequirement.STATUS_COMPLIANT),
            ("ISO22301", "8.4.3", "Süreklilik stratejileri ve planları", None, ComplianceRequirement.STATUS_PARTIAL),
            ("ISO22301", "8.5.4", "Süreklilik test ve tatbikatları", controls[0], ComplianceRequirement.STATUS_COMPLIANT),
            ("ISO27019", "A.9.1", "Enerji OT erişim kontrolleri", None, ComplianceRequirement.STATUS_PARTIAL),
            ("ISO27019", "A.12.1", "Operasyonel prosedürler ve bakım", controls[1], ComplianceRequirement.STATUS_COMPLIANT),
            ("EPDK", "EDK-02", "Enerji kesintisi bildirim süreçleri", None, ComplianceRequirement.STATUS_PARTIAL),
            ("EPDK", "EDK-07", "Bakım kayıtları ve raporlama", controls[1], ComplianceRequirement.STATUS_COMPLIANT),
        ]

        for framework_code, code, title, control, status in requirement_specs:
            framework = frameworks.get(framework_code)
            if not framework:
                continue
            ComplianceRequirement.objects.get_or_create(
                framework=framework,
                code=code,
                defaults={
                    "title": title,
                    "description": f"{framework.name} gereksinimi: {title}",
                    "status": status,
                    "control": control,
                    "evidence": "Örnek kanıt: politika dokümanı, test raporu veya kayıt.",
                    "last_reviewed": today - timedelta(days=30),
                },
            )

        # Seed continuity strategies
        strategies = [
            ("CONT-RED-001", "Veri Merkezi Aktif/Aktif", ContinuityStrategy.TYPE_REDUNDANCY, ContinuityStrategy.READINESS_READY),
            ("CONT-BCK-002", "Kritik Sistem Haftalık Yedek", ContinuityStrategy.TYPE_BACKUP, ContinuityStrategy.READINESS_IN_PROGRESS),
            ("CONT-MAN-003", "Manuel Süreç Devamı", ContinuityStrategy.TYPE_MANUAL, ContinuityStrategy.READINESS_PLANNED),
            ("CONT-VEN-004", "Alternatif Tedarikçi Devreye Alma", ContinuityStrategy.TYPE_VENDOR, ContinuityStrategy.READINESS_READY),
            ("CONT-WRK-005", "Geçici Operasyonel İş Akışı", ContinuityStrategy.TYPE_WORKAROUND, ContinuityStrategy.READINESS_TESTED),
        ]

        services = list(CriticalService.objects.order_by("code"))
        profiles = {p.service_id: p for p in ServiceBIAProfile.objects.select_related("service")}
        scenarios = list(Scenario.objects.order_by("-created_at"))

        for idx, (code, name, strategy_type, readiness) in enumerate(strategies, start=1):
            service = services[idx % len(services)] if services else None
            if not service:
                break
            ContinuityStrategy.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "strategy_type": strategy_type,
                    "status": ContinuityStrategy.STATUS_ACTIVE,
                    "readiness_level": readiness,
                    "service": service,
                    "bia_profile": profiles.get(service.id),
                    "scenario": scenarios[idx % len(scenarios)] if scenarios else None,
                    "rto_target_hours": max(getattr(profiles.get(service.id), "rto_hours", 8), 2),
                    "rpo_target_hours": max(getattr(profiles.get(service.id), "rpo_hours", 4), 1),
                    "owner": "süreklilik.ekibi",
                    "notes": "Örnek süreklilik stratejisi kaydı.",
                },
            )

        # Seed assessments
        Assessment.objects.get_or_create(
            title="Yıllık Risk Değerlendirmesi",
            defaults={
                "assessment_type": Assessment.TYPE_INTERNAL,
                "status": Assessment.STATUS_IN_PROGRESS,
                "owner": "risk.ekibi",
                "start_date": today - timedelta(days=10),
                "end_date": today + timedelta(days=20),
                "scope": "Elektrik, doğalgaz ve su altyapısı ile veri merkezi.",
                "notes": "Saha görüşmeleri ve belge incelemesi devam ediyor.",
            },
        )

        # Seed vulnerabilities, issues, and exceptions per risk (limited volume, varied content)
        vulnerability_specs = [
            ("Korozyon/Rutin Bulgu", "Rutin saha kontrolünde bakım ihtiyacı tespit edildi.", "bakim.ekibi", 30, "Yedek parça tedarik ediliyor."),
            ("Etiketleme Eksikliği", "Varlık etiketleme standardına uygunluk bulunmadı.", "operasyon.ekibi", 14, "Etiket seti hazırlanıyor."),
            ("Yedek Parça Kritik", "Kritik yedek parça stok seviyesi eşik altında.", "satinalma.ekibi", 21, "Tedarikçi siparişi açıldı."),
            ("İzleme Eksikliği", "İzleme alarmı tetiklenmiyor, eşik kontrol ediliyor.", "it.ekibi", 10, "Alarm eşikleri revize edilecek."),
            ("Sızdırmazlık Riski", "Sızdırmazlık testinde limit dışı ölçüm.", "bakim.ekibi", 20, "Conta seti değişimi planlandı."),
        ]

        issue_specs = [
            ("Operasyonel Uygunsuzluk", "Saha gözleminde düzeltme gerektiren uygunsuzluk bulundu.", "operasyon.ekibi", 21),
            ("Bakım Planı Gecikmesi", "Periyodik bakım planı hedef tarihte tamamlanmadı.", "bakim.ekibi", 30),
            ("Dokümantasyon Eksikliği", "Varlık dokümantasyonunda eksik alanlar var.", "it.ekibi", 14),
            ("Erişim Yetkisi Uyumsuzluğu", "Yetki matrisi ile kullanıcı erişimleri uyuşmuyor.", "guvenlik.ekibi", 21),
            ("Saha Envanter Tutarsızlığı", "Varlık kaydı ile saha envanteri uyuşmuyor.", "envanter.ekibi", 15),
        ]

        exception_specs = [
            ("Geçici Bakım Erteleme", "Planlı bakım takvimi nedeniyle geçici erteleme.", "bakim.ekibi", "risk.onay", 30),
            ("Bütçe Revizyonu Bekleniyor", "Yatırım planı onayı bekleniyor, geçici risk kabulü.", "finans.ekibi", "risk.onay", 60),
            ("Tedarikçi Bekleme Süresi", "Parça teslim süresi uzadı, geçici istisna.", "satinalma.ekibi", "risk.onay", 45),
            ("Operasyonel Zorunluluk", "Kısa vadeli operasyonel gereklilik nedeniyle istisna.", "operasyon.ekibi", "risk.onay", 20),
            ("Gözden Geçirme Talebi", "Risk gözden geçirme sonrası şartlı istisna.", "risk.ekibi", "risk.onay", 25),
        ]

        for idx, risk in enumerate(Risk.objects.select_related("primary_asset").order_by("id")[:80], start=1):
            asset = risk.primary_asset
            vuln_title, vuln_desc, vuln_owner, vuln_due_days, vuln_notes = vulnerability_specs[idx % len(vulnerability_specs)]
            issue_title, issue_desc, issue_owner, issue_due_days = issue_specs[idx % len(issue_specs)]
            exc_title, exc_just, exc_owner, exc_approver, exc_days = exception_specs[idx % len(exception_specs)]

            if asset:
                Vulnerability.objects.get_or_create(
                    title=f"{asset.asset_code} - {vuln_title}",
                    defaults={
                        "description": vuln_desc,
                        "severity": Vulnerability.SEVERITY_MEDIUM if idx % 3 else Vulnerability.SEVERITY_HIGH,
                        "status": Vulnerability.STATUS_OPEN,
                        "owner": vuln_owner,
                        "asset": asset,
                        "risk": risk,
                        "discovered_at": today - timedelta(days=7 + (idx % 5)),
                        "due_date": today + timedelta(days=vuln_due_days),
                        "notes": vuln_notes,
                    },
                )

            RiskIssue.objects.get_or_create(
                risk=risk,
                title=issue_title,
                defaults={
                    "description": issue_desc,
                    "status": RiskIssue.STATUS_IN_PROGRESS if idx % 2 else RiskIssue.STATUS_OPEN,
                    "owner": issue_owner,
                    "due_date": today + timedelta(days=issue_due_days),
                },
            )

            RiskException.objects.get_or_create(
                risk=risk,
                title=exc_title,
                defaults={
                    "justification": exc_just,
                    "status": RiskException.STATUS_APPROVED if idx % 3 else RiskException.STATUS_OPEN,
                    "owner": exc_owner,
                    "approved_by": exc_approver,
                    "start_date": today - timedelta(days=2 + (idx % 4)),
                    "end_date": today + timedelta(days=exc_days),
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded OSB assets and realistic risks from inventory."))
