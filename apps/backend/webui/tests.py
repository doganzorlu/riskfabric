from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from asset.models import Asset, AssetDependency, AssetType, BusinessUnit, CostCenter, Section
from risk.models import RiskApproval, RiskNotification
from core.models import AuditEvent
from risk.models import Risk, RiskTreatment


class WebUiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="user1", password="pass1234")
        self.viewer = get_user_model().objects.create_user(username="viewer1", password="pass1234")
        admin_group, _ = Group.objects.get_or_create(name="risk_admin")
        self.user.groups.add(admin_group)

        bu = BusinessUnit.objects.create(code="001.001", name="Campus")
        cc = CostCenter.objects.create(code="001.001.001", name="Admin Building", business_unit=bu)
        section = Section.objects.create(code="001.001.001.003", name="Floor 1", cost_center=cc)
        asset_type = AssetType.objects.create(code="LOK", name="Location")
        asset = Asset.objects.create(
            asset_code="LOK.ODA.001",
            asset_name="Room 101",
            business_unit=bu,
            cost_center=cc,
            section=section,
            asset_type=asset_type,
        )
        Risk.objects.create(title="Cooling outage risk", primary_asset=asset)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("webui:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_location_risk_page_authenticated(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:location-risks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Location Risks")
        self.assertContains(response, "001.001")

    def test_location_tree_page_authenticated(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:location-tree"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Location and Asset Tree")
        self.assertContains(response, "LOK.ODA.001")

    def test_location_tree_filters_render(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:location-tree"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asset Type")
        self.assertContains(response, "Due Date From")

    def test_risk_heatmap_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-heatmap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Risk Heatmap")

    def test_controls_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-controls"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Controls Library")

    def test_notifications_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notifications")

    def test_issues_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-issues"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Issues")

    def test_exceptions_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-exceptions"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exceptions")

    def test_reports_page(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scheduled Reports")

    def test_mark_all_notifications_read(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        RiskNotification.objects.create(
            user=self.user,
            risk=risk,
            notification_type=RiskNotification.TYPE_APPROVAL_REQUESTED,
            message="Test notification",
        )
        response = self.client.post(reverse("webui:risk-notifications"), data={"mark_all_read": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RiskNotification.objects.filter(user=self.user, read_at__isnull=True).count(), 0)

    def test_risk_list_htmx_partial(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-list"), HTTP_HX_REQUEST="true", data={"q": "Cooling"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cooling outage risk")

    def test_location_risk_htmx_partial(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(
            reverse("webui:location-risks"),
            HTTP_HX_REQUEST="true",
            data={"business_unit_code": "001.001"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Risk Distribution by Section")

    def test_risk_detail_page_authenticated(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.get(reverse("webui:risk-detail", args=[risk.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Risk Detail")

    def test_risk_detail_add_treatment(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-detail", args=[risk.id]),
            data={
                "action": "add_treatment",
                "treatment-risk": risk.id,
                "treatment-title": "Backup power upgrade",
                "treatment-strategy": RiskTreatment.STRATEGY_MITIGATE,
                "treatment-status": RiskTreatment.STATUS_PLANNED,
                "treatment-owner": "alice",
                "treatment-due_date": "",
                "treatment-progress_percent": 0,
                "treatment-notes": "Initial plan",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RiskTreatment.objects.filter(risk=risk, title="Backup power upgrade").exists())

    def test_risk_detail_update_risk(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-detail", args=[risk.id]),
            data={
                "action": "update_risk",
                "edit-title": "Updated risk title",
                "edit-description": "Updated description",
                "edit-category": "Operations",
                "edit-source": "Manual",
                "edit-owner": "bob",
                "edit-due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.title, "Updated risk title")

    def test_risk_detail_link_assets(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        extra_asset = Asset.objects.create(asset_code="GEN.UPS.001", asset_name="UPS")
        response = self.client.post(
            reverse("webui:risk-detail", args=[risk.id]),
            data={
                "action": "link_assets",
                "link-asset_ids": [str(extra_asset.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(risk.risk_assets.filter(asset=extra_asset).exists())

    def test_risk_detail_dependency_graph(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        source = risk.primary_asset
        target = Asset.objects.create(asset_code="GEN.SW.001", asset_name="Switch")
        risk.risk_assets.create(asset=target, is_primary=False)
        AssetDependency.objects.create(source_asset=source, target_asset=target, dependency_type="hard", strength=4)

        response = self.client.get(reverse("webui:risk-detail", args=[risk.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asset Dependencies")
        self.assertContains(response, "Dependency Graph")
        self.assertContains(response, "GEN.SW.001")

    def test_risk_approval_workflow(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-detail", args=[risk.id]),
            data={
                "action": "request_approval",
                "approval_request-comments": "Need approval to proceed",
            },
        )
        self.assertEqual(response.status_code, 302)
        approval = RiskApproval.objects.filter(risk=risk).first()
        self.assertIsNotNone(approval)

    def test_risk_bulk_update(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-list"),
            data={
                "action": "bulk_update",
                "risk_ids": [str(risk.id)],
                "bulk-status": Risk.STATUS_IN_PROGRESS,
                "bulk-owner": "bulk-owner",
                "bulk-due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.status, Risk.STATUS_IN_PROGRESS)
        self.assertEqual(risk.owner, "bulk-owner")

    def test_risk_bulk_update_clear_fields(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        risk.owner = "owner-to-clear"
        risk.due_date = timezone.localdate()
        risk.save(update_fields=["owner", "due_date", "updated_at"])
        response = self.client.post(
            reverse("webui:risk-list"),
            data={
                "action": "bulk_update",
                "risk_ids": [str(risk.id)],
                "bulk-clear_owner": "on",
                "bulk-clear_due_date": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.owner, "")
        self.assertIsNone(risk.due_date)

    def test_risk_export_csv(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:risk-export"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertContains(response, "treatment_count")

    def test_risk_status_update_htmx(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-status-update", args=[risk.id]),
            data={"status": Risk.STATUS_IN_PROGRESS},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        risk.refresh_from_db()
        self.assertEqual(risk.status, Risk.STATUS_IN_PROGRESS)
        self.assertTrue(
            AuditEvent.objects.filter(action="risk.status.update", entity_type="risk", entity_id=str(risk.id)).exists()
        )

    def test_treatment_progress_update_htmx(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        treatment = RiskTreatment.objects.create(risk=risk, title="Patch firmware")
        response = self.client.post(
            reverse("webui:treatment-progress-update", args=[treatment.id]),
            data={"progress_percent": 45, "status": RiskTreatment.STATUS_IN_PROGRESS},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        treatment.refresh_from_db()
        self.assertEqual(treatment.progress_percent, 45)
        self.assertEqual(treatment.status, RiskTreatment.STATUS_IN_PROGRESS)

    def test_invalid_transition_blocked(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        risk.status = Risk.STATUS_CLOSED
        risk.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("webui:risk-status-update", args=[risk.id]),
            data={"status": Risk.STATUS_IN_PROGRESS},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)
        risk.refresh_from_db()
        self.assertEqual(risk.status, Risk.STATUS_CLOSED)

    def test_review_accept_closes_risk(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-list"),
            data={
                "action": "add_review",
                "review-risk": risk.id,
                "review-decision": "accept",
                "review-comments": "Approved for closure",
                "review-next_review_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        risk.refresh_from_db()
        self.assertEqual(risk.status, Risk.STATUS_CLOSED)

    def test_non_privileged_user_cannot_update_status(self):
        self.client.login(username="viewer1", password="pass1234")
        risk = Risk.objects.first()
        response = self.client.post(
            reverse("webui:risk-status-update", args=[risk.id]),
            data={"status": Risk.STATUS_IN_PROGRESS},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_privileged_user_cannot_update_treatment(self):
        self.client.login(username="viewer1", password="pass1234")
        risk = Risk.objects.first()
        treatment = RiskTreatment.objects.create(risk=risk, title="Patch firmware")
        response = self.client.post(
            reverse("webui:treatment-progress-update", args=[treatment.id]),
            data={"progress_percent": 45, "status": RiskTreatment.STATUS_IN_PROGRESS},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_privileged_user_cannot_access_sync(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.get(reverse("webui:integration-sync"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You do not have permission to run EAM sync.")

    def test_sync_link_hidden_for_non_privileged_user(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.get(reverse("webui:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/integration/sync/"')


    def test_scoring_link_hidden_for_non_privileged_user(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.get(reverse("webui:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/scoring-methods/"')

    def test_scoring_methods_page_admin_access(self):
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:scoring-method-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scoring Methods")

    def test_scoring_methods_create_denied_for_viewer(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.post(
            reverse("webui:scoring-method-list"),
            data={
                "method-code": "method_x",
                "method-name": "Method X",
                "method-method_type": "custom",
                "method-likelihood_weight": "1.0",
                "method-impact_weight": "1.0",
                "method-treatment_effectiveness_weight": "1.0",
                "method-is_default": "on",
                "method-is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You do not have permission to manage scoring methods.")


    def test_seed_roles_command(self):
        Group.objects.filter(name__in=["risk_admin", "risk_owner", "risk_reviewer"]).delete()
        call_command("seed_roles")
        self.assertTrue(Group.objects.filter(name="risk_admin").exists())
        self.assertTrue(Group.objects.filter(name="risk_owner").exists())
        self.assertTrue(Group.objects.filter(name="risk_reviewer").exists())

    def test_work_queue_page_authenticated(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        RiskTreatment.objects.create(
            risk=risk,
            title="Network segmentation",
            due_date=timezone.localdate() - timedelta(days=1),
            status=RiskTreatment.STATUS_IN_PROGRESS,
            progress_percent=30,
        )
        response = self.client.get(reverse("webui:work-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Work Queue")
        self.assertContains(response, "Network segmentation")

    def test_work_queue_htmx_filter(self):
        self.client.login(username="user1", password="pass1234")
        risk = Risk.objects.first()
        RiskTreatment.objects.create(
            risk=risk,
            title="Firewall hardening",
            owner="alice",
            due_date=timezone.localdate() - timedelta(days=2),
            status=RiskTreatment.STATUS_IN_PROGRESS,
            progress_percent=40,
        )
        response = self.client.get(
            reverse("webui:work-queue"),
            HTTP_HX_REQUEST="true",
            data={"owner": "ali", "treatment_status": RiskTreatment.STATUS_IN_PROGRESS, "review_window_days": 10},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Firewall hardening")

    def test_audit_log_page_admin_only(self):
        AuditEvent.objects.create(action="risk.create", entity_type="risk", entity_id="10")
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:audit-log"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Log")

    def test_audit_log_page_forbidden_for_viewer(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.get(reverse("webui:audit-log"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You do not have permission to view audit logs.")

    def test_audit_log_htmx_filter(self):
        AuditEvent.objects.create(action="risk.status.update", entity_type="risk", entity_id="1")
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(
            reverse("webui:audit-log"),
            HTTP_HX_REQUEST="true",
            data={"action": "risk.status.update"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "risk.status.update")

    def test_audit_log_export_csv_admin(self):
        AuditEvent.objects.create(action="risk.create", entity_type="risk", entity_id="11")
        self.client.login(username="user1", password="pass1234")
        response = self.client.get(reverse("webui:audit-log-export"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertContains(response, "risk.create")

    def test_audit_log_export_csv_forbidden_for_viewer(self):
        self.client.login(username="viewer1", password="pass1234")
        response = self.client.get(reverse("webui:audit-log-export"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You do not have permission to export audit logs.")
