from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from asset.models import Asset
from asset.models import AssetDependency
from risk.models import CriticalService, ServiceAssetMapping, ServiceBIAProfile
from risk.services.resilience import evaluate_incident_services, evaluate_service_impact


class ResilienceEvaluationTests(TestCase):
    def setUp(self):
        self.service = CriticalService.objects.create(code="SERV-TEST", name="Test Service")
        self.profile = ServiceBIAProfile.objects.create(
            service=self.service,
            mao_hours=2,
            rto_hours=1,
            rpo_hours=1,
            service_criticality=ServiceBIAProfile.CRITICALITY_BUSINESS,
            impact_operational=4,
            impact_financial=3,
            impact_environmental=2,
            impact_safety=2,
            impact_legal=2,
            impact_reputation=3,
        )

    def test_validate_escalation_curve_increasing(self):
        curve = [
            {"time_minutes": 60, "level": "MINOR"},
            {"time_minutes": 30, "level": "DEGRADED"},
        ]
        with self.assertRaises(ValidationError):
            ServiceBIAProfile.validate_impact_escalation_curve(curve, mtpd_minutes=120)

    def test_missing_curve_derived_default(self):
        result = evaluate_service_impact(self.profile, outage_minutes=60)
        self.assertIn("MISSING_ESCALATION_CURVE_DERIVED_DEFAULT", result["warnings"])
        self.assertEqual(result["impact_level"], "DEGRADED")

    def test_missing_rules_defaults(self):
        result = evaluate_service_impact(self.profile, outage_minutes=30)
        self.assertIn("MISSING_CRISIS_RULES_DEFAULTS_APPLIED", result["warnings"])

    def test_threshold_boundaries(self):
        self.profile.impact_escalation_curve = [
            {"time_minutes": 30, "level": "MINOR"},
            {"time_minutes": 60, "level": "DEGRADED"},
            {"time_minutes": 90, "level": "SEVERE"},
            {"time_minutes": 120, "level": "CRITICAL"},
        ]
        self.profile.full_clean()
        self.profile.save()

        result_before = evaluate_service_impact(self.profile, outage_minutes=59)
        self.assertEqual(result_before["impact_level"], "MINOR")
        result_after = evaluate_service_impact(self.profile, outage_minutes=60)
        self.assertEqual(result_after["impact_level"], "DEGRADED")

    def test_outage_beyond_mtpd_triggers_crisis(self):
        result = evaluate_service_impact(self.profile, outage_minutes=200)
        self.assertEqual(result["impact_level"], "CATASTROPHIC")
        self.assertTrue(result["crisis_recommended"])

    def test_rto_breach_flagged(self):
        result = evaluate_service_impact(self.profile, outage_minutes=60)
        self.assertIn("RTO_BREACH", result["breaches"])

    def test_environmental_guardrail(self):
        self.profile.impact_environmental = 5
        self.profile.crisis_trigger_rules = {
            "mtpd_percentage_trigger": 0.9,
            "impact_level_trigger": "CRITICAL",
            "environmental_severity_trigger": 4,
        }
        self.profile.full_clean()
        self.profile.save()

        result = evaluate_service_impact(self.profile, outage_minutes=10)
        self.assertFalse(result["crisis_recommended"])

    def test_invalid_rules_rejected(self):
        with self.assertRaises(ValidationError):
            ServiceBIAProfile.validate_crisis_trigger_rules({"unsupported": 1})


class ResilienceMultiServiceTests(TestCase):
    def test_multi_service_evaluation(self):
        service_a = CriticalService.objects.create(code="SERV-A", name="Service A")
        service_b = CriticalService.objects.create(code="SERV-B", name="Service B")
        ServiceBIAProfile.objects.create(
            service=service_a,
            mao_hours=4,
            rto_hours=2,
            rpo_hours=1,
            service_criticality=ServiceBIAProfile.CRITICALITY_INFRASTRUCTURE,
            impact_operational=4,
            impact_financial=3,
            impact_environmental=2,
            impact_safety=2,
            impact_legal=2,
            impact_reputation=3,
        )
        ServiceBIAProfile.objects.create(
            service=service_b,
            mao_hours=4,
            rto_hours=2,
            rpo_hours=1,
            service_criticality=ServiceBIAProfile.CRITICALITY_SUPPORT,
            impact_operational=3,
            impact_financial=2,
            impact_environmental=1,
            impact_safety=1,
            impact_legal=1,
            impact_reputation=2,
        )

        asset_a = Asset.objects.create(asset_code="AST-A", asset_name="Asset A")
        asset_b = Asset.objects.create(asset_code="AST-B", asset_name="Asset B")
        AssetDependency.objects.create(source_asset=asset_a, target_asset=asset_b)

        ServiceAssetMapping.objects.create(service=service_a, asset=asset_a)
        ServiceAssetMapping.objects.create(service=service_b, asset=asset_b)

        start_time = timezone.now() - timedelta(hours=1)
        results = evaluate_incident_services(start_time, timezone.now(), [asset_a.id])
        service_ids = {item["service_id"] for item in results}
        self.assertEqual({service_a.id, service_b.id}, service_ids)
