from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "webui"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("work-queue/", views.work_queue, name="work-queue"),
    path("audit-log/", views.audit_log, name="audit-log"),
    path("audit-log/export/", views.audit_log_export, name="audit-log-export"),
    path("assets/", views.asset_list, name="asset-list"),
    path("risks/", views.risk_list, name="risk-list"),
    path("risks/export/", views.risk_export_csv, name="risk-export"),
    path("risks/controls/", views.risk_controls, name="risk-controls"),
    path("risks/control-tests/", views.control_tests, name="control-tests"),
    path("risks/control-tests/runs/", views.control_test_runs, name="control-test-runs"),
    path("risks/heatmap/", views.risk_heatmap, name="risk-heatmap"),
    path("risks/issues/", views.risk_issues, name="risk-issues"),
    path("risks/exceptions/", views.risk_exceptions, name="risk-exceptions"),
    path("risks/reports/", views.risk_reports, name="risk-reports"),
    path("assessments/", views.assessments, name="assessments"),
    path("vulnerabilities/", views.vulnerabilities, name="vulnerabilities"),
    path("governance/programs/", views.governance_programs, name="governance-programs"),
    path("compliance/frameworks/", views.compliance_frameworks, name="compliance-frameworks"),
    path("compliance/requirements/", views.compliance_requirements, name="compliance-requirements"),
    path("reports/", views.reports_overview, name="reports-overview"),
    path("reports/assessments/", views.assessment_reports, name="assessment-reports"),
    path("reports/vulnerabilities/", views.vulnerability_reports, name="vulnerability-reports"),
    path("reports/compliance/", views.compliance_reports, name="compliance-reports"),
    path("reports/export/<str:report_key>/", views.export_report_csv, name="reports-export"),
    path("notifications/", views.risk_notifications, name="risk-notifications"),
    path("scoring-methods/", views.scoring_method_list, name="scoring-method-list"),
    path("risks/<int:risk_id>/", views.risk_detail, name="risk-detail"),
    path("risks/<int:risk_id>/status/", views.risk_status_update, name="risk-status-update"),
    path("treatments/<int:treatment_id>/progress/", views.treatment_progress_update, name="treatment-progress-update"),
    path("locations/risks/", views.location_risk_overview, name="location-risks"),
    path("locations/tree/", views.location_tree, name="location-tree"),
    path("integration/sync/", views.integration_sync, name="integration-sync"),
    path("third-party/vendors/", views.third_party_vendors, name="third-party-vendors"),
    path("third-party/risks/", views.third_party_risks, name="third-party-risks"),
    path("policies/", views.policy_standards, name="policy-standards"),
    path("policies/mappings/", views.policy_mappings, name="policy-mappings"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="webui:login"), name="logout"),
]
