from django.contrib.auth import get_user_model
from django.test import TestCase

from asset.models import Asset, AssetType, BusinessUnit, CostCenter, Section

from .models import Risk, RiskReview, RiskScoringMethod, RiskTreatment
from .serializers import RiskSerializer


class RiskSerializerTests(TestCase):
    def setUp(self) -> None:
        self.business_unit = BusinessUnit.objects.create(code="001.001", name="Campus")
        self.cost_center = CostCenter.objects.create(code="001.001.001", name="Admin", business_unit=self.business_unit)
        self.section = Section.objects.create(code="001.001.001.003", name="Floor 1", cost_center=self.cost_center)
        self.asset_type = AssetType.objects.create(code="LOK", name="Location")

        self.asset_primary = Asset.objects.create(
            asset_code="LOK.ODA.001",
            asset_name="Room 101",
            business_unit=self.business_unit,
            cost_center=self.cost_center,
            section=self.section,
            asset_type=self.asset_type,
        )
        self.asset_secondary = Asset.objects.create(asset_code="E.CLIMA.001", asset_name="AC Unit")

        self.scoring_method = RiskScoringMethod.objects.create(
            code="TEST_WEIGHTED",
            name="Test Weighted",
            method_type=RiskScoringMethod.METHOD_CUSTOM,
            likelihood_weight=1.2,
            impact_weight=1.1,
            treatment_effectiveness_weight=1.0,
            is_default=True,
            is_active=True,
        )

        RiskScoringMethod.objects.exclude(id=self.scoring_method.id).update(is_default=False)

    def test_create_requires_primary_asset(self) -> None:
        serializer = RiskSerializer(data={"title": "No asset risk", "description": "Should fail"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("primary_asset", serializer.errors)

    def test_create_links_primary_and_additional_assets(self) -> None:
        serializer = RiskSerializer(
            data={
                "title": "Cooling outage risk",
                "description": "Impact on room operations",
                "primary_asset": self.asset_primary.id,
                "asset_ids": [self.asset_secondary.id],
                "scoring_method": self.scoring_method.id,
                "likelihood": 4,
                "impact": 5,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        risk = serializer.save()

        linked_ids = sorted(list(risk.risk_assets.values_list("asset_id", flat=True)))
        self.assertEqual(linked_ids, sorted([self.asset_primary.id, self.asset_secondary.id]))

        self.assertEqual(risk.business_unit_id, self.business_unit.id)
        self.assertEqual(risk.cost_center_id, self.cost_center.id)
        self.assertEqual(risk.section_id, self.section.id)
        self.assertEqual(risk.asset_type_id, self.asset_type.id)

        self.assertGreater(float(risk.inherent_score), 0.0)
        self.assertGreaterEqual(float(risk.residual_score), 0.0)
        self.assertEqual(risk.scoring_history.count(), 1)

    def test_treatment_progress_reduces_residual_score(self) -> None:
        serializer = RiskSerializer(
            data={
                "title": "Treatment score check",
                "primary_asset": self.asset_primary.id,
                "scoring_method": self.scoring_method.id,
                "likelihood": 5,
                "impact": 5,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        risk = serializer.save()

        initial_residual = float(risk.residual_score)

        RiskTreatment.objects.create(
            risk=risk,
            title="Initial mitigation",
            strategy=RiskTreatment.STRATEGY_MITIGATE,
            status=RiskTreatment.STATUS_IN_PROGRESS,
            progress_percent=60,
        )

        risk.refresh_scores(actor="test")
        risk.refresh_from_db()

        self.assertLess(float(risk.residual_score), initial_residual)

    def test_review_can_be_recorded(self) -> None:
        user = get_user_model().objects.create_user(username="reviewer", password="pass1234")
        serializer = RiskSerializer(
            data={
                "title": "Review flow",
                "primary_asset": self.asset_primary.id,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        risk = serializer.save()

        review = RiskReview.objects.create(
            risk=risk,
            reviewer=user,
            decision=RiskReview.DECISION_REVISIT,
            comments="Need another review cycle",
        )

        self.assertEqual(risk.reviews.count(), 1)
        self.assertEqual(review.reviewer.username, "reviewer")


    def test_create_in_progress_requires_owner(self) -> None:
        serializer = RiskSerializer(
            data={
                "title": "Owner required check",
                "primary_asset": self.asset_primary.id,
                "status": Risk.STATUS_IN_PROGRESS,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("owner", serializer.errors)

    def test_create_rejects_past_due_date_for_non_closed_risk(self) -> None:
        from django.utils import timezone
        from datetime import timedelta

        serializer = RiskSerializer(
            data={
                "title": "Past due check",
                "primary_asset": self.asset_primary.id,
                "status": Risk.STATUS_OPEN,
                "due_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("due_date", serializer.errors)

    def test_create_requires_asset_context_metadata(self) -> None:
        serializer = RiskSerializer(
            data={
                "title": "Missing context metadata",
                "primary_asset": self.asset_secondary.id,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("primary_asset", serializer.errors)

    def test_create_auto_assigns_default_scoring_method(self) -> None:
        serializer = RiskSerializer(
            data={
                "title": "Default scoring assignment",
                "primary_asset": self.asset_primary.id,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        risk = serializer.save()
        self.assertEqual(risk.scoring_method_id, self.scoring_method.id)
