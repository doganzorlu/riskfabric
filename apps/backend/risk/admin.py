from django.contrib import admin

from .models import Risk, RiskAsset, RiskReview, RiskScoringMethod, RiskScoringSnapshot, RiskTreatment


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
        "business_unit",
        "cost_center",
        "section",
        "asset_type",
        "scoring_method",
        "inherent_score",
        "residual_score",
        "created_at",
    )
    list_filter = ("status", "business_unit", "cost_center", "section", "asset_type", "scoring_method")
    search_fields = ("title", "description")
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
