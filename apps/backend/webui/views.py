from datetime import timedelta
from typing import Optional
import csv

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from asset.models import Asset, AssetDependency, AssetType, BusinessUnit, CostCenter, Section
from core.audit import create_audit_event
from core.models import AuditEvent
from integration.models import IntegrationSyncRun
from risk.models import (
    Risk,
    RiskApproval,
    RiskCategory,
    RiskControl,
    CriticalService,
    Hazard,
    HazardLink,
    Scenario,
    ServiceBIAProfile,
    RiskException,
    RiskIssue,
    RiskNotification,
    RiskReportRun,
    RiskReportSchedule,
    RiskReview,
    RiskScoringMethod,
    RiskScoringDread,
    RiskScoringOwasp,
    RiskScoringCvss,
    RiskTreatment,
    ThirdPartyVendor,
    ThirdPartyRisk,
    PolicyStandard,
    PolicyControlMapping,
    PolicyRiskMapping,
    ControlTestPlan,
    ControlTestRun,
    GovernanceProgram,
    Assessment,
    Vulnerability,
    ComplianceFramework,
    ComplianceRequirement,
    ContinuityStrategy,
)
from risk.services.resilience import simulate_scenario

from .forms import (
    EamSyncForm,
    RiskCreateForm,
    RiskAssetLinkForm,
    RiskApprovalDecisionForm,
    RiskApprovalRequestForm,
    RiskControlCreateForm,
    RiskExceptionCreateForm,
    RiskIssueCreateForm,
    RiskReportScheduleForm,
    RiskReviewCreateForm,
    RiskScoringApplyForm,
    RiskScoringInputsForm,
    RiskScoringMethodCreateForm,
    RiskBulkUpdateForm,
    RiskUpdateForm,
    RiskTreatmentCreateForm,
    ThirdPartyVendorForm,
    ThirdPartyRiskForm,
    PolicyStandardForm,
    PolicyControlMappingForm,
    PolicyRiskMappingForm,
    ControlTestPlanForm,
    ControlTestRunForm,
    GovernanceProgramForm,
    AssessmentForm,
    VulnerabilityForm,
    ComplianceFrameworkForm,
    ComplianceRequirementForm,
    CriticalServiceForm,
    ServiceBIAProfileForm,
    HazardForm,
    HazardLinkForm,
    ScenarioForm,
    ContinuityStrategyForm,
)

ROLE_RISK_ADMIN = "risk_admin"
ROLE_RISK_OWNER = "risk_owner"
ROLE_RISK_REVIEWER = "risk_reviewer"
ROLE_GOVERNANCE_MANAGER = "governance_manager"
ROLE_COMPLIANCE_AUDITOR = "compliance_auditor"


def _has_any_role(user, *role_names: str) -> bool:
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=role_names).exists()


def _can_manage_risks(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN, ROLE_RISK_OWNER)


def _can_review_risks(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN, ROLE_RISK_REVIEWER)


def _can_run_sync(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN)


def _can_manage_scoring(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN)


def _can_view_audit(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN)


def _can_manage_governance(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN, ROLE_GOVERNANCE_MANAGER)


def _can_view_compliance(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN, ROLE_COMPLIANCE_AUDITOR, ROLE_GOVERNANCE_MANAGER)


def _can_manage_compliance(user) -> bool:
    return _has_any_role(user, ROLE_RISK_ADMIN, ROLE_COMPLIANCE_AUDITOR)


def _can_view_all_assets(user) -> bool:
    return user.is_superuser or _has_any_role(user, ROLE_RISK_ADMIN)


def _accessible_assets(user):
    if not user.is_authenticated:
        return Asset.objects.none()
    if _can_view_all_assets(user):
        return Asset.objects.all()
    return (
        Asset.objects.filter(
            Q(access_users=user)
            | Q(access_teams__members=user)
            | (Q(access_users__isnull=True) & Q(access_teams__isnull=True))
        )
        .distinct()
    )


def _permission_context(user) -> dict:
    unread_notifications = 0
    if user.is_authenticated:
        unread_notifications = RiskNotification.objects.filter(user=user, read_at__isnull=True).count()
    return {
        "can_manage_risks": _can_manage_risks(user),
        "can_review_risks": _can_review_risks(user),
        "can_run_sync": _can_run_sync(user),
        "can_manage_scoring": _can_manage_scoring(user),
        "can_view_audit": _can_view_audit(user),
        "can_manage_governance": _can_manage_governance(user),
        "can_view_compliance": _can_view_compliance(user),
        "can_manage_compliance": _can_manage_compliance(user),
        "unread_notification_count": unread_notifications,
    }


@login_required
@require_POST
def category_create(request):
    if not _can_manage_risks(request.user):
        messages.error(request, _("You do not have permission to manage categories."))
        return redirect(request.POST.get("next") or "webui:dashboard")

    name = (request.POST.get("name") or "").strip()
    category_type = (request.POST.get("category_type") or "").strip()
    next_url = request.POST.get("next") or "webui:dashboard"

    valid_types = {choice[0] for choice in RiskCategory.TYPE_CHOICES}
    if not name or category_type not in valid_types:
        messages.error(request, _("Please provide a valid category name and type."))
        return redirect(next_url)

    category, created = RiskCategory.objects.get_or_create(
        category_type=category_type,
        name=name,
    )
    if created:
        messages.success(request, _("Category created: %(name)s") % {"name": category.name})
    else:
        messages.info(request, _("Category already exists: %(name)s") % {"name": category.name})
    return redirect(next_url)


def _filtered_audit_events(request):
    selected_action = request.GET.get("action", "").strip()
    selected_entity_type = request.GET.get("entity_type", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_user = request.GET.get("user", "").strip()
    query = request.GET.get("q", "").strip()

    events = AuditEvent.objects.select_related("user").order_by("-created_at")
    if selected_action:
        events = events.filter(action=selected_action)
    if selected_entity_type:
        events = events.filter(entity_type=selected_entity_type)
    if selected_status:
        events = events.filter(status=selected_status)
    if selected_user:
        events = events.filter(user__username__icontains=selected_user)
    if query:
        events = events.filter(
            Q(message__icontains=query)
            | Q(entity_id__icontains=query)
            | Q(path__icontains=query)
            | Q(action__icontains=query)
        )
    return events, selected_action, selected_entity_type, selected_status, selected_user, query


@login_required
def dashboard(request):
    today = timezone.localdate()
    upcoming_limit = today + timedelta(days=7)

    asset_scope = _accessible_assets(request.user)
    risk_scope = Risk.objects.all()
    if not _can_view_all_assets(request.user):
        risk_scope = risk_scope.filter(primary_asset__in=asset_scope)

    overdue_treatment_count = RiskTreatment.objects.filter(
        due_date__isnull=False,
        due_date__lt=today,
    ).exclude(status__in=[RiskTreatment.STATUS_COMPLETED, RiskTreatment.STATUS_CANCELLED])
    if not _can_view_all_assets(request.user):
        overdue_treatment_count = overdue_treatment_count.filter(risk__in=risk_scope)
    overdue_treatment_count = overdue_treatment_count.count()

    upcoming_review_count = (
        RiskReview.objects.select_related("risk")
        .filter(
            next_review_date__isnull=False,
            next_review_date__gte=today,
            next_review_date__lte=upcoming_limit,
            risk__status__in=[Risk.STATUS_OPEN, Risk.STATUS_IN_PROGRESS],
        )
    )
    if not _can_view_all_assets(request.user):
        upcoming_review_count = upcoming_review_count.filter(risk__in=risk_scope)
    upcoming_review_count = upcoming_review_count.count()

    status_rows = risk_scope.values("status").annotate(total=Count("id")).order_by("status")
    risk_status_lookup = dict(Risk.STATUS_CHOICES)
    status_labels = [_(risk_status_lookup.get(row["status"], row["status"])) for row in status_rows]
    status_values = [row["total"] for row in status_rows]

    business_unit_rows = (
        risk_scope.exclude(business_unit__isnull=True)
        .values("business_unit__code")
        .annotate(total=Count("id"))
        .order_by("-total", "business_unit__code")[:10]
    )
    business_unit_labels = [row["business_unit__code"] for row in business_unit_rows]
    business_unit_values = [row["total"] for row in business_unit_rows]

    pending_approval_count = RiskApproval.objects.filter(status=RiskApproval.STATUS_PENDING)
    if not _can_view_all_assets(request.user):
        pending_approval_count = pending_approval_count.filter(risk__in=risk_scope)
    pending_approval_count = pending_approval_count.count()

    open_issue_count = RiskIssue.objects.filter(
        status__in=[RiskIssue.STATUS_OPEN, RiskIssue.STATUS_IN_PROGRESS]
    )
    if not _can_view_all_assets(request.user):
        open_issue_count = open_issue_count.filter(risk__in=risk_scope)
    open_issue_count = open_issue_count.count()

    open_exception_count = RiskException.objects.filter(status=RiskException.STATUS_OPEN)
    if not _can_view_all_assets(request.user):
        open_exception_count = open_exception_count.filter(risk__in=risk_scope)
    open_exception_count = open_exception_count.count()

    vulnerability_scope = Vulnerability.objects.all()
    if not _can_view_all_assets(request.user):
        vulnerability_scope = vulnerability_scope.filter(Q(asset__in=asset_scope) | Q(risk__primary_asset__in=asset_scope))
    vulnerability_status_rows = (
        vulnerability_scope.values("status").annotate(total=Count("id")).order_by("status")
    )
    vulnerability_status_lookup = dict(Vulnerability.STATUS_CHOICES)
    vulnerability_status_labels = [
        _(vulnerability_status_lookup.get(row["status"], row["status"])) for row in vulnerability_status_rows
    ]
    vulnerability_status_values = [row["total"] for row in vulnerability_status_rows]

    vulnerability_severity_rows = (
        vulnerability_scope.values("severity").annotate(total=Count("id")).order_by("severity")
    )
    vulnerability_severity_lookup = dict(Vulnerability.SEVERITY_CHOICES)
    vulnerability_severity_labels = [
        _(vulnerability_severity_lookup.get(row["severity"], row["severity"])) for row in vulnerability_severity_rows
    ]
    vulnerability_severity_values = [row["total"] for row in vulnerability_severity_rows]

    compliance_status_rows = (
        ComplianceRequirement.objects.values("status").annotate(total=Count("id")).order_by("status")
    )
    compliance_status_lookup = dict(ComplianceRequirement.STATUS_CHOICES)
    compliance_status_labels = [
        _(compliance_status_lookup.get(row["status"], row["status"])) for row in compliance_status_rows
    ]
    compliance_status_values = [row["total"] for row in compliance_status_rows]

    context = {
        "asset_count": asset_scope.count(),
        "risk_count": risk_scope.count(),
        "open_risk_count": risk_scope.filter(status=Risk.STATUS_OPEN).count(),
        "treatment_count": RiskTreatment.objects.filter(risk__in=risk_scope).count(),
        "overdue_treatment_count": overdue_treatment_count,
        "upcoming_review_count": upcoming_review_count,
        "scoring_method_count": RiskScoringMethod.objects.filter(is_active=True).count(),
        "control_count": RiskControl.objects.count(),
        "pending_approval_count": pending_approval_count,
        "open_issue_count": open_issue_count,
        "open_exception_count": open_exception_count,
        "assessment_count": Assessment.objects.count(),
        "vulnerability_count": vulnerability_scope.count(),
        "governance_program_count": GovernanceProgram.objects.count(),
        "compliance_framework_count": ComplianceFramework.objects.count(),
        "compliance_requirement_count": ComplianceRequirement.objects.count(),
        "report_schedule_count": RiskReportSchedule.objects.count(),
        "last_report_run": RiskReportRun.objects.select_related("schedule").order_by("-created_at").first(),
        "last_sync": IntegrationSyncRun.objects.order_by("-created_at").first(),
        "status_labels": status_labels,
        "status_values": status_values,
        "business_unit_labels": business_unit_labels,
        "business_unit_values": business_unit_values,
        "vulnerability_status_labels": vulnerability_status_labels,
        "vulnerability_status_values": vulnerability_status_values,
        "vulnerability_severity_labels": vulnerability_severity_labels,
        "vulnerability_severity_values": vulnerability_severity_values,
        "compliance_status_labels": compliance_status_labels,
        "compliance_status_values": compliance_status_values,
        **_permission_context(request.user),
    }
    return render(request, "webui/dashboard.html", context)


@login_required
def work_queue(request):
    today = timezone.localdate()
    selected_owner = request.GET.get("owner", "").strip()
    selected_treatment_status = request.GET.get("treatment_status", "").strip()
    selected_reviewer = request.GET.get("reviewer", "").strip()

    try:
        review_window_days = int(request.GET.get("review_window_days", "7"))
    except (TypeError, ValueError):
        review_window_days = 7
    review_window_days = min(max(review_window_days, 1), 30)

    upcoming_limit = today + timedelta(days=review_window_days)

    overdue_treatments = (
        RiskTreatment.objects.select_related("risk")
        .filter(due_date__isnull=False, due_date__lt=today)
        .exclude(status__in=[RiskTreatment.STATUS_COMPLETED, RiskTreatment.STATUS_CANCELLED])
        .order_by("due_date", "-created_at")
    )
    if selected_owner:
        overdue_treatments = overdue_treatments.filter(owner__icontains=selected_owner)
    if selected_treatment_status:
        overdue_treatments = overdue_treatments.filter(status=selected_treatment_status)

    upcoming_reviews = (
        RiskReview.objects.select_related("risk", "reviewer")
        .filter(
            next_review_date__isnull=False,
            next_review_date__gte=today,
            next_review_date__lte=upcoming_limit,
            risk__status__in=[Risk.STATUS_OPEN, Risk.STATUS_IN_PROGRESS],
        )
        .order_by("next_review_date", "-reviewed_at")
    )
    if selected_reviewer:
        upcoming_reviews = upcoming_reviews.filter(reviewer__username__icontains=selected_reviewer)

    context = {
        "overdue_treatments": overdue_treatments,
        "upcoming_reviews": upcoming_reviews,
        "today": today,
        "upcoming_limit": upcoming_limit,
        "review_window_days": review_window_days,
        "selected_owner": selected_owner,
        "selected_treatment_status": selected_treatment_status,
        "selected_reviewer": selected_reviewer,
        "treatment_status_choices": RiskTreatment.STATUS_CHOICES,
        **_permission_context(request.user),
    }
    if request.headers.get("HX-Request"):
        return render(request, "webui/partials/work_queue_content.html", context)

    return render(request, "webui/work_queue.html", context)


@login_required
def audit_log(request):
    if not _can_view_audit(request.user):
        messages.error(request, _("You do not have permission to view audit logs."))
        return redirect("webui:dashboard")

    events, selected_action, selected_entity_type, selected_status, selected_user, query = _filtered_audit_events(request)

    action_choices = list(AuditEvent.objects.values_list("action", flat=True).distinct().order_by("action"))
    entity_type_choices = list(AuditEvent.objects.values_list("entity_type", flat=True).distinct().order_by("entity_type"))

    context = {
        "events": events[:200],
        "action_choices": action_choices,
        "entity_type_choices": entity_type_choices,
        "status_choices": AuditEvent.STATUS_CHOICES,
        "selected_action": selected_action,
        "selected_entity_type": selected_entity_type,
        "selected_status": selected_status,
        "selected_user": selected_user,
        "query": query,
        **_permission_context(request.user),
    }
    if request.headers.get("HX-Request"):
        return render(request, "webui/partials/audit_log_content.html", context)
    return render(request, "webui/audit_log.html", context)


@login_required
def audit_log_export(request):
    if not _can_view_audit(request.user):
        messages.error(request, _("You do not have permission to export audit logs."))
        return redirect("webui:dashboard")

    events = _filtered_audit_events(request)[0]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_log.csv"'

    writer = csv.writer(response)
    writer.writerow(["created_at", "user", "action", "entity_type", "entity_id", "status", "message", "path", "method"])
    for e in events[:5000]:
        writer.writerow(
            [
                e.created_at.isoformat(),
                e.user.username if e.user else "",
                e.action,
                e.entity_type,
                e.entity_id,
                e.status,
                e.message,
                e.path,
                e.method,
            ]
        )
    return response


@login_required
def asset_list(request):
    query = request.GET.get("q", "").strip()
    assets = _accessible_assets(request.user).select_related(
        "parent_asset",
        "asset_type",
        "asset_status",
        "business_unit",
        "cost_center",
        "section",
        "asset_group",
    ).order_by("asset_code")
    if query:
        assets = assets.filter(
            Q(asset_code__icontains=query)
            | Q(asset_name__icontains=query)
            | Q(business_unit__code__icontains=query)
            | Q(cost_center__code__icontains=query)
            | Q(section__code__icontains=query)
            | Q(asset_type__code__icontains=query)
            | Q(asset_status__code__icontains=query)
            | Q(asset_group__code__icontains=query)
        )
    paginator = Paginator(assets, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "webui/assets.html",
        {
            "assets": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_list(request):
    risks = (
        Risk.objects.select_related(
            "primary_asset",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method",
        )
        .prefetch_related("risk_assets__asset", "treatments", "reviews")
        .order_by("-created_at")
    )

    if not _can_view_all_assets(request.user):
        risks = risks.filter(primary_asset__in=_accessible_assets(request.user))

    selected_status = request.GET.get("status", "").strip()
    selected_business_unit_code = request.GET.get("business_unit_code", "").strip()
    query = request.GET.get("q", "").strip()

    if selected_status:
        risks = risks.filter(status=selected_status)
    if selected_business_unit_code:
        risks = risks.filter(business_unit__code=selected_business_unit_code)
    if query:
        risks = risks.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(primary_asset__asset_code__icontains=query)
            | Q(primary_asset__asset_name__icontains=query)
        )

    show_form = request.GET.get("new") == "1"
    page_number = request.GET.get("page", "1")
    paginator = Paginator(risks, 20)
    page_obj = paginator.get_page(page_number)
    risks = page_obj.object_list
    risk_form = RiskCreateForm(prefix="risk", data=request.POST or None, user=request.user)
    scoring_form = RiskScoringApplyForm(prefix="scoring", data=request.POST or None)
    treatment_form = RiskTreatmentCreateForm(prefix="treatment", data=request.POST or None)
    review_form = RiskReviewCreateForm(prefix="review", data=request.POST or None, user=request.user)
    bulk_form = RiskBulkUpdateForm(prefix="bulk", data=request.POST or None)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_risk":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.create",
                    entity_type="risk",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for risk creation.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to create or edit risks."))
                return redirect("webui:risk-list")
            if risk_form.is_valid():
                risk = risk_form.save()
                create_audit_event(action="risk.create", entity_type="risk", entity_id=risk.id, request=request)
                messages.success(request, _("Risk created: %(title)s") % {"title": risk.title})
                return redirect("webui:risk-list")
            messages.error(request, _("Please fix risk form errors."))
            show_form = True

        elif action == "apply_scoring":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.scoring.apply",
                    entity_type="risk",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for scoring apply.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to apply scoring."))
                return redirect("webui:risk-list")
            if scoring_form.is_valid():
                risk = scoring_form.execute()
                create_audit_event(action="risk.scoring.apply", entity_type="risk", entity_id=risk.id, request=request)
                messages.success(request, _("Scoring method applied for risk #%(risk_id)s.") % {"risk_id": risk.id})
                return redirect("webui:risk-list")
            messages.error(request, _("Please fix scoring form errors."))

        elif action == "add_treatment":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="treatment.create",
                    entity_type="risk_treatment",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for treatment creation.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to manage treatments."))
                return redirect("webui:risk-list")
            if treatment_form.is_valid():
                treatment = treatment_form.save()
                create_audit_event(
                    action="treatment.create",
                    entity_type="risk_treatment",
                    entity_id=treatment.id,
                    metadata={"risk_id": treatment.risk_id},
                    request=request,
                )
                messages.success(request, _("Treatment added: %(title)s") % {"title": treatment.title})
                return redirect("webui:risk-list")
            messages.error(request, _("Please fix treatment form errors."))

        elif action == "add_review":
            if not _can_review_risks(request.user):
                create_audit_event(
                    action="review.create",
                    entity_type="risk_review",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for review creation.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to add reviews."))
                return redirect("webui:risk-list")
            if review_form.is_valid():
                review = review_form.save()
                create_audit_event(
                    action="review.create",
                    entity_type="risk_review",
                    entity_id=review.id,
                    metadata={"risk_id": review.risk_id, "decision": review.decision},
                    request=request,
                )
                decision_status_map = {
                    review.DECISION_ACCEPT: Risk.STATUS_CLOSED,
                    review.DECISION_REJECT: Risk.STATUS_IN_PROGRESS,
                    review.DECISION_REVISIT: Risk.STATUS_OPEN,
                }
                next_status = decision_status_map.get(review.decision)
                if next_status:
                    try:
                        review.risk.transition_to(next_status)
                    except ValidationError:
                        create_audit_event(
                            action="risk.status.update",
                            entity_type="risk",
                            entity_id=review.risk_id,
                            status=AuditEvent.STATUS_FAILED,
                            message=f"Review transition failed to {next_status}.",
                            request=request,
                        )
                        messages.warning(
                            request,
                            _("Review saved but status transition to %(status)s is not allowed.") % {"status": next_status},
                        )
                messages.success(request, _("Review added for risk #%(risk_id)s.") % {"risk_id": review.risk_id})
                return redirect("webui:risk-list")
            messages.error(request, _("Please fix review form errors."))

        elif action == "request_approval":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="approval.request",
                    entity_type="risk_approval",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for approval request.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to request approval."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if approval_request_form.is_valid():
                approval = approval_request_form.save(commit=False)
                approval.risk = risk
                approval.requested_by = request.user
                approval.save()
                create_audit_event(
                    action="approval.request",
                    entity_type="risk_approval",
                    entity_id=approval.id,
                    metadata={"risk_id": approval.risk_id},
                    request=request,
                )
                messages.success(request, _("Approval requested."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix approval request errors."))

        elif action == "decide_approval":
            if not _can_review_risks(request.user):
                create_audit_event(
                    action="approval.decide",
                    entity_type="risk_approval",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for approval decision.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to decide approvals."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            approval_id = request.POST.get("approval_id")
            approval = RiskApproval.objects.filter(id=approval_id, risk=risk).first()
            if not approval:
                messages.error(request, _("Approval request not found."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            approval_decision_form = RiskApprovalDecisionForm(prefix="approval_decision", data=request.POST or None, instance=approval)
            if approval_decision_form.is_valid():
                approval = approval_decision_form.save(commit=False)
                approval.decided_by = request.user
                approval.decided_at = timezone.now()
                approval.save()
                create_audit_event(
                    action="approval.decide",
                    entity_type="risk_approval",
                    entity_id=approval.id,
                    metadata={"risk_id": approval.risk_id, "status": approval.status},
                    request=request,
                )
                messages.success(request, _("Approval decision recorded."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix approval decision errors."))

        elif action == "bulk_update":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.bulk.update",
                    entity_type="risk",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for bulk risk update.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to bulk update risks."))
                return redirect("webui:risk-list")
            risk_ids = request.POST.getlist("risk_ids")
            if not risk_ids:
                messages.error(request, _("Select at least one risk to update."))
                return redirect("webui:risk-list")
            if bulk_form.is_valid():
                status_value = bulk_form.cleaned_data.get("status") or ""
                owner_value = (bulk_form.cleaned_data.get("owner") or "").strip()
                due_date_value = bulk_form.cleaned_data.get("due_date")
                clear_owner = bulk_form.cleaned_data.get("clear_owner")
                clear_due_date = bulk_form.cleaned_data.get("clear_due_date")

                if clear_owner:
                    owner_value = ""
                if clear_due_date:
                    due_date_value = None

                if not status_value and not owner_value and not due_date_value and not clear_owner and not clear_due_date:
                    messages.error(request, _("Select at least one field to update."))
                    return redirect("webui:risk-list")

                risks_to_update = Risk.objects.filter(id__in=risk_ids)
                updated_count = 0
                failed_transitions = []
                for item in risks_to_update:
                    changed_fields = []
                    if status_value:
                        try:
                            item.transition_to(status_value)
                        except ValidationError:
                            failed_transitions.append(item.id)
                        else:
                            changed_fields.append("status")
                    if owner_value or clear_owner:
                        item.owner = owner_value
                        changed_fields.append("owner")
                    if due_date_value or clear_due_date:
                        item.due_date = due_date_value
                        changed_fields.append("due_date")
                    if changed_fields:
                        item.save(update_fields=list(set(changed_fields)) + ["updated_at"])
                        updated_count += 1

                create_audit_event(
                    action="risk.bulk.update",
                    entity_type="risk",
                    metadata={"updated": updated_count, "failed_transitions": failed_transitions},
                    request=request,
                )
                if failed_transitions:
                    messages.warning(
                        request,
                        _("Some risks could not transition to the selected status: %(ids)s")
                        % {"ids": ", ".join(str(i) for i in failed_transitions)},
                    )
                messages.success(request, _("Bulk update applied to %(count)s risks.") % {"count": updated_count})
                if request.headers.get("HX-Request"):
                    return render(request, "webui/partials/risk_table_update.html", context)
                return redirect("webui:risk-list")
            messages.error(request, _("Please fix bulk update form errors."))

    context = {
        "risks": risks,
        "risk_form": risk_form,
        "scoring_form": scoring_form,
        "treatment_form": treatment_form,
        "review_form": review_form,
        "bulk_form": bulk_form,
        "show_form": show_form,
        "risk_status_choices": Risk.STATUS_CHOICES,
        "business_units": BusinessUnit.objects.order_by("code"),
        "selected_status": selected_status,
        "selected_business_unit_code": selected_business_unit_code,
        "query": query,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        **_permission_context(request.user),
    }

    if request.headers.get("HX-Request"):
        return render(request, "webui/partials/risk_table.html", context)

    return render(request, "webui/risks.html", context)


@login_required
def risk_export_csv(request):
    risks = (
        Risk.objects.select_related(
            "primary_asset",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method",
        )
        .prefetch_related("treatments", "reviews")
        .order_by("-created_at")
    )
    if not _can_view_all_assets(request.user):
        risks = risks.filter(primary_asset__in=_accessible_assets(request.user))

    selected_status = request.GET.get("status", "").strip()
    selected_business_unit_code = request.GET.get("business_unit_code", "").strip()
    query = request.GET.get("q", "").strip()

    if selected_status:
        risks = risks.filter(status=selected_status)
    if selected_business_unit_code:
        risks = risks.filter(business_unit__code=selected_business_unit_code)
    if query:
        risks = risks.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(primary_asset__asset_code__icontains=query)
            | Q(primary_asset__asset_name__icontains=query)
        )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risks.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "id",
            "title",
            "status",
            "owner",
            "due_date",
            "primary_asset",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method",
            "inherent_score",
            "residual_score",
            "treatment_count",
            "latest_review",
        ]
    )
    for risk in risks:
        latest_review = risk.reviews.first()
        writer.writerow(
            [
                risk.id,
                risk.title,
                risk.status,
                risk.owner,
                risk.due_date,
                risk.primary_asset.asset_code if risk.primary_asset_id else "",
                risk.business_unit.code if risk.business_unit_id else "",
                risk.cost_center.code if risk.cost_center_id else "",
                risk.section.code if risk.section_id else "",
                risk.asset_type.code if risk.asset_type_id else "",
                risk.scoring_method.code if risk.scoring_method_id else "",
                risk.inherent_score,
                risk.residual_score,
                risk.treatments.count(),
                f"{latest_review.decision} by {latest_review.reviewer.username}" if latest_review else "",
            ]
        )
    return response


@login_required
def risk_controls(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("control_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    controls = RiskControl.objects.order_by("name")
    if query:
        controls = controls.filter(
            Q(code__icontains=query) | Q(name__icontains=query) | Q(category__icontains=query)
        )
    paginator = Paginator(controls, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = RiskControl.objects.filter(id=edit_id).first()
        show_form = True

    form = RiskControlCreateForm(prefix="control", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:risk-controls")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage controls."))
            return redirect(redirect_target)

        if action == "delete":
            control_id = request.POST.get("control_id")
            control = RiskControl.objects.filter(id=control_id).first()
            if control:
                create_audit_event(
                    action="control.delete",
                    entity_type="risk_control",
                    entity_id=control.id,
                    request=request,
                )
                control.delete()
                messages.success(request, _("Control deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            control = form.save()
            create_audit_event(
                action="control.update" if edit_instance else "control.create",
                entity_type="risk_control",
                entity_id=control.id,
                request=request,
            )
            messages.success(request, _("Control saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix control form errors."))
        show_form = True

    return render(
        request,
        "webui/risk_controls.html",
        {
            "controls": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_issues(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("issue_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    issues = RiskIssue.objects.select_related("risk").order_by("-created_at")
    if query:
        issue_filter = (
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(status__icontains=query)
            | Q(owner__icontains=query)
            | Q(risk__title__icontains=query)
        )
        if query.isdigit():
            issue_filter |= Q(risk_id=int(query))
        issues = issues.filter(issue_filter)
    paginator = Paginator(issues, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = RiskIssue.objects.filter(id=edit_id).first()
        show_form = True

    form = RiskIssueCreateForm(prefix="issue", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:risk-issues")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage issues."))
            return redirect(redirect_target)

        if action == "delete":
            issue_id = request.POST.get("issue_id")
            issue = RiskIssue.objects.filter(id=issue_id).first()
            if issue:
                create_audit_event(
                    action="issue.delete",
                    entity_type="risk_issue",
                    entity_id=issue.id,
                    metadata={"risk_id": issue.risk_id},
                    request=request,
                )
                issue.delete()
                messages.success(request, _("Issue deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            issue = form.save()
            create_audit_event(
                action="issue.update" if edit_instance else "issue.create",
                entity_type="risk_issue",
                entity_id=issue.id,
                metadata={"risk_id": issue.risk_id},
                request=request,
            )
            messages.success(request, _("Issue saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix issue form errors."))
        show_form = True

    return render(
        request,
        "webui/risk_issues.html",
        {
            "issues": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_exceptions(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("exception_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    exceptions = RiskException.objects.select_related("risk").order_by("-created_at")
    if query:
        exception_filter = (
            Q(title__icontains=query)
            | Q(justification__icontains=query)
            | Q(status__icontains=query)
            | Q(owner__icontains=query)
            | Q(risk__title__icontains=query)
        )
        if query.isdigit():
            exception_filter |= Q(risk_id=int(query))
        exceptions = exceptions.filter(exception_filter)
    paginator = Paginator(exceptions, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = RiskException.objects.filter(id=edit_id).first()
        show_form = True

    form = RiskExceptionCreateForm(prefix="exception", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:risk-exceptions")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage exceptions."))
            return redirect(redirect_target)

        if action == "delete":
            exception_id = request.POST.get("exception_id")
            item = RiskException.objects.filter(id=exception_id).first()
            if item:
                create_audit_event(
                    action="exception.delete",
                    entity_type="risk_exception",
                    entity_id=item.id,
                    metadata={"risk_id": item.risk_id},
                    request=request,
                )
                item.delete()
                messages.success(request, _("Exception deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="exception.update" if edit_instance else "exception.create",
                entity_type="risk_exception",
                entity_id=item.id,
                metadata={"risk_id": item.risk_id},
                request=request,
            )
            messages.success(request, _("Exception saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix exception form errors."))
        show_form = True

    return render(
        request,
        "webui/risk_exceptions.html",
        {
            "exceptions": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_reports(request):
    query = request.GET.get("q", "").strip()
    run_query = request.GET.get("run_q", "").strip()
    edit_id = request.POST.get("schedule_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    schedules = RiskReportSchedule.objects.order_by("name")
    if query:
        schedules = schedules.filter(
            Q(name__icontains=query)
            | Q(report_type__icontains=query)
            | Q(frequency__icontains=query)
        )
    paginator = Paginator(schedules, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    runs = RiskReportRun.objects.select_related("schedule").order_by("-created_at")
    if run_query:
        runs = runs.filter(
            Q(schedule__name__icontains=run_query)
            | Q(status__icontains=run_query)
            | Q(message__icontains=run_query)
        )
    run_paginator = Paginator(runs, 20)
    run_page_obj = run_paginator.get_page(request.GET.get("run_page"))

    edit_instance = None
    if edit_id:
        edit_instance = RiskReportSchedule.objects.filter(id=edit_id).first()
        show_form = True

    form = RiskReportScheduleForm(prefix="schedule", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:risk-reports")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage report schedules."))
            return redirect(redirect_target)

        if action == "delete":
            schedule_id = request.POST.get("schedule_id")
            schedule = RiskReportSchedule.objects.filter(id=schedule_id).first()
            if schedule:
                create_audit_event(
                    action="report.schedule.delete",
                    entity_type="risk_report_schedule",
                    entity_id=schedule.id,
                    request=request,
                )
                schedule.delete()
                messages.success(request, _("Report schedule deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            schedule = form.save()
            create_audit_event(
                action="report.schedule.update" if edit_instance else "report.schedule.create",
                entity_type="risk_report_schedule",
                entity_id=schedule.id,
                request=request,
            )
            messages.success(request, _("Report schedule saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix report schedule errors."))
        show_form = True

    return render(
        request,
        "webui/risk_reports.html",
        {
            "schedules": page_obj,
            "page_obj": page_obj,
            "query": query,
            "run_query": run_query,
            "runs": run_page_obj,
            "run_page_obj": run_page_obj,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_notifications(request):
    query = request.GET.get("q", "").strip()
    notifications = RiskNotification.objects.filter(user=request.user).order_by("-created_at")
    if query:
        notification_filter = Q(message__icontains=query) | Q(notification_type__icontains=query)
        if query.isdigit():
            notification_filter |= Q(risk_id=int(query))
        notifications = notifications.filter(notification_filter)
    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    if request.method == "POST":
        if request.POST.get("mark_all_read") == "1":
            RiskNotification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
            messages.success(request, _("All notifications marked as read."))
            return redirect("webui:risk-notifications")
        notification_id = request.POST.get("notification_id")
        notification = notifications.filter(id=notification_id).first()
        if notification and notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
            messages.success(request, _("Notification marked as read."))
            return redirect("webui:risk-notifications")
    return render(
        request,
        "webui/notifications.html",
        {
            "notifications": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_heatmap(request):
    selected_business_unit_code = request.GET.get("business_unit_code", "")
    selected_cost_center_code = request.GET.get("cost_center_code", "")
    selected_section_code = request.GET.get("section_code", "")
    selected_asset_type_code = request.GET.get("asset_type_code", "")
    selected_status = request.GET.get("status", "")
    selected_owner = request.GET.get("owner", "").strip()
    due_date_from = request.GET.get("due_date_from", "")
    due_date_to = request.GET.get("due_date_to", "")

    risks = Risk.objects.select_related("business_unit", "cost_center", "section", "asset_type")
    if selected_business_unit_code:
        risks = risks.filter(business_unit__code=selected_business_unit_code)
    if selected_cost_center_code:
        risks = risks.filter(cost_center__code=selected_cost_center_code)
    if selected_section_code:
        risks = risks.filter(section__code=selected_section_code)
    if selected_asset_type_code:
        risks = risks.filter(asset_type__code=selected_asset_type_code)
    if selected_status:
        risks = risks.filter(status=selected_status)
    if selected_owner:
        risks = risks.filter(owner__icontains=selected_owner)
    if due_date_from:
        risks = risks.filter(due_date__gte=due_date_from)
    if due_date_to:
        risks = risks.filter(due_date__lte=due_date_to)

    matrix = []
    for impact in range(5, 0, -1):
        row = []
        for likelihood in range(1, 6):
            count = risks.filter(impact=impact, likelihood=likelihood).count()
            row.append({"impact": impact, "likelihood": likelihood, "count": count})
        matrix.append(row)

    return render(
        request,
        "webui/risk_heatmap.html",
        {
            "matrix": matrix,
            "business_units": BusinessUnit.objects.order_by("code"),
            "cost_centers": CostCenter.objects.order_by("code"),
            "sections": Section.objects.order_by("code"),
            "asset_types": AssetType.objects.order_by("code"),
            "risk_status_choices": Risk.STATUS_CHOICES,
            "selected_business_unit_code": selected_business_unit_code,
            "selected_cost_center_code": selected_cost_center_code,
            "selected_section_code": selected_section_code,
            "selected_asset_type_code": selected_asset_type_code,
            "selected_status": selected_status,
            "selected_owner": selected_owner,
            "due_date_from": due_date_from,
            "due_date_to": due_date_to,
            **_permission_context(request.user),
        },
    )


@login_required
def risk_detail(request, risk_id: int):
    risk_queryset = Risk.objects.select_related(
            "primary_asset",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method",
        ).prefetch_related("risk_assets__asset", "treatments", "reviews", "scoring_history")
    if not _can_view_all_assets(request.user):
        risk_queryset = risk_queryset.filter(primary_asset__in=_accessible_assets(request.user))
    risk = get_object_or_404(risk_queryset, id=risk_id)
    linked_assets = (
        Asset.objects.filter(asset_risks__risk=risk)
        .select_related("asset_type")
        .order_by("asset_code")
    )
    dependency_edges = (
        AssetDependency.objects.select_related("source_asset", "target_asset")
        .filter(source_asset__in=linked_assets, target_asset__in=linked_assets)
        .order_by("source_asset__asset_code", "dependency_type", "target_asset__asset_code")
    )
    linked_assets_json = list(
        linked_assets.values(
            "id",
            "asset_code",
            "asset_name",
            "asset_type__code",
        )
    )
    dependency_edges_json = list(
        dependency_edges.values(
            "source_asset_id",
            "target_asset_id",
            "dependency_type",
            "strength",
        )
    )

    update_form = RiskUpdateForm(prefix="edit", data=request.POST or None, instance=risk)
    link_form = RiskAssetLinkForm(prefix="link", data=request.POST or None, risk=risk, user=request.user)
    scoring_form = RiskScoringApplyForm(prefix="scoring", data=request.POST or None)
    scoring_inputs_form = RiskScoringInputsForm(prefix="scoring_inputs", data=request.POST or None, risk=risk)
    treatment_form = RiskTreatmentCreateForm(prefix="treatment", data=request.POST or None)
    review_form = RiskReviewCreateForm(prefix="review", data=request.POST or None, user=request.user)
    approval_request_form = RiskApprovalRequestForm(prefix="approval_request", data=request.POST or None)
    approval_decision_form = RiskApprovalDecisionForm(prefix="approval_decision", data=request.POST or None)

    scoring_form.fields["risk_id"].initial = risk.id
    scoring_form.fields["risk_id"].widget = forms.HiddenInput()
    treatment_form.fields["risk"].initial = risk
    treatment_form.fields["risk"].widget = forms.HiddenInput()
    review_form.fields["risk"].initial = risk
    review_form.fields["risk"].widget = forms.HiddenInput()

    def _summary_context(current_risk: Risk) -> dict:
        return {
            "risk": current_risk,
            "risk_status_choices": Risk.STATUS_CHOICES,
            "can_manage_risks": _can_manage_risks(request.user),
        }

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_risk":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.update",
                    entity_type="risk",
                    entity_id=risk.id,
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for risk update.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to update risks."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if update_form.is_valid():
                updated_risk = update_form.save()
                updated_risk.refresh_scores(actor="webui")
                create_audit_event(action="risk.update", entity_type="risk", entity_id=updated_risk.id, request=request)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "webui/partials/risk_summary.html",
                        _summary_context(updated_risk),
                    )
                messages.success(request, _("Risk updated."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix risk update errors."))

        elif action == "link_assets":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.assets.update",
                    entity_type="risk",
                    entity_id=risk.id,
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for risk asset update.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to update linked assets."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if link_form.is_valid():
                link_form.save()
                create_audit_event(
                    action="risk.assets.update",
                    entity_type="risk",
                    entity_id=risk.id,
                    request=request,
                )
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "webui/partials/risk_linked_assets.html",
                        {
                            "risk": risk,
                            "link_form": RiskAssetLinkForm(risk=risk, prefix="link"),
                            "can_manage_risks": _can_manage_risks(request.user),
                        },
                    )
                messages.success(request, _("Linked assets updated."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix linked assets form errors."))

        elif action == "update_scoring_inputs":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="risk.scoring.update_inputs",
                    entity_type="risk",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for scoring update.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to update scoring inputs."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if scoring_inputs_form.is_valid():
                updated_risk = risk
                updated_risk.scoring_method = scoring_inputs_form.cleaned_data["scoring_method"]
                updated_risk.likelihood = scoring_inputs_form.cleaned_data["likelihood"]
                if updated_risk.scoring_method and updated_risk.scoring_method.method_type == RiskScoringMethod.METHOD_CIA:
                    updated_risk.confidentiality = scoring_inputs_form.cleaned_data["confidentiality"]
                    updated_risk.integrity = scoring_inputs_form.cleaned_data["integrity"]
                    updated_risk.availability = scoring_inputs_form.cleaned_data["availability"]
                    updated_risk.impact = updated_risk.impact
                    RiskScoringDread.objects.filter(risk=updated_risk).delete()
                    RiskScoringOwasp.objects.filter(risk=updated_risk).delete()
                    RiskScoringCvss.objects.filter(risk=updated_risk).delete()
                elif updated_risk.scoring_method and updated_risk.scoring_method.method_type == RiskScoringMethod.METHOD_DREAD:
                    dread, _ = RiskScoringDread.objects.get_or_create(risk=updated_risk)
                    dread.damage = scoring_inputs_form.cleaned_data["dread_damage"]
                    dread.reproducibility = scoring_inputs_form.cleaned_data["dread_reproducibility"]
                    dread.exploitability = scoring_inputs_form.cleaned_data["dread_exploitability"]
                    dread.affected_users = scoring_inputs_form.cleaned_data["dread_affected_users"]
                    dread.discoverability = scoring_inputs_form.cleaned_data["dread_discoverability"]
                    dread.save()
                    likelihood_vals = [
                        dread.reproducibility,
                        dread.exploitability,
                        dread.discoverability,
                    ]
                    impact_vals = [dread.damage, dread.affected_users]
                    updated_risk.likelihood = int(round(sum(likelihood_vals) / len(likelihood_vals)))
                    updated_risk.impact = int(round(sum(impact_vals) / len(impact_vals)))
                    updated_risk.confidentiality = None
                    updated_risk.integrity = None
                    updated_risk.availability = None
                    RiskScoringOwasp.objects.filter(risk=updated_risk).delete()
                    RiskScoringCvss.objects.filter(risk=updated_risk).delete()
                elif updated_risk.scoring_method and updated_risk.scoring_method.method_type == RiskScoringMethod.METHOD_OWASP:
                    owasp, _ = RiskScoringOwasp.objects.get_or_create(risk=updated_risk)
                    owasp.skill_level = scoring_inputs_form.cleaned_data["owasp_skill_level"]
                    owasp.motive = scoring_inputs_form.cleaned_data["owasp_motive"]
                    owasp.opportunity = scoring_inputs_form.cleaned_data["owasp_opportunity"]
                    owasp.size = scoring_inputs_form.cleaned_data["owasp_size"]
                    owasp.ease_of_discovery = scoring_inputs_form.cleaned_data["owasp_ease_of_discovery"]
                    owasp.ease_of_exploit = scoring_inputs_form.cleaned_data["owasp_ease_of_exploit"]
                    owasp.awareness = scoring_inputs_form.cleaned_data["owasp_awareness"]
                    owasp.intrusion_detection = scoring_inputs_form.cleaned_data["owasp_intrusion_detection"]
                    owasp.loss_confidentiality = scoring_inputs_form.cleaned_data["owasp_loss_confidentiality"]
                    owasp.loss_integrity = scoring_inputs_form.cleaned_data["owasp_loss_integrity"]
                    owasp.loss_availability = scoring_inputs_form.cleaned_data["owasp_loss_availability"]
                    owasp.loss_accountability = scoring_inputs_form.cleaned_data["owasp_loss_accountability"]
                    owasp.financial_damage = scoring_inputs_form.cleaned_data["owasp_financial_damage"]
                    owasp.reputation_damage = scoring_inputs_form.cleaned_data["owasp_reputation_damage"]
                    owasp.non_compliance = scoring_inputs_form.cleaned_data["owasp_non_compliance"]
                    owasp.privacy_violation = scoring_inputs_form.cleaned_data["owasp_privacy_violation"]
                    owasp.save()
                    likelihood_vals = [
                        owasp.skill_level,
                        owasp.motive,
                        owasp.opportunity,
                        owasp.size,
                        owasp.ease_of_discovery,
                        owasp.ease_of_exploit,
                        owasp.awareness,
                        owasp.intrusion_detection,
                    ]
                    impact_vals = [
                        owasp.loss_confidentiality,
                        owasp.loss_integrity,
                        owasp.loss_availability,
                        owasp.loss_accountability,
                        owasp.financial_damage,
                        owasp.reputation_damage,
                        owasp.non_compliance,
                        owasp.privacy_violation,
                    ]
                    updated_risk.likelihood = int(round(sum(likelihood_vals) / len(likelihood_vals)))
                    updated_risk.impact = int(round(sum(impact_vals) / len(impact_vals)))
                    updated_risk.confidentiality = None
                    updated_risk.integrity = None
                    updated_risk.availability = None
                    RiskScoringDread.objects.filter(risk=updated_risk).delete()
                    RiskScoringCvss.objects.filter(risk=updated_risk).delete()
                elif updated_risk.scoring_method and updated_risk.scoring_method.method_type == RiskScoringMethod.METHOD_CVSS:
                    cvss, _ = RiskScoringCvss.objects.get_or_create(risk=updated_risk)
                    cvss.attack_vector = scoring_inputs_form.cleaned_data["cvss_attack_vector"]
                    cvss.attack_complexity = scoring_inputs_form.cleaned_data["cvss_attack_complexity"]
                    cvss.authentication = scoring_inputs_form.cleaned_data["cvss_authentication"]
                    cvss.confidentiality_impact = scoring_inputs_form.cleaned_data["cvss_confidentiality_impact"]
                    cvss.integrity_impact = scoring_inputs_form.cleaned_data["cvss_integrity_impact"]
                    cvss.availability_impact = scoring_inputs_form.cleaned_data["cvss_availability_impact"]
                    cvss.exploitability = scoring_inputs_form.cleaned_data["cvss_exploitability"]
                    cvss.remediation_level = scoring_inputs_form.cleaned_data["cvss_remediation_level"]
                    cvss.report_confidence = scoring_inputs_form.cleaned_data["cvss_report_confidence"]
                    cvss.collateral_damage_potential = scoring_inputs_form.cleaned_data["cvss_collateral_damage_potential"]
                    cvss.target_distribution = scoring_inputs_form.cleaned_data["cvss_target_distribution"]
                    cvss.confidentiality_requirement = scoring_inputs_form.cleaned_data["cvss_confidentiality_requirement"]
                    cvss.integrity_requirement = scoring_inputs_form.cleaned_data["cvss_integrity_requirement"]
                    cvss.availability_requirement = scoring_inputs_form.cleaned_data["cvss_availability_requirement"]
                    cvss.save()
                    likelihood_vals = [
                        cvss.attack_vector,
                        cvss.attack_complexity,
                        cvss.authentication,
                        cvss.exploitability,
                        cvss.report_confidence,
                    ]
                    impact_vals = [
                        cvss.confidentiality_impact,
                        cvss.integrity_impact,
                        cvss.availability_impact,
                        cvss.collateral_damage_potential,
                        cvss.target_distribution,
                        cvss.confidentiality_requirement,
                        cvss.integrity_requirement,
                        cvss.availability_requirement,
                    ]
                    updated_risk.likelihood = int(round(sum(likelihood_vals) / len(likelihood_vals)))
                    updated_risk.impact = int(round(sum(impact_vals) / len(impact_vals)))
                    updated_risk.confidentiality = None
                    updated_risk.integrity = None
                    updated_risk.availability = None
                    RiskScoringDread.objects.filter(risk=updated_risk).delete()
                    RiskScoringOwasp.objects.filter(risk=updated_risk).delete()
                else:
                    updated_risk.impact = scoring_inputs_form.cleaned_data["impact"]
                    updated_risk.confidentiality = None
                    updated_risk.integrity = None
                    updated_risk.availability = None
                    RiskScoringDread.objects.filter(risk=updated_risk).delete()
                    RiskScoringOwasp.objects.filter(risk=updated_risk).delete()
                    RiskScoringCvss.objects.filter(risk=updated_risk).delete()
                updated_risk.save()
                updated_risk.refresh_scores(actor="webui")
                create_audit_event(
                    action="risk.scoring.update_inputs",
                    entity_type="risk",
                    entity_id=updated_risk.id,
                    request=request,
                )
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "webui/partials/risk_scoring_update.html",
                        {
                            **_summary_context(updated_risk),
                            "scoring_history": updated_risk.scoring_history.all()[:20],
                        },
                    )
                messages.success(request, _("Scoring inputs updated."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix scoring input errors."))

        elif action == "add_treatment":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="treatment.create",
                    entity_type="risk_treatment",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for treatment creation.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to manage treatments."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if treatment_form.is_valid():
                treatment = treatment_form.save(commit=False)
                treatment.risk = risk
                treatment.save()
                treatment.risk.refresh_scores(actor="webui-treatment")
                create_audit_event(
                    action="treatment.create",
                    entity_type="risk_treatment",
                    entity_id=treatment.id,
                    metadata={"risk_id": treatment.risk_id},
                    request=request,
                )
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "webui/partials/risk_treatment_update.html",
                        {
                            **_summary_context(treatment.risk),
                            "treatments": treatment.risk.treatments.all(),
                            "treatment_status_choices": RiskTreatment.STATUS_CHOICES,
                            "can_manage_risks": _can_manage_risks(request.user),
                        },
                    )
                messages.success(request, _("Treatment added: %(title)s") % {"title": treatment.title})
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix treatment form errors."))

        elif action == "add_review":
            if not _can_review_risks(request.user):
                create_audit_event(
                    action="review.create",
                    entity_type="risk_review",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for review creation.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to add reviews."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.risk = risk
                review.save()
                create_audit_event(
                    action="review.create",
                    entity_type="risk_review",
                    entity_id=review.id,
                    metadata={"risk_id": review.risk_id, "decision": review.decision},
                    request=request,
                )
                decision_status_map = {
                    review.DECISION_ACCEPT: Risk.STATUS_CLOSED,
                    review.DECISION_REJECT: Risk.STATUS_IN_PROGRESS,
                    review.DECISION_REVISIT: Risk.STATUS_OPEN,
                }
                next_status = decision_status_map.get(review.decision)
                if next_status:
                    try:
                        review.risk.transition_to(next_status)
                    except ValidationError:
                        create_audit_event(
                            action="risk.status.update",
                            entity_type="risk",
                            entity_id=review.risk_id,
                            status=AuditEvent.STATUS_FAILED,
                            message=f"Review transition failed to {next_status}.",
                            request=request,
                        )
                        messages.warning(
                            request,
                            _("Review saved but status transition to %(status)s is not allowed.") % {"status": next_status},
                        )
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "webui/partials/risk_review_update.html",
                        {
                            **_summary_context(review.risk),
                            "reviews": review.risk.reviews.select_related("reviewer").all(),
                        },
                    )
                messages.success(request, _("Review added for risk #%(risk_id)s.") % {"risk_id": review.risk_id})
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix review form errors."))

        elif action == "request_approval":
            if not _can_manage_risks(request.user):
                create_audit_event(
                    action="approval.request",
                    entity_type="risk_approval",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for approval request.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to request approval."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            if approval_request_form.is_valid():
                approval = approval_request_form.save(commit=False)
                approval.risk = risk
                approval.requested_by = request.user
                approval.save()
                create_audit_event(
                    action="approval.request",
                    entity_type="risk_approval",
                    entity_id=approval.id,
                    metadata={"risk_id": approval.risk_id},
                    request=request,
                )
                messages.success(request, _("Approval requested."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix approval request errors."))

        elif action == "decide_approval":
            if not _can_review_risks(request.user):
                create_audit_event(
                    action="approval.decide",
                    entity_type="risk_approval",
                    status=AuditEvent.STATUS_DENIED,
                    message="Permission denied for approval decision.",
                    request=request,
                )
                messages.error(request, _("You do not have permission to decide approvals."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            approval_id = request.POST.get("approval_id")
            approval = RiskApproval.objects.filter(id=approval_id, risk=risk).first()
            if not approval:
                messages.error(request, _("Approval request not found."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            approval_decision_form = RiskApprovalDecisionForm(
                prefix="approval_decision",
                data=request.POST or None,
                instance=approval,
            )
            if approval_decision_form.is_valid():
                approval = approval_decision_form.save(commit=False)
                approval.decided_by = request.user
                approval.decided_at = timezone.now()
                approval.save()
                create_audit_event(
                    action="approval.decide",
                    entity_type="risk_approval",
                    entity_id=approval.id,
                    metadata={"risk_id": approval.risk_id, "status": approval.status},
                    request=request,
                )
                messages.success(request, _("Approval decision recorded."))
                return redirect("webui:risk-detail", risk_id=risk.id)
            messages.error(request, _("Please fix approval decision errors."))

    context = {
        "risk": risk,
        "risk_status_choices": Risk.STATUS_CHOICES,
        "treatment_status_choices": RiskTreatment.STATUS_CHOICES,
        "scoring_history": risk.scoring_history.all()[:20],
        "treatments": risk.treatments.all(),
        "reviews": risk.reviews.select_related("reviewer").all(),
        "approvals": risk.approvals.select_related("requested_by", "decided_by").all(),
        "scoring_methods": list(
            RiskScoringMethod.objects.filter(is_active=True)
            .order_by("name")
            .values(
                "id",
                "name",
                "method_type",
                "likelihood_weight",
                "impact_weight",
                "treatment_effectiveness_weight",
            )
        ),
        "linked_assets": linked_assets,
        "dependency_edges": dependency_edges,
        "linked_assets_json": linked_assets_json,
        "dependency_edges_json": dependency_edges_json,
        "link_form": link_form,
        "update_form": update_form,
        "scoring_form": scoring_form,
        "scoring_inputs_form": scoring_inputs_form,
        "treatment_form": treatment_form,
        "review_form": review_form,
        "approval_request_form": approval_request_form,
        "approval_decision_form": approval_decision_form,
        **_permission_context(request.user),
    }
    return render(request, "webui/risk_detail.html", context)


@login_required
@require_POST
def risk_status_update(request, risk_id: int):
    if not _can_manage_risks(request.user):
        create_audit_event(
            action="risk.status.update",
            entity_type="risk",
            entity_id=risk_id,
            status=AuditEvent.STATUS_DENIED,
            message="Permission denied for risk status update.",
            request=request,
        )
        return HttpResponseForbidden(_("You do not have permission to update risk status."))

    risk = get_object_or_404(Risk, id=risk_id)
    status = request.POST.get("status", "").strip()
    valid_statuses = {choice[0] for choice in Risk.STATUS_CHOICES}
    if status not in valid_statuses:
        create_audit_event(
            action="risk.status.update",
            entity_type="risk",
            entity_id=risk.id,
            status=AuditEvent.STATUS_FAILED,
            message=f"Invalid risk status value: {status}",
            request=request,
        )
        return HttpResponseBadRequest(_("Invalid risk status value."))

    try:
        risk.transition_to(status)
    except ValidationError:
        create_audit_event(
            action="risk.status.update",
            entity_type="risk",
            entity_id=risk.id,
            status=AuditEvent.STATUS_FAILED,
            message=f"Invalid transition attempt to {status}.",
            request=request,
        )
        return HttpResponseBadRequest(_("Invalid transition for current risk status."))

    create_audit_event(
        action="risk.status.update",
        entity_type="risk",
        entity_id=risk.id,
        metadata={"status": status},
        request=request,
    )

    if request.headers.get("HX-Request"):
        origin = request.POST.get("origin", "detail")
        if origin == "list":
            return render(
                request,
                "webui/partials/risk_status_cell.html",
                {
                    "risk": risk,
                    "risk_status_choices": Risk.STATUS_CHOICES,
                    "can_manage_risks": _can_manage_risks(request.user),
                    "origin": "list",
                },
            )
        return render(
            request,
            "webui/partials/risk_summary.html",
            {
                "risk": risk,
                "risk_status_choices": Risk.STATUS_CHOICES,
                "can_manage_risks": _can_manage_risks(request.user),
            },
        )

    messages.success(request, _("Risk status updated."))
    return redirect("webui:risk-detail", risk_id=risk.id)


@login_required
@require_POST
def treatment_progress_update(request, treatment_id: int):
    if not _can_manage_risks(request.user):
        create_audit_event(
            action="treatment.update",
            entity_type="risk_treatment",
            entity_id=treatment_id,
            status=AuditEvent.STATUS_DENIED,
            message="Permission denied for treatment update.",
            request=request,
        )
        return HttpResponseForbidden(_("You do not have permission to update treatments."))

    treatment = get_object_or_404(RiskTreatment.objects.select_related("risk"), id=treatment_id)

    try:
        progress_percent = int(request.POST.get("progress_percent", treatment.progress_percent))
    except (TypeError, ValueError):
        create_audit_event(
            action="treatment.update",
            entity_type="risk_treatment",
            entity_id=treatment.id,
            status=AuditEvent.STATUS_FAILED,
            message="Invalid treatment progress value.",
            request=request,
        )
        return HttpResponseBadRequest(_("Invalid treatment progress value."))

    if progress_percent < 0 or progress_percent > 100:
        create_audit_event(
            action="treatment.update",
            entity_type="risk_treatment",
            entity_id=treatment.id,
            status=AuditEvent.STATUS_FAILED,
            message="Progress percent out of range.",
            request=request,
        )
        return HttpResponseBadRequest(_("Treatment progress must be between 0 and 100."))

    status = request.POST.get("status", treatment.status).strip()
    valid_statuses = {choice[0] for choice in RiskTreatment.STATUS_CHOICES}
    if status not in valid_statuses:
        create_audit_event(
            action="treatment.update",
            entity_type="risk_treatment",
            entity_id=treatment.id,
            status=AuditEvent.STATUS_FAILED,
            message=f"Invalid treatment status {status}.",
            request=request,
        )
        return HttpResponseBadRequest(_("Invalid treatment status value."))

    treatment.progress_percent = progress_percent
    treatment.status = status
    treatment.save(update_fields=["progress_percent", "status", "updated_at"])
    treatment.risk.refresh_scores(actor="webui-inline")

    create_audit_event(
        action="treatment.update",
        entity_type="risk_treatment",
        entity_id=treatment.id,
        metadata={"status": status, "progress_percent": progress_percent},
        request=request,
    )

    if request.headers.get("HX-Request"):
        return render(
            request,
            "webui/partials/risk_treatment_update.html",
            {
                "treatments": treatment.risk.treatments.all(),
                "treatment_status_choices": RiskTreatment.STATUS_CHOICES,
                "can_manage_risks": _can_manage_risks(request.user),
                "risk": treatment.risk,
                "risk_status_choices": Risk.STATUS_CHOICES,
            },
        )

    messages.success(request, _("Treatment updated."))
    return redirect("webui:risk-detail", risk_id=treatment.risk_id)


@login_required
def location_risk_overview(request):
    selected_business_unit_code = request.GET.get("business_unit_code", "")
    selected_cost_center_code = request.GET.get("cost_center_code", "")
    selected_section_code = request.GET.get("section_code", "")
    selected_asset_type_code = request.GET.get("asset_type_code", "")
    selected_status = request.GET.get("status", "")
    selected_owner = request.GET.get("owner", "").strip()
    due_date_from = request.GET.get("due_date_from", "")
    due_date_to = request.GET.get("due_date_to", "")

    risks = Risk.objects.select_related(
        "primary_asset",
        "business_unit",
        "cost_center",
        "section",
        "asset_type",
    )

    if selected_business_unit_code:
        risks = risks.filter(business_unit__code=selected_business_unit_code)
    if selected_cost_center_code:
        risks = risks.filter(cost_center__code=selected_cost_center_code)
    if selected_section_code:
        risks = risks.filter(section__code=selected_section_code)
    if selected_asset_type_code:
        risks = risks.filter(asset_type__code=selected_asset_type_code)
    if selected_status:
        risks = risks.filter(status=selected_status)
    if selected_owner:
        risks = risks.filter(owner__icontains=selected_owner)
    if due_date_from:
        risks = risks.filter(due_date__gte=due_date_from)
    if due_date_to:
        risks = risks.filter(due_date__lte=due_date_to)

    risks = risks.order_by("-created_at")

    by_section = (
        risks.values(
            "business_unit__code",
            "business_unit__name",
            "cost_center__code",
            "cost_center__name",
            "section__code",
            "section__name",
        )
        .annotate(
            total_risks=Count("id", distinct=True),
            open_risks=Count("id", filter=Q(status=Risk.STATUS_OPEN), distinct=True),
        )
        .order_by("business_unit__name", "cost_center__name", "section__name")
    )

    section_labels = [
        row["section__name"] or row["section__code"] or "-" for row in by_section
    ]
    section_total_values = [row["total_risks"] for row in by_section]
    section_open_values = [row["open_risks"] for row in by_section]

    context = {
        "risks": risks,
        "by_section": by_section,
        "business_units": BusinessUnit.objects.order_by("code"),
        "cost_centers": CostCenter.objects.order_by("code"),
        "sections": Section.objects.order_by("code"),
        "selected_business_unit_code": selected_business_unit_code,
        "selected_cost_center_code": selected_cost_center_code,
        "selected_section_code": selected_section_code,
        "selected_asset_type_code": selected_asset_type_code,
        "selected_status": selected_status,
        "selected_owner": selected_owner,
        "due_date_from": due_date_from,
        "due_date_to": due_date_to,
        "section_labels": section_labels,
        "section_total_values": section_total_values,
        "section_open_values": section_open_values,
        "asset_types": AssetType.objects.order_by("code"),
        "risk_status_choices": Risk.STATUS_CHOICES,
        **_permission_context(request.user),
    }

    if request.headers.get("HX-Request"):
        return render(request, "webui/partials/location_risks_content.html", context)

    return render(request, "webui/location_risks.html", context)


@login_required
def location_tree(request):
    selected_business_unit_code = request.GET.get("business_unit_code", "")
    selected_cost_center_code = request.GET.get("cost_center_code", "")
    selected_section_code = request.GET.get("section_code", "")
    selected_asset_type_code = request.GET.get("asset_type_code", "")
    selected_status = request.GET.get("status", "")
    selected_owner = request.GET.get("owner", "").strip()
    due_date_from = request.GET.get("due_date_from", "")
    due_date_to = request.GET.get("due_date_to", "")

    filters_active = any(
        [
            selected_business_unit_code,
            selected_cost_center_code,
            selected_section_code,
            selected_asset_type_code,
            selected_status,
            selected_owner,
            due_date_from,
            due_date_to,
        ]
    )

    risks = Risk.objects.select_related("primary_asset", "business_unit", "cost_center", "section", "asset_type")
    if selected_business_unit_code:
        risks = risks.filter(business_unit__code=selected_business_unit_code)
    if selected_cost_center_code:
        risks = risks.filter(cost_center__code=selected_cost_center_code)
    if selected_section_code:
        risks = risks.filter(section__code=selected_section_code)
    if selected_asset_type_code:
        risks = risks.filter(asset_type__code=selected_asset_type_code)
    if selected_status:
        risks = risks.filter(status=selected_status)
    if selected_owner:
        risks = risks.filter(owner__icontains=selected_owner)
    if due_date_from:
        risks = risks.filter(due_date__gte=due_date_from)
    if due_date_to:
        risks = risks.filter(due_date__lte=due_date_to)

    section_stats = {
        item["section_id"]: item
        for item in risks.values("section_id").annotate(
            total_risks=Count("id", distinct=True),
            open_risks=Count("id", filter=Q(status=Risk.STATUS_OPEN), distinct=True),
        )
    }

    asset_stats = {
        item["primary_asset_id"]: item
        for item in risks.values("primary_asset_id").annotate(
            total_risks=Count("id", distinct=True),
            open_risks=Count("id", filter=Q(status=Risk.STATUS_OPEN), distinct=True),
        )
    }

    business_units = BusinessUnit.objects.prefetch_related("cost_centers__sections__assets").order_by("code")
    if selected_business_unit_code:
        business_units = business_units.filter(code=selected_business_unit_code)

    tree = []
    for bu in business_units:
        bu_node = {
            "business_unit": bu,
            "cost_centers": [],
            "total_risks": 0,
            "open_risks": 0,
        }

        for cost_center in bu.cost_centers.all().order_by("code"):
            if selected_cost_center_code and cost_center.code != selected_cost_center_code:
                continue
            cc_node = {
                "cost_center": cost_center,
                "sections": [],
                "total_risks": 0,
                "open_risks": 0,
            }

            for section in cost_center.sections.all().order_by("code"):
                if selected_section_code and section.code != selected_section_code:
                    continue
                sec_stat = section_stats.get(section.id, {"total_risks": 0, "open_risks": 0})
                if filters_active and sec_stat["total_risks"] == 0:
                    continue
                assets = []
                for asset in section.assets.all().order_by("asset_code"):
                    if selected_asset_type_code and getattr(asset.asset_type, "code", None) != selected_asset_type_code:
                        continue
                    a_stat = asset_stats.get(asset.id, {"total_risks": 0, "open_risks": 0})
                    if filters_active and a_stat["total_risks"] == 0:
                        continue
                    assets.append(
                        {
                            "asset": asset,
                            "total_risks": a_stat["total_risks"],
                            "open_risks": a_stat["open_risks"],
                        }
                    )

                sec_node = {
                    "section": section,
                    "assets": assets,
                    "total_risks": sec_stat["total_risks"],
                    "open_risks": sec_stat["open_risks"],
                }

                cc_node["sections"].append(sec_node)
                cc_node["total_risks"] += sec_node["total_risks"]
                cc_node["open_risks"] += sec_node["open_risks"]

            bu_node["cost_centers"].append(cc_node)
            bu_node["total_risks"] += cc_node["total_risks"]
            bu_node["open_risks"] += cc_node["open_risks"]

        if not filters_active or bu_node["total_risks"] > 0:
            tree.append(bu_node)

    return render(
        request,
        "webui/location_tree.html",
        {
            "tree": tree,
            "business_units": BusinessUnit.objects.order_by("code"),
            "cost_centers": CostCenter.objects.order_by("code"),
            "sections": Section.objects.order_by("code"),
            "asset_types": AssetType.objects.order_by("code"),
            "risk_status_choices": Risk.STATUS_CHOICES,
            "selected_business_unit_code": selected_business_unit_code,
            "selected_cost_center_code": selected_cost_center_code,
            "selected_section_code": selected_section_code,
            "selected_asset_type_code": selected_asset_type_code,
            "selected_status": selected_status,
            "selected_owner": selected_owner,
            "due_date_from": due_date_from,
            "due_date_to": due_date_to,
            **_permission_context(request.user),
        },
    )


@login_required
def scoring_method_list(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("method_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    methods = RiskScoringMethod.objects.order_by("name")
    if query:
        methods = methods.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(method_type__icontains=query))
    paginator = Paginator(methods, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = RiskScoringMethod.objects.filter(id=edit_id).first()
        show_form = True

    form = RiskScoringMethodCreateForm(prefix="method", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:scoring-method-list")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_scoring(request.user):
            create_audit_event(
                action="risk.scoring_method.create",
                entity_type="risk_scoring_method",
                status=AuditEvent.STATUS_DENIED,
                message="Permission denied for scoring method creation.",
                request=request,
            )
            messages.error(request, _("You do not have permission to manage scoring methods."))
            return redirect(redirect_target)

        if action == "delete":
            method_id = request.POST.get("method_id")
            method = RiskScoringMethod.objects.filter(id=method_id).first()
            if method:
                create_audit_event(
                    action="risk.scoring_method.delete",
                    entity_type="risk_scoring_method",
                    entity_id=method.id,
                    metadata={"code": method.code, "method_type": method.method_type},
                    request=request,
                )
                method.delete()
                messages.success(request, _("Scoring method deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            method = form.save()
            create_audit_event(
                action="risk.scoring_method.update" if edit_instance else "risk.scoring_method.create",
                entity_type="risk_scoring_method",
                entity_id=method.id,
                metadata={"code": method.code, "method_type": method.method_type},
                request=request,
            )
            messages.success(request, _("Scoring method saved: %(name)s") % {"name": method.name})
            return redirect(redirect_target)

        messages.error(request, _("Please fix scoring method form errors."))
        show_form = True

    return render(
        request,
        "webui/scoring_methods.html",
        {
            "methods": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def integration_sync(request):
    if not _can_run_sync(request.user):
        create_audit_event(
            action="eam.sync.execute",
            entity_type="integration_sync",
            status=AuditEvent.STATUS_DENIED,
            message="Permission denied for EAM sync.",
            request=request,
        )
        messages.error(request, _("You do not have permission to run EAM sync."))
        return redirect("webui:dashboard")

    query = request.GET.get("q", "").strip()
    sync_runs = IntegrationSyncRun.objects.order_by("-created_at")
    if query:
        sync_runs = sync_runs.filter(
            Q(status__icontains=query)
            | Q(direction__icontains=query)
            | Q(plugin_name__icontains=query)
            | Q(plugin_version__icontains=query)
            | Q(message__icontains=query)
        )
    paginator = Paginator(sync_runs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    form = EamSyncForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            sync_run = form.execute()
            create_audit_event(
                action="eam.sync.execute",
                entity_type="integration_sync",
                entity_id=sync_run.id,
                status=AuditEvent.STATUS_SUCCESS if sync_run.status == IntegrationSyncRun.STATUS_SUCCESS else AuditEvent.STATUS_FAILED,
                message=sync_run.message,
                metadata={"plugin_name": sync_run.plugin_name, "plugin_version": sync_run.plugin_version},
                request=request,
            )
            if sync_run.status == IntegrationSyncRun.STATUS_SUCCESS:
                messages.success(
                    request,
                    _("Sync completed (%(plugin)s:%(version)s)")
                    % {"plugin": sync_run.plugin_name, "version": sync_run.plugin_version},
                )
            else:
                messages.error(
                    request,
                    _("Sync failed (%(plugin)s:%(version)s): %(message)s")
                    % {
                        "plugin": sync_run.plugin_name,
                        "version": sync_run.plugin_version,
                        "message": sync_run.message,
                    },
                )
            return redirect("webui:integration-sync")
        messages.error(request, _("Please fix sync form errors."))

    return render(
        request,
        "webui/integration_sync.html",
        {
            "sync_runs": page_obj,
            "page_obj": page_obj,
            "query": query,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def third_party_vendors(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("vendor_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))

    vendors = ThirdPartyVendor.objects.order_by("name")
    if query:
        vendors = vendors.filter(
            Q(name__icontains=query)
            | Q(category__icontains=query)
            | Q(contact_email__icontains=query)
            | Q(owner__icontains=query)
        )

    paginator = Paginator(vendors, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ThirdPartyVendor.objects.filter(id=edit_id).first()
        show_form = True

    form = ThirdPartyVendorForm(prefix="vendor", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        base_url = reverse("webui:third-party-vendors")
        redirect_target = f"{base_url}?q={query}" if query else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage third-party vendors."))
            return redirect(redirect_target)

        if action == "delete":
            vendor_id = request.POST.get("vendor_id")
            vendor = ThirdPartyVendor.objects.filter(id=vendor_id).first()
            if vendor:
                create_audit_event(
                    action="third_party.vendor.delete",
                    entity_type="third_party_vendor",
                    entity_id=vendor.id,
                    request=request,
                )
                vendor.delete()
                messages.success(request, _("Vendor deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            vendor = form.save()
            create_audit_event(
                action="third_party.vendor.update" if edit_instance else "third_party.vendor.create",
                entity_type="third_party_vendor",
                entity_id=vendor.id,
                request=request,
            )
            messages.success(request, _("Vendor saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix vendor form errors."))
        show_form = True

    return render(
        request,
        "webui/third_party_vendors.html",
        {
            "vendors": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def third_party_risks(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("risk_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))

    risks = ThirdPartyRisk.objects.select_related("vendor").order_by("-created_at")
    if query:
        risk_filter = (
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(status__icontains=query)
            | Q(owner__icontains=query)
            | Q(vendor__name__icontains=query)
        )
        risks = risks.filter(risk_filter)

    paginator = Paginator(risks, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ThirdPartyRisk.objects.filter(id=edit_id).first()
        show_form = True

    form = ThirdPartyRiskForm(prefix="third_party_risk", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        base_url = reverse("webui:third-party-risks")
        redirect_target = f"{base_url}?q={query}" if query else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage third-party risks."))
            return redirect(redirect_target)

        if action == "delete":
            risk_id = request.POST.get("risk_id")
            item = ThirdPartyRisk.objects.filter(id=risk_id).first()
            if item:
                create_audit_event(
                    action="third_party.risk.delete",
                    entity_type="third_party_risk",
                    entity_id=item.id,
                    metadata={"vendor_id": item.vendor_id},
                    request=request,
                )
                item.delete()
                messages.success(request, _("Third-party risk deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="third_party.risk.update" if edit_instance else "third_party.risk.create",
                entity_type="third_party_risk",
                entity_id=item.id,
                metadata={"vendor_id": item.vendor_id},
                request=request,
            )
            messages.success(request, _("Third-party risk saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix third-party risk form errors."))
        show_form = True

    return render(
        request,
        "webui/third_party_risks.html",
        {
            "risks": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def policy_standards(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("policy_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))

    policies = PolicyStandard.objects.order_by("name")
    if query:
        policies = policies.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(category__icontains=query)
            | Q(owner__icontains=query)
        )

    paginator = Paginator(policies, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = PolicyStandard.objects.filter(id=edit_id).first()
        show_form = True

    form = PolicyStandardForm(prefix="policy", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        base_url = reverse("webui:policy-standards")
        redirect_target = f"{base_url}?q={query}" if query else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage policies."))
            return redirect(redirect_target)

        if action == "delete":
            policy_id = request.POST.get("policy_id")
            policy = PolicyStandard.objects.filter(id=policy_id).first()
            if policy:
                create_audit_event(
                    action="policy.delete",
                    entity_type="policy_standard",
                    entity_id=policy.id,
                    request=request,
                )
                policy.delete()
                messages.success(request, _("Policy deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            policy = form.save()
            create_audit_event(
                action="policy.update" if edit_instance else "policy.create",
                entity_type="policy_standard",
                entity_id=policy.id,
                request=request,
            )
            messages.success(request, _("Policy saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix policy form errors."))
        show_form = True

    return render(
        request,
        "webui/policy_standards.html",
        {
            "policies": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def policy_mappings(request):
    control_query = request.GET.get("control_q", "").strip()
    risk_query = request.GET.get("risk_q", "").strip()

    control_mappings = PolicyControlMapping.objects.select_related("policy", "control").order_by("-id")
    if control_query:
        control_mappings = control_mappings.filter(
            Q(policy__name__icontains=control_query)
            | Q(control__name__icontains=control_query)
        )
    control_paginator = Paginator(control_mappings, 20)
    control_page_obj = control_paginator.get_page(request.GET.get("control_page"))

    risk_mappings = PolicyRiskMapping.objects.select_related("policy", "risk").order_by("-id")
    if risk_query:
        risk_mappings = risk_mappings.filter(
            Q(policy__name__icontains=risk_query)
            | Q(risk__title__icontains=risk_query)
        )
    risk_paginator = Paginator(risk_mappings, 20)
    risk_page_obj = risk_paginator.get_page(request.GET.get("risk_page"))

    control_form = PolicyControlMappingForm(prefix="policy_control", data=request.POST or None)
    risk_form = PolicyRiskMappingForm(prefix="policy_risk", data=request.POST or None)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        base_url = reverse("webui:policy-mappings")

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage policy mappings."))
            return redirect(base_url)

        if action == "delete_control":
            mapping_id = request.POST.get("mapping_id")
            mapping = PolicyControlMapping.objects.filter(id=mapping_id).first()
            if mapping:
                create_audit_event(
                    action="policy.control.unlink",
                    entity_type="policy_control_mapping",
                    entity_id=mapping.id,
                    request=request,
                )
                mapping.delete()
                messages.success(request, _("Control mapping deleted."))
            return redirect(base_url)

        if action == "delete_risk":
            mapping_id = request.POST.get("mapping_id")
            mapping = PolicyRiskMapping.objects.filter(id=mapping_id).first()
            if mapping:
                create_audit_event(
                    action="policy.risk.unlink",
                    entity_type="policy_risk_mapping",
                    entity_id=mapping.id,
                    request=request,
                )
                mapping.delete()
                messages.success(request, _("Risk mapping deleted."))
            return redirect(base_url)

        if action == "save_control":
            if control_form.is_valid():
                mapping = control_form.save()
                create_audit_event(
                    action="policy.control.link",
                    entity_type="policy_control_mapping",
                    entity_id=mapping.id,
                    request=request,
                )
                messages.success(request, _("Control mapping saved."))
                return redirect(base_url)
            messages.error(request, _("Please fix control mapping form errors."))

        if action == "save_risk":
            if risk_form.is_valid():
                mapping = risk_form.save()
                create_audit_event(
                    action="policy.risk.link",
                    entity_type="policy_risk_mapping",
                    entity_id=mapping.id,
                    request=request,
                )
                messages.success(request, _("Risk mapping saved."))
                return redirect(base_url)
            messages.error(request, _("Please fix risk mapping form errors."))

    return render(
        request,
        "webui/policy_mappings.html",
        {
            "control_mappings": control_page_obj,
            "control_page_obj": control_page_obj,
            "risk_mappings": risk_page_obj,
            "risk_page_obj": risk_page_obj,
            "control_query": control_query,
            "risk_query": risk_query,
            "control_form": control_form,
            "risk_form": risk_form,
            **_permission_context(request.user),
        },
    )


@login_required
def control_tests(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("plan_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))

    plans = ControlTestPlan.objects.select_related("control").order_by("-created_at")
    if query:
        plans = plans.filter(
            Q(control__code__icontains=query)
            | Q(control__name__icontains=query)
            | Q(owner__icontains=query)
        )
    plans = plans.prefetch_related(Prefetch("runs", queryset=ControlTestRun.objects.order_by("-tested_at")))

    paginator = Paginator(plans, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    for plan in page_obj:
        runs = list(plan.runs.all())
        plan.latest_run = runs[0] if runs else None

    edit_instance = None
    if edit_id:
        edit_instance = ControlTestPlan.objects.filter(id=edit_id).first()
        show_form = True

    form = ControlTestPlanForm(prefix="control_test_plan", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:control-tests")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage control tests."))
            return redirect(redirect_target)

        if action == "delete":
            plan_id = request.POST.get("plan_id")
            plan = ControlTestPlan.objects.filter(id=plan_id).first()
            if plan:
                create_audit_event(
                    action="control_test.plan.delete",
                    entity_type="control_test_plan",
                    entity_id=plan.id,
                    request=request,
                )
                plan.delete()
                messages.success(request, _("Test plan deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            plan = form.save()
            create_audit_event(
                action="control_test.plan.update" if edit_instance else "control_test.plan.create",
                entity_type="control_test_plan",
                entity_id=plan.id,
                request=request,
            )
            messages.success(request, _("Test plan saved."))
            return redirect(redirect_target)

        messages.error(request, _("Please fix test plan form errors."))
        show_form = True

    return render(
        request,
        "webui/control_tests.html",
        {
            "plans": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def control_test_runs(request):
    query = request.GET.get("q", "").strip()
    plan_filter = request.GET.get("plan_id", "").strip()
    edit_id = request.POST.get("run_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))

    runs = ControlTestRun.objects.select_related("plan", "plan__control").order_by("-tested_at")
    if plan_filter:
        runs = runs.filter(plan_id=plan_filter)
    if query:
        runs = runs.filter(
            Q(plan__control__name__icontains=query)
            | Q(plan__control__code__icontains=query)
            | Q(tester__icontains=query)
            | Q(result__icontains=query)
        )

    paginator = Paginator(runs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ControlTestRun.objects.filter(id=edit_id).first()
        show_form = True

    form_initial = {}
    if plan_filter and not edit_instance:
        form_initial["plan"] = plan_filter

    form = ControlTestRunForm(
        prefix="control_test_run",
        data=request.POST or None,
        instance=edit_instance,
        initial=form_initial or None,
    )

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        return_plan = request.POST.get("return_plan", "").strip()
        base_url = reverse("webui:control-test-runs")
        params = []
        if return_q:
            params.append(f"q={return_q}")
        if return_plan:
            params.append(f"plan_id={return_plan}")
        redirect_target = f"{base_url}?{'&'.join(params)}" if params else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage control test runs."))
            return redirect(redirect_target)

        if action == "delete":
            run_id = request.POST.get("run_id")
            run = ControlTestRun.objects.filter(id=run_id).first()
            if run:
                create_audit_event(
                    action="control_test.run.delete",
                    entity_type="control_test_run",
                    entity_id=run.id,
                    request=request,
                )
                run.delete()
                messages.success(request, _("Test run deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            run = form.save()
            create_audit_event(
                action="control_test.run.update" if edit_instance else "control_test.run.create",
                entity_type="control_test_run",
                entity_id=run.id,
                request=request,
            )
            messages.success(request, _("Test run saved."))
            return redirect(redirect_target)

        messages.error(request, _("Please fix test run form errors."))
        show_form = True

    plans_for_filter = ControlTestPlan.objects.select_related("control").order_by("control__name")

    return render(
        request,
        "webui/control_test_runs.html",
        {
            "runs": page_obj,
            "page_obj": page_obj,
            "query": query,
            "plan_filter": plan_filter,
            "plans_for_filter": plans_for_filter,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def assessments(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("assessment_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    items = Assessment.objects.order_by("-created_at")
    if query:
        items = items.filter(
            Q(title__icontains=query)
            | Q(owner__icontains=query)
            | Q(status__icontains=query)
        )
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = Assessment.objects.filter(id=edit_id).first()
        show_form = True

    form = AssessmentForm(prefix="assessment", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:assessments")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage assessments."))
            return redirect(redirect_target)

        if action == "delete":
            item_id = request.POST.get("assessment_id")
            item = Assessment.objects.filter(id=item_id).first()
            if item:
                create_audit_event(
                    action="assessment.delete",
                    entity_type="assessment",
                    entity_id=item.id,
                    request=request,
                )
                item.delete()
                messages.success(request, _("Assessment deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="assessment.update" if edit_instance else "assessment.create",
                entity_type="assessment",
                entity_id=item.id,
                request=request,
            )
            messages.success(request, _("Assessment saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix assessment form errors."))
        show_form = True

    return render(
        request,
        "webui/assessments.html",
        {
            "assessments": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def vulnerabilities(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("vulnerability_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    items = Vulnerability.objects.select_related("asset", "risk").order_by("-created_at")
    if not _can_view_all_assets(request.user):
        asset_qs = _accessible_assets(request.user)
        items = items.filter(Q(asset__in=asset_qs) | Q(risk__primary_asset__in=asset_qs))
    if query:
        items = items.filter(
            Q(title__icontains=query)
            | Q(severity__icontains=query)
            | Q(status__icontains=query)
            | Q(owner__icontains=query)
        )
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = items.filter(id=edit_id).first()
        show_form = True

    form = VulnerabilityForm(prefix="vulnerability", data=request.POST or None, instance=edit_instance, user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:vulnerabilities")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage vulnerabilities."))
            return redirect(redirect_target)

        if action == "delete":
            item_id = request.POST.get("vulnerability_id")
            item = Vulnerability.objects.filter(id=item_id).first()
            if item:
                create_audit_event(
                    action="vulnerability.delete",
                    entity_type="vulnerability",
                    entity_id=item.id,
                    request=request,
                )
                item.delete()
                messages.success(request, _("Vulnerability deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="vulnerability.update" if edit_instance else "vulnerability.create",
                entity_type="vulnerability",
                entity_id=item.id,
                request=request,
            )
            messages.success(request, _("Vulnerability saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix vulnerability form errors."))
        show_form = True

    return render(
        request,
        "webui/vulnerabilities.html",
        {
            "vulnerabilities": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def governance_programs(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("program_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    programs = GovernanceProgram.objects.order_by("name")
    if query:
        programs = programs.filter(
            Q(name__icontains=query)
            | Q(owner__icontains=query)
            | Q(status__icontains=query)
        )
    paginator = Paginator(programs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = GovernanceProgram.objects.filter(id=edit_id).first()
        show_form = True

    form = GovernanceProgramForm(prefix="program", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        if not _can_manage_governance(request.user):
            messages.error(request, _("You do not have permission to manage governance programs."))
            return redirect("webui:governance-programs")
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:governance-programs")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if action == "delete":
            program_id = request.POST.get("program_id")
            item = GovernanceProgram.objects.filter(id=program_id).first()
            if item:
                create_audit_event(
                    action="governance.delete",
                    entity_type="governance_program",
                    entity_id=item.id,
                    request=request,
                )
                item.delete()
                messages.success(request, _("Governance program deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="governance.update" if edit_instance else "governance.create",
                entity_type="governance_program",
                entity_id=item.id,
                request=request,
            )
            messages.success(request, _("Governance program saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix governance program form errors."))
        show_form = True

    return render(
        request,
        "webui/governance_programs.html",
        {
            "programs": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def compliance_frameworks(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("framework_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    items = ComplianceFramework.objects.order_by("name")
    if not _can_view_compliance(request.user):
        messages.error(request, _("You do not have permission to view compliance data."))
        return redirect("webui:dashboard")
    if query:
        items = items.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(owner__icontains=query)
        )
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ComplianceFramework.objects.filter(id=edit_id).first()
        show_form = True

    form = ComplianceFrameworkForm(prefix="framework", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        if not _can_manage_compliance(request.user):
            messages.error(request, _("You do not have permission to manage compliance frameworks."))
            return redirect("webui:compliance-frameworks")
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:compliance-frameworks")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if action == "delete":
            item_id = request.POST.get("framework_id")
            item = ComplianceFramework.objects.filter(id=item_id).first()
            if item:
                create_audit_event(
                    action="compliance.framework.delete",
                    entity_type="compliance_framework",
                    entity_id=item.id,
                    request=request,
                )
                item.delete()
                messages.success(request, _("Compliance framework deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="compliance.framework.update" if edit_instance else "compliance.framework.create",
                entity_type="compliance_framework",
                entity_id=item.id,
                request=request,
            )
            messages.success(request, _("Compliance framework saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix compliance framework form errors."))
        show_form = True

    return render(
        request,
        "webui/compliance_frameworks.html",
        {
            "frameworks": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def compliance_requirements(request):
    query = request.GET.get("q", "").strip()
    framework_filter = request.GET.get("framework_id", "").strip()
    edit_id = request.POST.get("requirement_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    items = ComplianceRequirement.objects.select_related("framework", "control").order_by("framework__name", "code")
    if not _can_view_compliance(request.user):
        messages.error(request, _("You do not have permission to view compliance data."))
        return redirect("webui:dashboard")
    if framework_filter:
        items = items.filter(framework_id=framework_filter)
    if query:
        items = items.filter(
            Q(code__icontains=query)
            | Q(title__icontains=query)
            | Q(status__icontains=query)
            | Q(framework__name__icontains=query)
        )
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ComplianceRequirement.objects.filter(id=edit_id).first()
        show_form = True

    form_initial = {}
    if framework_filter and not edit_instance:
        form_initial["framework"] = framework_filter

    form = ComplianceRequirementForm(
        prefix="requirement",
        data=request.POST or None,
        instance=edit_instance,
        initial=form_initial or None,
    )

    if request.method == "POST":
        if not _can_manage_compliance(request.user):
            messages.error(request, _("You do not have permission to manage compliance requirements."))
            return redirect("webui:compliance-requirements")
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        return_framework = request.POST.get("return_framework", "").strip()
        base_url = reverse("webui:compliance-requirements")
        params = []
        if return_q:
            params.append(f"q={return_q}")
        if return_framework:
            params.append(f"framework_id={return_framework}")
        redirect_target = f"{base_url}?{'&'.join(params)}" if params else base_url

        if action == "delete":
            item_id = request.POST.get("requirement_id")
            item = ComplianceRequirement.objects.filter(id=item_id).first()
            if item:
                create_audit_event(
                    action="compliance.requirement.delete",
                    entity_type="compliance_requirement",
                    entity_id=item.id,
                    request=request,
                )
                item.delete()
                messages.success(request, _("Compliance requirement deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            item = form.save()
            create_audit_event(
                action="compliance.requirement.update" if edit_instance else "compliance.requirement.create",
                entity_type="compliance_requirement",
                entity_id=item.id,
                request=request,
            )
            messages.success(request, _("Compliance requirement saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix compliance requirement form errors."))
        show_form = True

    frameworks_for_filter = ComplianceFramework.objects.order_by("name")

    return render(
        request,
        "webui/compliance_requirements.html",
        {
            "requirements": page_obj,
            "page_obj": page_obj,
            "query": query,
            "framework_filter": framework_filter,
            "frameworks_for_filter": frameworks_for_filter,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def reports_overview(request):
    return render(
        request,
        "webui/reports_overview.html",
        {
            **_permission_context(request.user),
        },
    )


@login_required
def assessment_reports(request):
    query = request.GET.get("q", "").strip()
    items = Assessment.objects.order_by("-created_at")
    if query:
        items = items.filter(Q(title__icontains=query) | Q(status__icontains=query) | Q(owner__icontains=query))
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "webui/assessment_reports.html",
        {
            "assessments": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def vulnerability_reports(request):
    query = request.GET.get("q", "").strip()
    items = Vulnerability.objects.select_related("asset", "risk").order_by("-created_at")
    if not _can_view_all_assets(request.user):
        asset_qs = _accessible_assets(request.user)
        items = items.filter(Q(asset__in=asset_qs) | Q(risk__primary_asset__in=asset_qs))
    if query:
        items = items.filter(Q(title__icontains=query) | Q(severity__icontains=query) | Q(status__icontains=query))
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "webui/vulnerability_reports.html",
        {
            "vulnerabilities": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def compliance_reports(request):
    query = request.GET.get("q", "").strip()
    if not _can_view_compliance(request.user):
        messages.error(request, _("You do not have permission to view compliance data."))
        return redirect("webui:dashboard")
    items = ComplianceRequirement.objects.select_related("framework", "control").order_by("framework__name", "code")
    if query:
        items = items.filter(
            Q(code__icontains=query)
            | Q(title__icontains=query)
            | Q(status__icontains=query)
            | Q(framework__name__icontains=query)
        )
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "webui/compliance_reports.html",
        {
            "requirements": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def export_report_csv(request, report_key: str):
    allowed = {
        "risk_status": _("Risk Status Distribution"),
        "vulnerability_status": _("Vulnerability Status Distribution"),
        "vulnerability_severity": _("Vulnerability Severity Distribution"),
        "compliance_status": _("Compliance Status Distribution"),
    }
    if report_key not in allowed:
        return HttpResponseBadRequest(_("Unknown report export."))

    asset_scope = _accessible_assets(request.user)
    if report_key == "risk_status":
        risk_qs = Risk.objects.all()
        if not _can_view_all_assets(request.user):
            risk_qs = risk_qs.filter(primary_asset__in=asset_scope)
        rows = risk_qs.values("status").annotate(total=Count("id")).order_by("status")
        label_lookup = dict(Risk.STATUS_CHOICES)
        filename = "risk_status_distribution.csv"
    elif report_key == "vulnerability_status":
        vuln_qs = Vulnerability.objects.all()
        if not _can_view_all_assets(request.user):
            vuln_qs = vuln_qs.filter(Q(asset__in=asset_scope) | Q(risk__primary_asset__in=asset_scope))
        rows = vuln_qs.values("status").annotate(total=Count("id")).order_by("status")
        label_lookup = dict(Vulnerability.STATUS_CHOICES)
        filename = "vulnerability_status_distribution.csv"
    elif report_key == "vulnerability_severity":
        vuln_qs = Vulnerability.objects.all()
        if not _can_view_all_assets(request.user):
            vuln_qs = vuln_qs.filter(Q(asset__in=asset_scope) | Q(risk__primary_asset__in=asset_scope))
        rows = vuln_qs.values("severity").annotate(total=Count("id")).order_by("severity")
        label_lookup = dict(Vulnerability.SEVERITY_CHOICES)
        filename = "vulnerability_severity_distribution.csv"
    else:
        if not _can_view_all_assets(request.user):
            return HttpResponseForbidden(_("You do not have permission to export compliance data."))
        rows = ComplianceRequirement.objects.values("status").annotate(total=Count("id")).order_by("status")
        label_lookup = dict(ComplianceRequirement.STATUS_CHOICES)
        filename = "compliance_status_distribution.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["label", "count"])
    for row in rows:
        label_key = row.get("status") or row.get("severity")
        label = _(label_lookup.get(label_key, label_key))
        writer.writerow([label, row["total"]])

    create_audit_event(
        action="report.export",
        entity_type="report_export",
        metadata={"report_key": report_key, "title": allowed[report_key]},
        request=request,
    )
    return response


@login_required
def critical_services(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("service_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    services = CriticalService.objects.order_by("name")
    if query:
        services = services.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(owner__icontains=query))
    paginator = Paginator(services, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = CriticalService.objects.filter(id=edit_id).first()
        show_form = True

    form = CriticalServiceForm(prefix="service", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:critical-services")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
            return redirect(redirect_target)

        if action == "delete":
            service_id = request.POST.get("service_id")
            service = CriticalService.objects.filter(id=service_id).first()
            if service:
                create_audit_event(
                    action="service.delete",
                    entity_type="critical_service",
                    entity_id=service.id,
                    request=request,
                )
                service.delete()
                messages.success(request, _("Service deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            service = form.save()
            create_audit_event(
                action="service.update" if edit_instance else "service.create",
                entity_type="critical_service",
                entity_id=service.id,
                request=request,
            )
            messages.success(request, _("Service saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix service form errors."))
        show_form = True

    return render(
        request,
        "webui/critical_services.html",
        {
            "services": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def bia_profiles(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("profile_id") or request.GET.get("edit")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    profiles = ServiceBIAProfile.objects.select_related("service").order_by("service__name")
    if query:
        profiles = profiles.filter(Q(service__name__icontains=query) | Q(service__code__icontains=query))
    paginator = Paginator(profiles, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = ServiceBIAProfile.objects.filter(id=edit_id).first()
        show_form = True

    form = ServiceBIAProfileForm(prefix="bia", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:bia-profiles")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
            return redirect(redirect_target)

        if action == "delete":
            profile_id = request.POST.get("profile_id")
            profile = ServiceBIAProfile.objects.filter(id=profile_id).first()
            if profile:
                create_audit_event(
                    action="bia.delete",
                    entity_type="service_bia_profile",
                    entity_id=profile.id,
                    request=request,
                )
                profile.delete()
                messages.success(request, _("BIA profile deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            profile = form.save()
            create_audit_event(
                action="bia.update" if edit_instance else "bia.create",
                entity_type="service_bia_profile",
                entity_id=profile.id,
                request=request,
            )
            messages.success(request, _("BIA profile saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix BIA form errors."))
        show_form = True

    return render(
        request,
        "webui/bia_profiles.html",
        {
            "profiles": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )


@login_required
def hazards(request):
    query = request.GET.get("q", "").strip()
    hazards_qs = Hazard.objects.order_by("name")
    if query:
        hazards_qs = hazards_qs.filter(Q(code__icontains=query) | Q(name__icontains=query))
    paginator = Paginator(hazards_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    if request.method == "POST":
        action = request.POST.get("action", "delete")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:hazards")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
            return redirect(redirect_target)

        if action == "delete":
            hazard_id = request.POST.get("hazard_id")
            hazard = Hazard.objects.filter(id=hazard_id).first()
            if hazard:
                create_audit_event(
                    action="hazard.delete",
                    entity_type="hazard",
                    entity_id=hazard.id,
                    request=request,
                )
                hazard.delete()
                messages.success(request, _("Hazard deleted."))
            return redirect(redirect_target)

    return render(
        request,
        "webui/hazards.html",
        {
            "hazards": page_obj,
            "page_obj": page_obj,
            "query": query,
            **_permission_context(request.user),
        },
    )


@login_required
def hazard_detail(request, hazard_id: Optional[int] = None):
    edit_link_id = request.POST.get("link_id") or request.GET.get("edit_link")
    edit_instance = None
    if hazard_id:
        edit_instance = Hazard.objects.filter(id=hazard_id).first()

    link_instance = None
    if edit_link_id:
        link_instance = HazardLink.objects.filter(id=edit_link_id).first()
        if link_instance:
            edit_instance = edit_instance or link_instance.hazard

    form = HazardForm(prefix="hazard", data=request.POST or None, instance=edit_instance)
    link_form = HazardLinkForm(
        prefix="hazard_link",
        data=request.POST or None,
        instance=link_instance,
        hazard=(edit_instance or (link_instance.hazard if link_instance else None)),
    )
    hazard_links = HazardLink.objects.select_related("hazard", "asset", "service").order_by("-created_at")
    if edit_instance:
        hazard_links = hazard_links.filter(hazard=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
            return redirect(reverse("webui:hazards"))

        if action == "link_hazard":
            if link_form.is_valid():
                link = link_form.save()
                create_audit_event(
                    action="hazard.link.create",
                    entity_type="hazard_link",
                    entity_id=link.id,
                    request=request,
                )
                messages.success(request, _("Hazard link saved."))
                return redirect(reverse("webui:hazard-detail", kwargs={"hazard_id": link.hazard_id}))
            messages.error(request, _("Please fix hazard link form errors."))

        if action == "delete_link":
            link_id = request.POST.get("link_id")
            link = HazardLink.objects.filter(id=link_id).first()
            if link:
                hazard_target = link.hazard_id
                create_audit_event(
                    action="hazard.link.delete",
                    entity_type="hazard_link",
                    entity_id=link.id,
                    request=request,
                )
                link.delete()
                messages.success(request, _("Hazard link deleted."))
                return redirect(reverse("webui:hazard-detail", kwargs={"hazard_id": hazard_target}))

        if action == "save":
            if form.is_valid():
                hazard = form.save()
                create_audit_event(
                    action="hazard.update" if edit_instance else "hazard.create",
                    entity_type="hazard",
                    entity_id=hazard.id,
                    request=request,
                )
                messages.success(request, _("Hazard saved."))
                return redirect(reverse("webui:hazard-detail", kwargs={"hazard_id": hazard.id}))
            messages.error(request, _("Please fix hazard form errors."))

    return render(
        request,
        "webui/hazard_detail.html",
        {
            "edit_instance": edit_instance,
            "form": form,
            "link_form": link_form,
            "hazard_links": hazard_links[:50],
            **_permission_context(request.user),
        },
    )


@login_required
def scenarios(request):
    query = request.GET.get("q", "").strip()
    edit_id = request.POST.get("scenario_id") or request.GET.get("edit")
    simulate_id = request.GET.get("simulate")
    duration_override = request.GET.get("duration")
    show_form = request.GET.get("new") == "1" or bool(request.GET.get("edit"))
    scenarios_qs = Scenario.objects.select_related("hazard").order_by("-created_at")
    if query:
        scenarios_qs = scenarios_qs.filter(Q(name__icontains=query) | Q(hazard__name__icontains=query))
    paginator = Paginator(scenarios_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    edit_instance = None
    if edit_id:
        edit_instance = Scenario.objects.filter(id=edit_id).first()
        show_form = True

    form = ScenarioForm(prefix="scenario", data=request.POST or None, instance=edit_instance)
    simulation_result = None

    if simulate_id:
        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
        else:
            scenario = Scenario.objects.select_related("hazard").filter(id=simulate_id).first()
            if scenario:
                duration_hours = None
                if duration_override:
                    try:
                        duration_hours = int(duration_override)
                    except ValueError:
                        messages.error(request, _("Duration must be a number of hours."))
                simulation_result = simulate_scenario(scenario, duration_hours=duration_hours)
            else:
                messages.error(request, _("Scenario not found."))

    if request.method == "POST":
        action = request.POST.get("action", "save")
        return_q = request.POST.get("return_q", "").strip()
        base_url = reverse("webui:scenarios")
        redirect_target = f"{base_url}?q={return_q}" if return_q else base_url

        if not _can_manage_risks(request.user):
            messages.error(request, _("You do not have permission to manage risks."))
            return redirect(redirect_target)

        if action == "delete":
            scenario_id = request.POST.get("scenario_id")
            scenario = Scenario.objects.filter(id=scenario_id).first()
            if scenario:
                create_audit_event(
                    action="scenario.delete",
                    entity_type="scenario",
                    entity_id=scenario.id,
                    request=request,
                )
                scenario.delete()
                messages.success(request, _("Scenario deleted."))
            return redirect(redirect_target)

        if form.is_valid():
            scenario = form.save()
            create_audit_event(
                action="scenario.update" if edit_instance else "scenario.create",
                entity_type="scenario",
                entity_id=scenario.id,
                request=request,
            )
            messages.success(request, _("Scenario saved."))
            return redirect(redirect_target)
        messages.error(request, _("Please fix scenario form errors."))
        show_form = True

    return render(
        request,
        "webui/scenarios.html",
        {
            "scenarios": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            "simulation_result": simulation_result,
            "duration_override": duration_override or "",
            **_permission_context(request.user),
        },
    )


@login_required
def continuity_strategies(request):
    items = ContinuityStrategy.objects.select_related("service", "bia_profile", "scenario").order_by("code")
    query = request.GET.get("q", "").strip()
    show_form = request.GET.get("new") == "1"
    edit_id = request.GET.get("edit")
    edit_instance = None
    if edit_id:
        edit_instance = ContinuityStrategy.objects.filter(id=edit_id).first()
        show_form = True

    if query:
        items = items.filter(
            Q(code__icontains=query)
            | Q(name__icontains=query)
            | Q(service__name__icontains=query)
        )

    page_number = request.GET.get("page", "1")
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(page_number)

    form = ContinuityStrategyForm(prefix="continuity", data=request.POST or None, instance=edit_instance)

    if request.method == "POST":
        action = request.POST.get("action")
        redirect_target = reverse("webui:continuity-strategies")

        if action == "delete":
            if not _can_manage_risks(request.user):
                messages.error(request, _("You do not have permission to manage risks."))
                return redirect(redirect_target)
            strategy_id = request.POST.get("strategy_id")
            strategy = ContinuityStrategy.objects.filter(id=strategy_id).first()
            if strategy:
                strategy.delete()
                messages.success(request, _("Continuity strategy deleted."))
            return redirect(redirect_target)

        if action == "save":
            if not _can_manage_risks(request.user):
                messages.error(request, _("You do not have permission to manage risks."))
                return redirect(redirect_target)
            if form.is_valid():
                strategy = form.save()
                messages.success(request, _("Continuity strategy saved."))
                return redirect(redirect_target)
            messages.error(request, _("Please fix continuity strategy form errors."))
            show_form = True

    return render(
        request,
        "webui/continuity_strategies.html",
        {
            "strategies": page_obj,
            "page_obj": page_obj,
            "query": query,
            "show_form": show_form,
            "edit_instance": edit_instance,
            "form": form,
            **_permission_context(request.user),
        },
    )
