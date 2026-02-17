from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    CriticalService,
    Hazard,
    HazardLink,
    ImpactEscalationCurve,
    Risk,
    RiskAsset,
    RiskCategory,
    RiskReview,
    RiskScoringMethod,
    RiskScoringSnapshot,
    RiskSource,
    RiskTreatment,
    Scenario,
    ServiceAssetMapping,
    ServiceBIAProfile,
    ServiceProcess,
)


class RiskAssetInline(admin.TabularInline):
    model = RiskAsset
    extra = 1


class RiskTreatmentInline(admin.TabularInline):
    model = RiskTreatment
    extra = 0


class RiskReviewInline(admin.TabularInline):
    model = RiskReview
    extra = 0


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "status",
        "primary_asset",
        "critical_service",
        "business_unit",
        "cost_center",
        "section",
        "asset_type",
        "scoring_method",
        "inherent_score",
        "residual_score",
        "dynamic_risk_score",
        "created_at",
    )
    list_filter = (
        "status",
        "business_unit",
        "cost_center",
        "section",
        "asset_type",
        "scoring_method",
        "critical_service",
    )
    search_fields = ("title", "description", "owner")
    inlines = [RiskAssetInline, RiskTreatmentInline, RiskReviewInline]


@admin.register(RiskAsset)
class RiskAssetAdmin(admin.ModelAdmin):
    list_display = ("risk", "asset", "is_primary")


@admin.register(RiskScoringMethod)
class RiskScoringMethodAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "method_type",
        "likelihood_weight",
        "impact_weight",
        "treatment_effectiveness_weight",
        "is_default",
        "is_active",
    )
    list_filter = ("method_type", "is_default", "is_active")


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category_type", "description", "updated_at")
    list_filter = ("category_type",)
    search_fields = ("name", "description")


@admin.register(RiskSource)
class RiskSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "description", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(RiskScoringSnapshot)
class RiskScoringSnapshotAdmin(admin.ModelAdmin):
    list_display = ("risk", "scoring_method", "inherent_score", "residual_score", "calculated_by", "created_at")
    list_filter = ("scoring_method",)


@admin.register(RiskTreatment)
class RiskTreatmentAdmin(admin.ModelAdmin):
    list_display = ("risk", "title", "strategy", "status", "owner", "due_date", "progress_percent")
    list_filter = ("strategy", "status")


@admin.register(RiskReview)
class RiskReviewAdmin(admin.ModelAdmin):
    list_display = ("risk", "reviewer", "decision", "next_review_date", "reviewed_at")
    list_filter = ("decision",)


@admin.register(CriticalService)
class CriticalServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "status", "owner", "updated_at")
    list_filter = ("status",)
    search_fields = ("code", "name", "owner", "description")


@admin.register(ServiceProcess)
class ServiceProcessAdmin(admin.ModelAdmin):
    list_display = ("service", "code", "name", "criticality", "updated_at")
    list_filter = ("criticality", "service")
    search_fields = ("code", "name", "description")


@admin.register(ServiceAssetMapping)
class ServiceAssetMappingAdmin(admin.ModelAdmin):
    list_display = ("service", "process", "asset", "role")
    list_filter = ("service", "role")
    search_fields = ("service__name", "asset__asset_code", "asset__asset_name")


@admin.register(ServiceBIAProfile)
class ServiceBIAProfileAdmin(admin.ModelAdmin):
    list_display = ("service", "service_criticality", "mao_hours", "rto_hours", "rpo_hours")
    search_fields = ("service__name", "service__code")
    fieldsets = (
        (None, {"fields": ("service", "service_criticality", "notes")}),
        (_("Time Thresholds"), {"fields": ("mao_hours", "rto_hours", "rpo_hours")}),
        (_("Impact Dimensions"), {"fields": ("impact_operational", "impact_financial", "impact_environmental", "impact_safety", "impact_legal", "impact_reputation")}),
        (_("Escalation & Crisis Rules"), {"fields": ("impact_escalation_curve", "crisis_trigger_rules")}),
    )


@admin.register(ImpactEscalationCurve)
class ImpactEscalationCurveAdmin(admin.ModelAdmin):
    list_display = ("bia_profile", "impact_category", "t1_hours", "t2_hours", "t3_hours", "t4_hours", "t5_hours")
    list_filter = ("impact_category",)
    search_fields = ("bia_profile__service__name", "impact_category")


@admin.register(Hazard)
class HazardAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "hazard_type", "default_likelihood", "updated_at")
    list_filter = ("hazard_type",)
    search_fields = ("code", "name", "description")


@admin.register(HazardLink)
class HazardLinkAdmin(admin.ModelAdmin):
    list_display = ("hazard", "asset", "service", "impact_multiplier", "created_at")
    list_filter = ("hazard",)
    search_fields = ("hazard__name", "asset__asset_code", "service__name")


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "hazard", "duration_hours", "created_at")
    list_filter = ("hazard",)
    search_fields = ("name", "notes")
