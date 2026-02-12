from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from asset.models import Asset, AssetType, BusinessUnit, CostCenter, Section
from core.models import AuditEvent
from risk.models import Risk


class RiskApiPermissionTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(username="api_admin", password="pass1234")
        self.owner_user = user_model.objects.create_user(username="api_owner", password="pass1234")
        self.reviewer_user = user_model.objects.create_user(username="api_reviewer", password="pass1234")
        self.viewer_user = user_model.objects.create_user(username="api_viewer", password="pass1234")

        admin_group, _ = Group.objects.get_or_create(name="risk_admin")
        owner_group, _ = Group.objects.get_or_create(name="risk_owner")
        reviewer_group, _ = Group.objects.get_or_create(name="risk_reviewer")
        self.admin_user.groups.add(admin_group)
        self.owner_user.groups.add(owner_group)
        self.reviewer_user.groups.add(reviewer_group)

        bu = BusinessUnit.objects.create(code="001.001", name="Campus")
        cc = CostCenter.objects.create(code="001.001.001", name="Admin Building", business_unit=bu)
        sec = Section.objects.create(code="001.001.001.003", name="Floor 1", cost_center=cc)
        asset_type = AssetType.objects.create(code="LOK", name="Location")
        self.asset = Asset.objects.create(
            asset_code="LOK.ODA.001",
            asset_name="Room 101",
            business_unit=bu,
            cost_center=cc,
            section=sec,
            asset_type=asset_type,
        )
        self.risk = Risk.objects.create(title="Cooling outage risk", primary_asset=self.asset)

    def test_viewer_cannot_create_risk(self):
        self.client.force_authenticate(self.viewer_user)
        response = self.client.post(
            reverse("risk-list"),
            data={"title": "Unauthorized create", "primary_asset": self.asset.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_create_risk(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            reverse("risk-list"),
            data={"title": "Owner create", "primary_asset": self.asset.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AuditEvent.objects.filter(action="risk.create", entity_type="risk").exists())

    def test_reviewer_cannot_update_risk_status(self):
        self.client.force_authenticate(self.reviewer_user)
        response = self.client.patch(
            reverse("risk-detail", args=[self.risk.id]),
            data={"status": Risk.STATUS_IN_PROGRESS},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reviewer_can_create_review(self):
        self.client.force_authenticate(self.reviewer_user)
        response = self.client.post(
            reverse("risk-review-list"),
            data={"risk": self.risk.id, "decision": "revisit", "comments": "Need more controls."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_cannot_create_scoring_method(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            reverse("risk-scoring-method-list"),
            data={"code": "OWNER_X", "name": "Owner Method", "method_type": "custom"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_scoring_method(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            reverse("risk-scoring-method-list"),
            data={"code": "ADMIN_X", "name": "Admin Method", "method_type": "custom"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
