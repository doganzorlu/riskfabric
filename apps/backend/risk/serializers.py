from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from asset.access import accessible_assets
from asset.models import Asset

from .models import (
    Assessment,
    ComplianceFramework,
    ComplianceRequirement,
    ControlTestPlan,
    ControlTestRun,
    GovernanceProgram,
    Risk,
    RiskApproval,
    RiskAsset,
    RiskControl,
    RiskNotification,
    RiskIssue,
    RiskException,
    RiskReportSchedule,
    RiskReportRun,
    RiskReview,
    RiskScoringMethod,
    RiskScoringSnapshot,
    RiskTreatment,
    Vulnerability,
)


class RiskScoringMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScoringMethod
        fields = [
            "id",
            "code",
            "name",
            "method_type",
            "likelihood_weight",
            "impact_weight",
            "treatment_effectiveness_weight",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]


class RiskScoringSnapshotSerializer(serializers.ModelSerializer):
    scoring_method_code = serializers.CharField(source="scoring_method.code", read_only=True)

    class Meta:
        model = RiskScoringSnapshot
        fields = [
            "id",
            "risk",
            "scoring_method",
            "scoring_method_code",
            "inherent_score",
            "residual_score",
            "calculated_by",
            "created_at",
        ]


class RiskTreatmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskTreatment
        fields = [
            "id",
            "risk",
            "control",
            "title",
            "strategy",
            "status",
            "owner",
            "due_date",
            "progress_percent",
            "notes",
            "created_at",
            "updated_at",
        ]


class RiskReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True)

    class Meta:
        model = RiskReview
        fields = [
            "id",
            "risk",
            "reviewer",
            "reviewer_username",
            "decision",
            "comments",
            "next_review_date",
            "reviewed_at",
        ]
        read_only_fields = ["reviewed_at", "reviewer_username", "reviewer"]


class RiskApprovalSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    decided_by_username = serializers.CharField(source="decided_by.username", read_only=True)

    class Meta:
        model = RiskApproval
        fields = [
            "id",
            "risk",
            "requested_by",
            "requested_by_username",
            "decided_by",
            "decided_by_username",
            "status",
            "comments",
            "decided_at",
            "created_at",
        ]
        read_only_fields = ["requested_by", "requested_by_username", "decided_by", "decided_by_username", "decided_at", "created_at"]


class RiskControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskControl
        fields = [
            "id",
            "code",
            "name",
            "category",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]


class RiskNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskNotification
        fields = [
            "id",
            "user",
            "risk",
            "notification_type",
            "message",
            "read_at",
            "created_at",
        ]


class RiskIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskIssue
        fields = [
            "id",
            "risk",
            "title",
            "description",
            "status",
            "owner",
            "due_date",
            "created_at",
            "updated_at",
        ]


class RiskExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskException
        fields = [
            "id",
            "risk",
            "title",
            "justification",
            "status",
            "owner",
            "approved_by",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]


class RiskReportScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskReportSchedule
        fields = [
            "id",
            "name",
            "report_type",
            "frequency",
            "day_of_week",
            "day_of_month",
            "hour",
            "minute",
            "recipients",
            "is_active",
            "last_run_at",
            "created_at",
            "updated_at",
        ]


class RiskReportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskReportRun
        fields = ["id", "schedule", "status", "message", "created_at"]


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = [
            "id",
            "title",
            "assessment_type",
            "status",
            "owner",
            "start_date",
            "end_date",
            "scope",
            "notes",
            "created_at",
            "updated_at",
        ]


class VulnerabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vulnerability
        fields = [
            "id",
            "title",
            "description",
            "severity",
            "status",
            "owner",
            "asset",
            "risk",
            "discovered_at",
            "due_date",
            "notes",
            "created_at",
            "updated_at",
        ]


class GovernanceProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovernanceProgram
        fields = [
            "id",
            "name",
            "owner",
            "status",
            "objective",
            "review_date",
            "created_at",
            "updated_at",
        ]


class ComplianceFrameworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceFramework
        fields = [
            "id",
            "name",
            "code",
            "owner",
            "status",
            "description",
            "created_at",
            "updated_at",
        ]


class ComplianceRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRequirement
        fields = [
            "id",
            "framework",
            "code",
            "title",
            "description",
            "status",
            "control",
            "evidence",
            "last_reviewed",
            "created_at",
            "updated_at",
        ]


class ControlTestPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlTestPlan
        fields = [
            "id",
            "control",
            "owner",
            "frequency",
            "next_due_date",
            "notes",
            "created_at",
            "updated_at",
        ]


class ControlTestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlTestRun
        fields = [
            "id",
            "plan",
            "tested_at",
            "tester",
            "result",
            "effectiveness_score",
            "notes",
            "created_at",
            "updated_at",
        ]


class RiskSerializer(serializers.ModelSerializer):
    asset_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=False,
        help_text="Optional additional assets linked to risk. primary_asset is always included.",
    )
    linked_asset_ids = serializers.SerializerMethodField(read_only=True)
    primary_asset_code = serializers.CharField(source="primary_asset.asset_code", read_only=True)
    scoring_method_code = serializers.CharField(source="scoring_method.code", read_only=True)
    latest_review = serializers.SerializerMethodField(read_only=True)
    context = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Risk
        fields = [
            "id",
            "title",
            "description",
            "source",
            "category",
            "likelihood",
            "impact",
            "inherent_score",
            "residual_score",
            "status",
            "owner",
            "due_date",
            "primary_asset",
            "primary_asset_code",
            "scoring_method",
            "scoring_method_code",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "asset_ids",
            "linked_asset_ids",
            "latest_review",
            "context",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "linked_asset_ids",
            "primary_asset_code",
            "business_unit",
            "cost_center",
            "section",
            "asset_type",
            "scoring_method_code",
            "latest_review",
            "context",
        ]

    def get_linked_asset_ids(self, obj: Risk) -> list[int]:
        return list(obj.risk_assets.values_list("asset_id", flat=True))

    def get_latest_review(self, obj: Risk) -> dict | None:
        review = obj.reviews.first()
        if not review:
            return None
        return {
            "id": review.id,
            "decision": review.decision,
            "reviewer": review.reviewer.username,
            "reviewed_at": review.reviewed_at,
            "next_review_date": review.next_review_date,
        }

    def get_context(self, obj: Risk) -> dict:
        return {
            "business_unit": {
                "id": obj.business_unit_id,
                "code": getattr(obj.business_unit, "code", None),
                "name": getattr(obj.business_unit, "name", None),
            },
            "cost_center": {
                "id": obj.cost_center_id,
                "code": getattr(obj.cost_center, "code", None),
                "name": getattr(obj.cost_center, "name", None),
            },
            "section": {
                "id": obj.section_id,
                "code": getattr(obj.section, "code", None),
                "name": getattr(obj.section, "name", None),
            },
            "asset_type": {
                "id": obj.asset_type_id,
                "code": getattr(obj.asset_type, "code", None),
                "name": getattr(obj.asset_type, "name", None),
            },
        }

    def validate_title(self, value: str) -> str:
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be empty.")
        return title

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)

        status = attrs.get("status", self.instance.status if self.instance else Risk.STATUS_OPEN)
        owner = (attrs.get("owner", self.instance.owner if self.instance else "") or "").strip()
        due_date = attrs.get("due_date", self.instance.due_date if self.instance else None)
        primary_asset = attrs.get("primary_asset", self.instance.primary_asset if self.instance else None)
        request = self.context.get("request")
        accessible_ids = set(accessible_assets(getattr(request, "user", None)).values_list("id", flat=True))

        if status == Risk.STATUS_IN_PROGRESS and not owner:
            raise serializers.ValidationError({"owner": "Owner is required when risk status is In Progress."})

        if due_date and due_date < timezone.localdate() and status != Risk.STATUS_CLOSED:
            raise serializers.ValidationError({"due_date": "Due date cannot be in the past unless risk is Closed."})

        if primary_asset:
            if primary_asset.id not in accessible_ids:
                raise serializers.ValidationError({"primary_asset": "You do not have access to the selected primary asset."})
            missing = []
            if not primary_asset.business_unit_id:
                missing.append("business_unit")
            if not primary_asset.cost_center_id:
                missing.append("cost_center")
            if not primary_asset.section_id:
                missing.append("section")
            if not primary_asset.asset_type_id:
                missing.append("asset_type")
            if missing:
                raise serializers.ValidationError(
                    {"primary_asset": "Primary asset is missing required context metadata: " + ", ".join(missing)}
                )

        return attrs

    def validate_asset_ids(self, value: list[int]) -> list[int]:
        unique_ids = sorted(set(value))
        request = self.context.get("request")
        accessible_ids = set(accessible_assets(getattr(request, "user", None)).values_list("id", flat=True))
        existing_count = Asset.objects.filter(id__in=unique_ids).count()
        if existing_count != len(unique_ids):
            raise serializers.ValidationError("One or more asset_ids are invalid.")
        if any(asset_id not in accessible_ids for asset_id in unique_ids):
            raise serializers.ValidationError("You do not have access to one or more asset_ids.")
        return unique_ids

    def _resolve_default_scoring_method(self) -> RiskScoringMethod | None:
        return (
            RiskScoringMethod.objects.filter(is_active=True, is_default=True).order_by("id").first()
            or RiskScoringMethod.objects.filter(is_active=True).order_by("id").first()
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> Risk:
        asset_ids = validated_data.pop("asset_ids", [])
        if not validated_data.get("scoring_method"):
            validated_data["scoring_method"] = self._resolve_default_scoring_method()
        risk = super().create(validated_data)
        self._sync_asset_links(risk, asset_ids)
        risk.refresh_scores(actor="api")
        return risk

    @transaction.atomic
    def update(self, instance: Risk, validated_data: dict) -> Risk:
        asset_ids = validated_data.pop("asset_ids", None)
        if "scoring_method" in validated_data and not validated_data.get("scoring_method"):
            validated_data["scoring_method"] = self._resolve_default_scoring_method()
        risk = super().update(instance, validated_data)
        if asset_ids is not None:
            self._sync_asset_links(risk, asset_ids)
        risk.refresh_scores(actor="api")
        return risk

    def _sync_asset_links(self, risk: Risk, asset_ids: list[int]) -> None:
        merged_asset_ids = set(asset_ids)
        merged_asset_ids.add(risk.primary_asset_id)

        RiskAsset.objects.filter(risk=risk).exclude(asset_id__in=merged_asset_ids).delete()

        for asset_id in merged_asset_ids:
            RiskAsset.objects.update_or_create(
                risk=risk,
                asset_id=asset_id,
                defaults={"is_primary": asset_id == risk.primary_asset_id},
            )

        RiskAsset.objects.filter(risk=risk).exclude(asset_id=risk.primary_asset_id).update(is_primary=False)
