from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from asset.models import Asset
from integration.models import IntegrationSyncRun
from integration.services import execute_eam_sync
from risk.models import (
    Risk,
    RiskApproval,
    RiskAsset,
    RiskCategory,
    RiskControl,
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
    RiskException,
    RiskIssue,
    RiskReportSchedule,
    RiskReview,
    RiskScoringMethod,
    RiskTreatment,
)
from risk.models import RiskApproval


def _resolve_default_scoring_method() -> RiskScoringMethod | None:
    return (
        RiskScoringMethod.objects.filter(is_active=True, is_default=True).order_by("id").first()
        or RiskScoringMethod.objects.filter(is_active=True).order_by("id").first()
    )


def _category_choices(category_type: str, extra_value: str | None = None) -> list[tuple[str, str]]:
    choices = [("", _("----"))]
    categories = RiskCategory.objects.filter(category_type=category_type).order_by("name")
    choices.extend([(item.name, item.name) for item in categories])
    if extra_value:
        existing = {value for value, _ in choices}
        if extra_value not in existing:
            choices.append((extra_value, extra_value))
    return choices


def _bound_or_initial_value(form: forms.Form, field_name: str) -> str | None:
    if form.is_bound:
        return form.data.get(form.add_prefix(field_name)) or None
    if form.initial.get(field_name):
        return form.initial.get(field_name)
    instance = getattr(form, "instance", None)
    if instance is not None:
        return getattr(instance, field_name, None) or None
    return None


def _apply_bootstrap(form: forms.Form) -> None:
    for field in form.fields.values():
        widget = field.widget
        if widget.is_hidden:
            continue
        classes = widget.attrs.get("class", "").split()
        if isinstance(widget, (forms.CheckboxInput,)):
            classes.append("form-check-input")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            classes.append("form-select")
        else:
            classes.append("form-control")
        widget.attrs["class"] = " ".join(sorted(set(classes)))


def _can_view_all_assets(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or user.groups.filter(name="risk_admin").exists()


def _accessible_assets_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
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


class RiskCreateForm(forms.ModelForm):
    category = forms.ChoiceField(required=False)
    additional_assets = forms.ModelMultipleChoiceField(
        queryset=Asset.objects.none(),
        required=False,
        help_text=_("Optional additional assets impacted by this risk."),
    )

    class Meta:
        model = Risk
        fields = [
            "title",
            "description",
            "category",
            "source",
            "primary_asset",
            "scoring_method",
            "additional_assets",
            "likelihood",
            "impact",
            "status",
            "owner",
            "due_date",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        asset_qs = _accessible_assets_for_user(self.user).order_by("asset_code")
        self.fields["primary_asset"].queryset = asset_qs
        self.fields["additional_assets"].queryset = asset_qs
        self.fields["scoring_method"].queryset = RiskScoringMethod.objects.filter(is_active=True).order_by("name")
        self.fields["primary_asset"].help_text = _(
            "Business unit, cost center, section, and asset type are inherited automatically from primary asset."
        )
        self.fields["category"].choices = _category_choices(
            RiskCategory.TYPE_RISK,
            _bound_or_initial_value(self, "category"),
        )

        default_method = _resolve_default_scoring_method()
        if default_method and not self.initial.get("scoring_method"):
            self.fields["scoring_method"].initial = default_method
        _apply_bootstrap(self)

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError(_("Title cannot be empty."))
        return title

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        owner = (cleaned_data.get("owner") or "").strip()
        due_date = cleaned_data.get("due_date")
        primary_asset = cleaned_data.get("primary_asset")
        additional_assets = cleaned_data.get("additional_assets")
        accessible_ids = set(
            _accessible_assets_for_user(self.user).values_list("id", flat=True)
        )

        if status == Risk.STATUS_IN_PROGRESS and not owner:
            self.add_error("owner", _("Owner is required when risk status is In Progress."))

        if due_date and due_date < timezone.localdate() and status != Risk.STATUS_CLOSED:
            self.add_error("due_date", _("Due date cannot be in the past unless risk is Closed."))

        if primary_asset:
            if primary_asset.id not in accessible_ids:
                self.add_error("primary_asset", _("You do not have access to the selected primary asset."))
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
                self.add_error(
                    "primary_asset",
                    _("Primary asset is missing required context metadata: ") + ", ".join(missing),
                )

        if additional_assets is not None:
            if any(asset.id not in accessible_ids for asset in additional_assets):
                self.add_error("additional_assets", _("You do not have access to one or more additional assets."))
            if primary_asset and primary_asset in additional_assets:
                self.add_error("additional_assets", _("Primary asset must not be duplicated in additional assets."))

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        risk = super().save(commit=False)
        if not risk.scoring_method:
            risk.scoring_method = _resolve_default_scoring_method()

        if commit:
            risk.save()

        linked_asset_ids = {risk.primary_asset_id}
        for asset in self.cleaned_data.get("additional_assets", []):
            linked_asset_ids.add(asset.id)

        RiskAsset.objects.filter(risk=risk).exclude(asset_id__in=linked_asset_ids).delete()

        for asset_id in linked_asset_ids:
            RiskAsset.objects.update_or_create(
                risk=risk,
                asset_id=asset_id,
                defaults={"is_primary": asset_id == risk.primary_asset_id},
            )

        risk.refresh_scores(actor="webui")
        return risk


class RiskUpdateForm(forms.ModelForm):
    category = forms.ChoiceField(required=False)
    class Meta:
        model = Risk
        fields = ["title", "description", "category", "source", "owner", "due_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = _category_choices(
            RiskCategory.TYPE_RISK,
            _bound_or_initial_value(self, "category"),
        )
        _apply_bootstrap(self)

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError(_("Title cannot be empty."))
        return title

    def clean(self):
        cleaned_data = super().clean()
        owner = (cleaned_data.get("owner") or "").strip()
        due_date = cleaned_data.get("due_date")

        status = self.instance.status if self.instance else Risk.STATUS_OPEN
        if status == Risk.STATUS_IN_PROGRESS and not owner:
            self.add_error("owner", _("Owner is required when risk status is In Progress."))

        if due_date and due_date < timezone.localdate() and status != Risk.STATUS_CLOSED:
            self.add_error("due_date", _("Due date cannot be in the past unless risk is Closed."))

        return cleaned_data


class RiskAssetLinkForm(forms.Form):
    asset_ids = forms.ModelMultipleChoiceField(
        queryset=Asset.objects.none(),
        required=False,
        help_text=_("Select additional assets linked to this risk."),
    )

    def __init__(self, *args, **kwargs):
        self.risk = kwargs.pop("risk")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        asset_qs = _accessible_assets_for_user(self.user).order_by("asset_code")
        self.fields["asset_ids"].queryset = asset_qs
        self.fields["asset_ids"].initial = self.risk.risk_assets.exclude(asset_id=self.risk.primary_asset_id).values_list(
            "asset_id",
            flat=True,
        )
        _apply_bootstrap(self)

    def clean(self):
        cleaned_data = super().clean()
        selected = cleaned_data.get("asset_ids") or []
        accessible_ids = set(
            _accessible_assets_for_user(self.user).values_list("id", flat=True)
        )
        if any(asset.id not in accessible_ids for asset in selected):
            self.add_error("asset_ids", _("You do not have access to one or more selected assets."))
        return cleaned_data

    @transaction.atomic
    def save(self):
        selected_ids = set(self.cleaned_data.get("asset_ids", []).values_list("id", flat=True))
        selected_ids.add(self.risk.primary_asset_id)

        RiskAsset.objects.filter(risk=self.risk).exclude(asset_id__in=selected_ids).delete()

        for asset_id in selected_ids:
            RiskAsset.objects.update_or_create(
                risk=self.risk,
                asset_id=asset_id,
                defaults={"is_primary": asset_id == self.risk.primary_asset_id},
            )

        RiskAsset.objects.filter(risk=self.risk).exclude(asset_id=self.risk.primary_asset_id).update(is_primary=False)


class RiskScoringApplyForm(forms.Form):
    risk_id = forms.IntegerField()
    scoring_method = forms.ModelChoiceField(queryset=RiskScoringMethod.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scoring_method"].queryset = RiskScoringMethod.objects.filter(is_active=True).order_by("name")
        _apply_bootstrap(self)

    def execute(self):
        risk = Risk.objects.get(id=self.cleaned_data["risk_id"])
        risk.scoring_method = self.cleaned_data["scoring_method"]
        risk.save(update_fields=["scoring_method", "updated_at"])
        risk.refresh_scores(actor="webui")
        return risk


class RiskBulkUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=[("", "----")] + Risk.STATUS_CHOICES, required=False)
    owner = forms.CharField(required=False)
    due_date = forms.DateField(required=False)
    clear_owner = forms.BooleanField(required=False)
    clear_due_date = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class RiskTreatmentCreateForm(forms.ModelForm):
    class Meta:
        model = RiskTreatment
        fields = [
            "risk",
            "control",
            "title",
            "strategy",
            "status",
            "owner",
            "due_date",
            "progress_percent",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["risk"].queryset = Risk.objects.order_by("-created_at")
        self.fields["control"].queryset = RiskControl.objects.filter(is_active=True).order_by("name")
        _apply_bootstrap(self)

    def save(self, commit=True):
        treatment = super().save(commit=commit)
        treatment.risk.refresh_scores(actor="webui-treatment")
        return treatment


class RiskReviewCreateForm(forms.ModelForm):
    class Meta:
        model = RiskReview
        fields = ["risk", "decision", "comments", "next_review_date"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["risk"].queryset = Risk.objects.order_by("-created_at")
        _apply_bootstrap(self)

    def save(self, commit=True):
        review = super().save(commit=False)
        review.reviewer = self.user
        if commit:
            review.save()
        return review


class RiskApprovalRequestForm(forms.ModelForm):
    class Meta:
        model = RiskApproval
        fields = ["comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class RiskApprovalDecisionForm(forms.ModelForm):
    class Meta:
        model = RiskApproval
        fields = ["status", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class RiskControlCreateForm(forms.ModelForm):
    category = forms.ChoiceField(required=False)

    class Meta:
        model = RiskControl
        fields = ["code", "name", "category", "description", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = _category_choices(
            RiskCategory.TYPE_CONTROL,
            _bound_or_initial_value(self, "category"),
        )
        _apply_bootstrap(self)


class RiskIssueCreateForm(forms.ModelForm):
    class Meta:
        model = RiskIssue
        fields = ["risk", "title", "description", "status", "owner", "due_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["risk"].queryset = Risk.objects.order_by("-created_at")
        _apply_bootstrap(self)


class RiskExceptionCreateForm(forms.ModelForm):
    class Meta:
        model = RiskException
        fields = ["risk", "title", "justification", "status", "owner", "approved_by", "start_date", "end_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["risk"].queryset = Risk.objects.order_by("-created_at")
        _apply_bootstrap(self)


class RiskReportScheduleForm(forms.ModelForm):
    class Meta:
        model = RiskReportSchedule
        fields = [
            "name",
            "report_type",
            "frequency",
            "day_of_week",
            "day_of_month",
            "hour",
            "minute",
            "recipients",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class RiskScoringMethodCreateForm(forms.ModelForm):
    class Meta:
        model = RiskScoringMethod
        fields = [
            "code",
            "name",
            "method_type",
            "likelihood_weight",
            "impact_weight",
            "treatment_effectiveness_weight",
            "is_default",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)

    def save(self, commit=True):
        method = super().save(commit=commit)
        if method.is_default:
            RiskScoringMethod.objects.exclude(id=method.id).update(is_default=False)
        return method


class EamSyncForm(forms.Form):
    direction = forms.ChoiceField(choices=IntegrationSyncRun.DIRECTION_CHOICES, initial=IntegrationSyncRun.DIRECTION_INBOUND)
    plugin_name = forms.ChoiceField(
        choices=[
            ("excel_bootstrap", "excel_bootstrap"),
            ("beam_web_service", "beam_web_service"),
        ],
        initial="excel_bootstrap",
    )
    plugin_version = forms.CharField(initial="v1")
    excel_file_path = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)

    def execute(self):
        context = {}
        excel_path = self.cleaned_data.get("excel_file_path")
        if excel_path:
            context["excel_file_path"] = excel_path

        return execute_eam_sync(
            direction=self.cleaned_data["direction"],
            plugin_name=self.cleaned_data["plugin_name"],
            plugin_version=self.cleaned_data["plugin_version"],
            context=context or None,
        )


class ThirdPartyVendorForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyVendor
        fields = ["name", "category", "contact_email", "owner", "status", "criticality", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class ThirdPartyRiskForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyRisk
        fields = [
            "vendor",
            "title",
            "description",
            "status",
            "owner",
            "due_date",
            "likelihood",
            "impact",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = ThirdPartyVendor.objects.order_by("name")
        _apply_bootstrap(self)


class PolicyStandardForm(forms.ModelForm):
    class Meta:
        model = PolicyStandard
        fields = [
            "name",
            "code",
            "category",
            "owner",
            "status",
            "effective_date",
            "review_date",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class PolicyControlMappingForm(forms.ModelForm):
    class Meta:
        model = PolicyControlMapping
        fields = ["policy", "control", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["policy"].queryset = PolicyStandard.objects.order_by("name")
        self.fields["control"].queryset = RiskControl.objects.order_by("name")
        _apply_bootstrap(self)


class PolicyRiskMappingForm(forms.ModelForm):
    class Meta:
        model = PolicyRiskMapping
        fields = ["policy", "risk", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["policy"].queryset = PolicyStandard.objects.order_by("name")
        self.fields["risk"].queryset = Risk.objects.order_by("-created_at")
        _apply_bootstrap(self)


class ControlTestPlanForm(forms.ModelForm):
    class Meta:
        model = ControlTestPlan
        fields = ["control", "owner", "frequency", "next_due_date", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["control"].queryset = RiskControl.objects.order_by("name")
        _apply_bootstrap(self)


class ControlTestRunForm(forms.ModelForm):
    class Meta:
        model = ControlTestRun
        fields = ["plan", "tested_at", "tester", "result", "effectiveness_score", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = ControlTestPlan.objects.select_related("control").order_by("control__name")
        _apply_bootstrap(self)


class GovernanceProgramForm(forms.ModelForm):
    class Meta:
        model = GovernanceProgram
        fields = ["name", "owner", "status", "objective", "review_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            "title",
            "assessment_type",
            "status",
            "owner",
            "start_date",
            "end_date",
            "scope",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class VulnerabilityForm(forms.ModelForm):
    class Meta:
        model = Vulnerability
        fields = [
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
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        asset_qs = _accessible_assets_for_user(self.user).order_by("asset_code")
        self.fields["asset"].queryset = asset_qs
        self.fields["risk"].queryset = Risk.objects.filter(primary_asset__in=asset_qs).order_by("-created_at")
        _apply_bootstrap(self)

    def clean(self):
        cleaned_data = super().clean()
        asset = cleaned_data.get("asset")
        risk = cleaned_data.get("risk")
        accessible_ids = set(
            _accessible_assets_for_user(self.user).values_list("id", flat=True)
        )
        if asset and asset.id not in accessible_ids:
            self.add_error("asset", _("You do not have access to the selected asset."))
        if risk and risk.primary_asset_id not in accessible_ids:
            self.add_error("risk", _("You do not have access to the selected risk."))
        return cleaned_data


class ComplianceFrameworkForm(forms.ModelForm):
    class Meta:
        model = ComplianceFramework
        fields = ["name", "code", "owner", "status", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class ComplianceRequirementForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequirement
        fields = ["framework", "code", "title", "description", "status", "control", "evidence", "last_reviewed"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["framework"].queryset = ComplianceFramework.objects.order_by("name")
        self.fields["control"].queryset = RiskControl.objects.order_by("name")
        _apply_bootstrap(self)
