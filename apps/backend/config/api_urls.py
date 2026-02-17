from django.urls import include, path
from rest_framework.routers import DefaultRouter

from asset.views import AssetViewSet
from integration.views import EamSyncView, IntegrationPluginCatalogView
from risk.views import (
    AssessmentViewSet,
    ComplianceFrameworkViewSet,
    ComplianceRequirementViewSet,
    ControlTestPlanViewSet,
    ControlTestRunViewSet,
    GovernanceProgramViewSet,
    evaluate_incident,
    RiskApprovalViewSet,
    RiskControlViewSet,
    RiskNotificationViewSet,
    RiskIssueViewSet,
    RiskExceptionViewSet,
    RiskReportRunViewSet,
    RiskReportScheduleViewSet,
    RiskReviewViewSet,
    RiskScoringMethodViewSet,
    RiskScoringSnapshotViewSet,
    RiskTreatmentViewSet,
    RiskViewSet,
    VulnerabilityViewSet,
)

router = DefaultRouter()
router.register(r"assets", AssetViewSet, basename="asset")
router.register(r"risks", RiskViewSet, basename="risk")
router.register(r"risk-scoring-methods", RiskScoringMethodViewSet, basename="risk-scoring-method")
router.register(r"risk-scoring-snapshots", RiskScoringSnapshotViewSet, basename="risk-scoring-snapshot")
router.register(r"risk-controls", RiskControlViewSet, basename="risk-control")
router.register(r"risk-treatments", RiskTreatmentViewSet, basename="risk-treatment")
router.register(r"risk-reviews", RiskReviewViewSet, basename="risk-review")
router.register(r"risk-approvals", RiskApprovalViewSet, basename="risk-approval")
router.register(r"risk-notifications", RiskNotificationViewSet, basename="risk-notification")
router.register(r"risk-issues", RiskIssueViewSet, basename="risk-issue")
router.register(r"risk-exceptions", RiskExceptionViewSet, basename="risk-exception")
router.register(r"risk-report-schedules", RiskReportScheduleViewSet, basename="risk-report-schedule")
router.register(r"risk-report-runs", RiskReportRunViewSet, basename="risk-report-run")
router.register(r"assessments", AssessmentViewSet, basename="assessment")
router.register(r"vulnerabilities", VulnerabilityViewSet, basename="vulnerability")
router.register(r"governance-programs", GovernanceProgramViewSet, basename="governance-program")
router.register(r"compliance-frameworks", ComplianceFrameworkViewSet, basename="compliance-framework")
router.register(r"compliance-requirements", ComplianceRequirementViewSet, basename="compliance-requirement")
router.register(r"control-test-plans", ControlTestPlanViewSet, basename="control-test-plan")
router.register(r"control-test-runs", ControlTestRunViewSet, basename="control-test-run")

urlpatterns = [
    path("", include(router.urls)),
    path("integration/eam/plugins", IntegrationPluginCatalogView.as_view(), name="integration-eam-plugins"),
    path("integration/eam/sync", EamSyncView.as_view(), name="integration-eam-sync"),
    path("resilience/evaluate-incident/", evaluate_incident, name="resilience-evaluate-incident"),
]
