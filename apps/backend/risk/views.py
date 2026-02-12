from django.db.models import Q
from rest_framework import decorators, response, status, viewsets
from rest_framework.permissions import IsAuthenticated

from core.audit import create_audit_event
from core.permissions import (
    IsRiskAdminOrReadOnly,
    IsRiskManagerOrReadOnly,
    IsRiskReviewerOrReadOnly,
    IsGovernanceManagerOrReadOnly,
    IsComplianceAuditorOrReadOnly,
)

from asset.access import accessible_assets, can_view_all_assets

from .models import (
    Risk,
    RiskApproval,
    RiskControl,
    RiskNotification,
    RiskIssue,
    RiskException,
    RiskReportRun,
    RiskReportSchedule,
    RiskReview,
    RiskScoringMethod,
    RiskScoringSnapshot,
    RiskTreatment,
    Assessment,
    Vulnerability,
    GovernanceProgram,
    ComplianceFramework,
    ComplianceRequirement,
    ControlTestPlan,
    ControlTestRun,
)
from .serializers import (
    RiskApprovalSerializer,
    RiskControlSerializer,
    RiskNotificationSerializer,
    RiskIssueSerializer,
    RiskExceptionSerializer,
    RiskReportRunSerializer,
    RiskReportScheduleSerializer,
    RiskReviewSerializer,
    RiskScoringMethodSerializer,
    RiskScoringSnapshotSerializer,
    RiskSerializer,
    RiskTreatmentSerializer,
    AssessmentSerializer,
    VulnerabilitySerializer,
    GovernanceProgramSerializer,
    ComplianceFrameworkSerializer,
    ComplianceRequirementSerializer,
    ControlTestPlanSerializer,
    ControlTestRunSerializer,
)


class RiskScoringMethodViewSet(viewsets.ModelViewSet):
    queryset = RiskScoringMethod.objects.order_by("name")
    serializer_class = RiskScoringMethodSerializer
    permission_classes = [IsRiskAdminOrReadOnly]
    search_fields = ("code", "name")
    ordering_fields = ("code", "name", "created_at", "updated_at")


class RiskTreatmentViewSet(viewsets.ModelViewSet):
    queryset = RiskTreatment.objects.select_related("risk").order_by("-created_at")
    serializer_class = RiskTreatmentSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("title", "status", "owner")
    ordering_fields = ("created_at", "updated_at", "due_date", "progress_percent")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs

    def perform_create(self, serializer):
        treatment = serializer.save()
        treatment.risk.refresh_scores(actor="api-treatment")
        create_audit_event(
            action="treatment.create",
            entity_type="risk_treatment",
            entity_id=treatment.id,
            metadata={"risk_id": treatment.risk_id},
            request=self.request,
        )

    def perform_update(self, serializer):
        treatment = serializer.save()
        treatment.risk.refresh_scores(actor="api-treatment")
        create_audit_event(
            action="treatment.update",
            entity_type="risk_treatment",
            entity_id=treatment.id,
            metadata={"risk_id": treatment.risk_id},
            request=self.request,
        )


class RiskReviewViewSet(viewsets.ModelViewSet):
    queryset = RiskReview.objects.select_related("risk", "reviewer").order_by("-reviewed_at")
    serializer_class = RiskReviewSerializer
    permission_classes = [IsRiskReviewerOrReadOnly]
    search_fields = ("decision", "comments")
    ordering_fields = ("reviewed_at", "next_review_date", "created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs

    def perform_create(self, serializer):
        review = serializer.save(reviewer=self.request.user)
        create_audit_event(
            action="review.create",
            entity_type="risk_review",
            entity_id=review.id,
            metadata={"risk_id": review.risk_id, "decision": review.decision},
            request=self.request,
        )


class RiskApprovalViewSet(viewsets.ModelViewSet):
    queryset = RiskApproval.objects.select_related("risk", "requested_by", "decided_by").order_by("-created_at")
    serializer_class = RiskApprovalSerializer
    permission_classes = [IsRiskReviewerOrReadOnly]
    search_fields = ("status", "comments")
    ordering_fields = ("created_at", "decided_at", "status")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs

    def perform_create(self, serializer):
        approval = serializer.save(requested_by=self.request.user)
        create_audit_event(
            action="approval.request",
            entity_type="risk_approval",
            entity_id=approval.id,
            metadata={"risk_id": approval.risk_id},
            request=self.request,
        )
        RiskNotification.objects.create(
            user=self.request.user,
            risk=approval.risk,
            notification_type=RiskNotification.TYPE_APPROVAL_REQUESTED,
            message=f"Approval requested for risk #{approval.risk_id}.",
        )

    def perform_update(self, serializer):
        approval = serializer.save(decided_by=self.request.user)
        create_audit_event(
            action="approval.update",
            entity_type="risk_approval",
            entity_id=approval.id,
            metadata={"risk_id": approval.risk_id, "status": approval.status},
            request=self.request,
        )
        RiskNotification.objects.create(
            user=self.request.user,
            risk=approval.risk,
            notification_type=RiskNotification.TYPE_APPROVAL_DECIDED,
            message=f"Approval {approval.status} for risk #{approval.risk_id}.",
        )


class RiskControlViewSet(viewsets.ModelViewSet):
    queryset = RiskControl.objects.order_by("name")
    serializer_class = RiskControlSerializer
    permission_classes = [IsRiskAdminOrReadOnly]
    search_fields = ("code", "name", "category")
    ordering_fields = ("code", "name", "created_at", "updated_at")


class RiskNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RiskNotificationSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ("message", "notification_type")
    ordering_fields = ("created_at",)

    def get_queryset(self):
        return RiskNotification.objects.filter(user=self.request.user).order_by("-created_at")


class RiskIssueViewSet(viewsets.ModelViewSet):
    queryset = RiskIssue.objects.select_related("risk").order_by("-created_at")
    serializer_class = RiskIssueSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("title", "status", "owner")
    ordering_fields = ("created_at", "updated_at", "due_date")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs

    def perform_create(self, serializer):
        issue = serializer.save()
        create_audit_event(
            action="issue.create",
            entity_type="risk_issue",
            entity_id=issue.id,
            metadata={"risk_id": issue.risk_id},
            request=self.request,
        )

    def perform_update(self, serializer):
        issue = serializer.save()
        create_audit_event(
            action="issue.update",
            entity_type="risk_issue",
            entity_id=issue.id,
            metadata={"risk_id": issue.risk_id},
            request=self.request,
        )


class RiskExceptionViewSet(viewsets.ModelViewSet):
    queryset = RiskException.objects.select_related("risk").order_by("-created_at")
    serializer_class = RiskExceptionSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("title", "status", "owner", "justification")
    ordering_fields = ("created_at", "updated_at", "start_date", "end_date")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs

    def perform_create(self, serializer):
        exception = serializer.save()
        create_audit_event(
            action="exception.create",
            entity_type="risk_exception",
            entity_id=exception.id,
            metadata={"risk_id": exception.risk_id},
            request=self.request,
        )

    def perform_update(self, serializer):
        exception = serializer.save()
        create_audit_event(
            action="exception.update",
            entity_type="risk_exception",
            entity_id=exception.id,
            metadata={"risk_id": exception.risk_id},
            request=self.request,
        )


class RiskReportScheduleViewSet(viewsets.ModelViewSet):
    queryset = RiskReportSchedule.objects.order_by("name")
    serializer_class = RiskReportScheduleSerializer
    permission_classes = [IsRiskAdminOrReadOnly]
    search_fields = ("name", "report_type", "frequency")
    ordering_fields = ("name", "created_at", "updated_at")

    def perform_create(self, serializer):
        schedule = serializer.save()
        create_audit_event(
            action="report.schedule.create",
            entity_type="risk_report_schedule",
            entity_id=schedule.id,
            request=self.request,
        )

    def perform_update(self, serializer):
        schedule = serializer.save()
        create_audit_event(
            action="report.schedule.update",
            entity_type="risk_report_schedule",
            entity_id=schedule.id,
            request=self.request,
        )


class RiskReportRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RiskReportRun.objects.select_related("schedule").order_by("-created_at")
    serializer_class = RiskReportRunSerializer
    permission_classes = [IsRiskAdminOrReadOnly]
    search_fields = ("status", "message")
    ordering_fields = ("created_at", "status")

class RiskScoringSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RiskScoringSnapshot.objects.select_related("risk", "scoring_method").order_by("-created_at")
    serializer_class = RiskScoringSnapshotSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ("created_at",)

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            qs = qs.filter(risk__primary_asset__in=accessible_assets(self.request.user))
        return qs


class RiskViewSet(viewsets.ModelViewSet):
    serializer_class = RiskSerializer
    search_fields = ("title", "description", "status")
    permission_classes = [IsRiskManagerOrReadOnly]
    ordering_fields = ("created_at", "updated_at", "due_date", "status", "inherent_score", "residual_score")

    def get_queryset(self):
        queryset = Risk.objects.select_related(
            "primary_asset",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method",
        ).prefetch_related("risk_assets", "reviews")

        if not can_view_all_assets(self.request.user):
            queryset = queryset.filter(primary_asset__in=accessible_assets(self.request.user))

        business_unit_code = self.request.query_params.get("business_unit_code")
        cost_center_code = self.request.query_params.get("cost_center_code")
        section_code = self.request.query_params.get("section_code")
        asset_type_code = self.request.query_params.get("asset_type_code")
        status_value = self.request.query_params.get("status")

        if business_unit_code:
            queryset = queryset.filter(business_unit__code=business_unit_code)
        if cost_center_code:
            queryset = queryset.filter(cost_center__code=cost_center_code)
        if section_code:
            queryset = queryset.filter(section__code=section_code)
        if asset_type_code:
            queryset = queryset.filter(asset_type__code=asset_type_code)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        risk = serializer.save()
        create_audit_event(
            action="risk.create",
            entity_type="risk",
            entity_id=risk.id,
            request=self.request,
        )

    def perform_update(self, serializer):
        risk = serializer.save()
        create_audit_event(
            action="risk.update",
            entity_type="risk",
            entity_id=risk.id,
            request=self.request,
        )

    def perform_destroy(self, instance):
        risk_id = instance.id
        instance.delete()
        create_audit_event(
            action="risk.delete",
            entity_type="risk",
            entity_id=risk_id,
            request=self.request,
        )

    @decorators.action(detail=True, methods=["post"], url_path="recalculate")
    def recalculate(self, request, pk=None):
        risk = self.get_object()
        risk.refresh_scores(actor=request.user.username if request.user.is_authenticated else "api")
        create_audit_event(
            action="risk.scoring.recalculate",
            entity_type="risk",
            entity_id=risk.id,
            request=request,
        )
        return response.Response(self.get_serializer(risk).data, status=status.HTTP_200_OK)


class AssessmentViewSet(viewsets.ModelViewSet):
    queryset = Assessment.objects.order_by("-created_at")
    serializer_class = AssessmentSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("title", "status", "owner")
    ordering_fields = ("created_at", "updated_at", "start_date", "end_date")


class VulnerabilityViewSet(viewsets.ModelViewSet):
    queryset = Vulnerability.objects.select_related("asset", "risk").order_by("-created_at")
    serializer_class = VulnerabilitySerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("title", "status", "severity", "owner")
    ordering_fields = ("created_at", "updated_at", "due_date", "severity", "status")

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_view_all_assets(self.request.user):
            asset_qs = accessible_assets(self.request.user)
            qs = qs.filter(Q(asset__in=asset_qs) | Q(risk__primary_asset__in=asset_qs))
        return qs


class GovernanceProgramViewSet(viewsets.ModelViewSet):
    queryset = GovernanceProgram.objects.order_by("name")
    serializer_class = GovernanceProgramSerializer
    permission_classes = [IsGovernanceManagerOrReadOnly]
    search_fields = ("name", "owner", "status")
    ordering_fields = ("name", "created_at", "updated_at", "review_date")


class ComplianceFrameworkViewSet(viewsets.ModelViewSet):
    queryset = ComplianceFramework.objects.order_by("name")
    serializer_class = ComplianceFrameworkSerializer
    permission_classes = [IsComplianceAuditorOrReadOnly]
    search_fields = ("name", "code", "owner", "status")
    ordering_fields = ("name", "code", "created_at", "updated_at")


class ComplianceRequirementViewSet(viewsets.ModelViewSet):
    queryset = ComplianceRequirement.objects.select_related("framework", "control").order_by("framework__name", "code")
    serializer_class = ComplianceRequirementSerializer
    permission_classes = [IsComplianceAuditorOrReadOnly]
    search_fields = ("code", "title", "status")
    ordering_fields = ("framework__name", "code", "created_at", "updated_at")


class ControlTestPlanViewSet(viewsets.ModelViewSet):
    queryset = ControlTestPlan.objects.select_related("control").order_by("-created_at")
    serializer_class = ControlTestPlanSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("owner", "frequency")
    ordering_fields = ("created_at", "updated_at", "next_due_date")


class ControlTestRunViewSet(viewsets.ModelViewSet):
    queryset = ControlTestRun.objects.select_related("plan", "plan__control").order_by("-tested_at")
    serializer_class = ControlTestRunSerializer
    permission_classes = [IsRiskManagerOrReadOnly]
    search_fields = ("tester", "result")
    ordering_fields = ("tested_at", "created_at", "updated_at", "effectiveness_score")
