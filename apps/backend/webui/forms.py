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
    RiskSource,
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
    CriticalService,
    Hazard,
    HazardLink,
    Scenario,
    ContinuityStrategy,
    ServiceBIAProfile,
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


def _source_choices(extra_value: str | None = None) -> list[tuple[str, str]]:
    choices = [("", _("----"))]
    sources = RiskSource.objects.filter(is_active=True).order_by("name")
    choices.extend([(item.name, item.name) for item in sources])
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
    source = forms.ChoiceField(required=False)
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
            "confidentiality",
            "integrity",
            "availability",
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
        self.fields["source"].choices = _source_choices(
            _bound_or_initial_value(self, "source"),
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
    source = forms.ChoiceField(required=False)
    class Meta:
        model = Risk
        fields = [
            "title",
            "description",
            "category",
            "source",
            "owner",
            "due_date",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = _category_choices(
            RiskCategory.TYPE_RISK,
            _bound_or_initial_value(self, "category"),
        )
        self.fields["source"].choices = _source_choices(
            _bound_or_initial_value(self, "source"),
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
        help_text=_("Select assets to add to this risk."),
    )

    def __init__(self, *args, **kwargs):
        self.risk = kwargs.pop("risk")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        asset_qs = _accessible_assets_for_user(self.user).order_by("asset_code")
        linked_ids = list(self.risk.risk_assets.values_list("asset_id", flat=True))
        self.fields["asset_ids"].queryset = asset_qs.exclude(id__in=linked_ids)
        self.fields["asset_ids"].widget.attrs.setdefault("size", "12")
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
        for asset_id in selected_ids:
            RiskAsset.objects.update_or_create(
                risk=self.risk,
                asset_id=asset_id,
                defaults={"is_primary": asset_id == self.risk.primary_asset_id},
            )


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


class RiskScoringInputsForm(forms.Form):
    scoring_method = forms.ModelChoiceField(queryset=RiskScoringMethod.objects.none())
    likelihood = forms.IntegerField(min_value=1, max_value=5)
    impact = forms.IntegerField(min_value=1, max_value=5, required=False)
    confidentiality = forms.IntegerField(min_value=1, max_value=5, required=False)
    integrity = forms.IntegerField(min_value=1, max_value=5, required=False)
    availability = forms.IntegerField(min_value=1, max_value=5, required=False)
    dread_damage = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Damage"))
    dread_reproducibility = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Reproducibility"))
    dread_exploitability = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Exploitability"))
    dread_affected_users = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Affected Users"))
    dread_discoverability = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Discoverability"))
    owasp_skill_level = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Skill Level"))
    owasp_motive = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Motive"))
    owasp_opportunity = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Opportunity"))
    owasp_size = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Size"))
    owasp_ease_of_discovery = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Ease of Discovery"))
    owasp_ease_of_exploit = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Ease of Exploit"))
    owasp_awareness = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Awareness"))
    owasp_intrusion_detection = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Intrusion Detection"))
    owasp_loss_confidentiality = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Loss of Confidentiality"))
    owasp_loss_integrity = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Loss of Integrity"))
    owasp_loss_availability = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Loss of Availability"))
    owasp_loss_accountability = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Loss of Accountability"))
    owasp_financial_damage = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Financial Damage"))
    owasp_reputation_damage = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Reputation Damage"))
    owasp_non_compliance = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Non-Compliance"))
    owasp_privacy_violation = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Privacy Violation"))
    cvss_attack_vector = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Attack Vector"))
    cvss_attack_complexity = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Attack Complexity"))
    cvss_authentication = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Authentication"))
    cvss_confidentiality_impact = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Confidentiality Impact"))
    cvss_integrity_impact = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Integrity Impact"))
    cvss_availability_impact = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Availability Impact"))
    cvss_exploitability = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Exploitability"))
    cvss_remediation_level = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Remediation Level"))
    cvss_report_confidence = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Report Confidence"))
    cvss_collateral_damage_potential = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Collateral Damage Potential"))
    cvss_target_distribution = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Target Distribution"))
    cvss_confidentiality_requirement = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Confidentiality Requirement"))
    cvss_integrity_requirement = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Integrity Requirement"))
    cvss_availability_requirement = forms.IntegerField(min_value=1, max_value=5, required=False, label=_("Availability Requirement"))

    def __init__(self, *args, **kwargs):
        self.risk = kwargs.pop("risk", None)
        super().__init__(*args, **kwargs)
        self.fields["scoring_method"].queryset = RiskScoringMethod.objects.filter(is_active=True).order_by("name")
        if self.risk:
            self.fields["scoring_method"].initial = self.risk.scoring_method
            self.fields["likelihood"].initial = self.risk.likelihood
            self.fields["impact"].initial = self.risk.impact
            self.fields["confidentiality"].initial = self.risk.confidentiality
            self.fields["integrity"].initial = self.risk.integrity
            self.fields["availability"].initial = self.risk.availability
            if hasattr(self.risk, "dread_inputs"):
                dread = self.risk.dread_inputs
                self.fields["dread_damage"].initial = dread.damage
                self.fields["dread_reproducibility"].initial = dread.reproducibility
                self.fields["dread_exploitability"].initial = dread.exploitability
                self.fields["dread_affected_users"].initial = dread.affected_users
                self.fields["dread_discoverability"].initial = dread.discoverability
            if hasattr(self.risk, "owasp_inputs"):
                owasp = self.risk.owasp_inputs
                self.fields["owasp_skill_level"].initial = owasp.skill_level
                self.fields["owasp_motive"].initial = owasp.motive
                self.fields["owasp_opportunity"].initial = owasp.opportunity
                self.fields["owasp_size"].initial = owasp.size
                self.fields["owasp_ease_of_discovery"].initial = owasp.ease_of_discovery
                self.fields["owasp_ease_of_exploit"].initial = owasp.ease_of_exploit
                self.fields["owasp_awareness"].initial = owasp.awareness
                self.fields["owasp_intrusion_detection"].initial = owasp.intrusion_detection
                self.fields["owasp_loss_confidentiality"].initial = owasp.loss_confidentiality
                self.fields["owasp_loss_integrity"].initial = owasp.loss_integrity
                self.fields["owasp_loss_availability"].initial = owasp.loss_availability
                self.fields["owasp_loss_accountability"].initial = owasp.loss_accountability
                self.fields["owasp_financial_damage"].initial = owasp.financial_damage
                self.fields["owasp_reputation_damage"].initial = owasp.reputation_damage
                self.fields["owasp_non_compliance"].initial = owasp.non_compliance
                self.fields["owasp_privacy_violation"].initial = owasp.privacy_violation
            if hasattr(self.risk, "cvss_inputs"):
                cvss = self.risk.cvss_inputs
                self.fields["cvss_attack_vector"].initial = cvss.attack_vector
                self.fields["cvss_attack_complexity"].initial = cvss.attack_complexity
                self.fields["cvss_authentication"].initial = cvss.authentication
                self.fields["cvss_confidentiality_impact"].initial = cvss.confidentiality_impact
                self.fields["cvss_integrity_impact"].initial = cvss.integrity_impact
                self.fields["cvss_availability_impact"].initial = cvss.availability_impact
                self.fields["cvss_exploitability"].initial = cvss.exploitability
                self.fields["cvss_remediation_level"].initial = cvss.remediation_level
                self.fields["cvss_report_confidence"].initial = cvss.report_confidence
                self.fields["cvss_collateral_damage_potential"].initial = cvss.collateral_damage_potential
                self.fields["cvss_target_distribution"].initial = cvss.target_distribution
                self.fields["cvss_confidentiality_requirement"].initial = cvss.confidentiality_requirement
                self.fields["cvss_integrity_requirement"].initial = cvss.integrity_requirement
                self.fields["cvss_availability_requirement"].initial = cvss.availability_requirement
        _apply_bootstrap(self)

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("scoring_method")
        if not method:
            return cleaned
        if method.method_type == RiskScoringMethod.METHOD_CIA:
            missing = [name for name in ("confidentiality", "integrity", "availability") if not cleaned.get(name)]
            if missing:
                raise forms.ValidationError(
                    _("CIA scoring requires confidentiality, integrity, and availability scores.")
                )
        elif method.method_type == RiskScoringMethod.METHOD_DREAD:
            required = [
                "dread_damage",
                "dread_reproducibility",
                "dread_exploitability",
                "dread_affected_users",
                "dread_discoverability",
            ]
            if any(not cleaned.get(name) for name in required):
                raise forms.ValidationError(_("DREAD scoring requires all DREAD factors."))
        elif method.method_type == RiskScoringMethod.METHOD_OWASP:
            required = [
                "owasp_skill_level",
                "owasp_motive",
                "owasp_opportunity",
                "owasp_size",
                "owasp_ease_of_discovery",
                "owasp_ease_of_exploit",
                "owasp_awareness",
                "owasp_intrusion_detection",
                "owasp_loss_confidentiality",
                "owasp_loss_integrity",
                "owasp_loss_availability",
                "owasp_loss_accountability",
                "owasp_financial_damage",
                "owasp_reputation_damage",
                "owasp_non_compliance",
                "owasp_privacy_violation",
            ]
            if any(not cleaned.get(name) for name in required):
                raise forms.ValidationError(_("OWASP scoring requires all OWASP factors."))
        elif method.method_type == RiskScoringMethod.METHOD_CVSS:
            required = [
                "cvss_attack_vector",
                "cvss_attack_complexity",
                "cvss_authentication",
                "cvss_confidentiality_impact",
                "cvss_integrity_impact",
                "cvss_availability_impact",
                "cvss_exploitability",
                "cvss_remediation_level",
                "cvss_report_confidence",
                "cvss_collateral_damage_potential",
                "cvss_target_distribution",
                "cvss_confidentiality_requirement",
                "cvss_integrity_requirement",
                "cvss_availability_requirement",
            ]
            if any(not cleaned.get(name) for name in required):
                raise forms.ValidationError(_("CVSS scoring requires all CVSS factors."))
        else:
            if not cleaned.get("impact"):
                raise forms.ValidationError(_("Impact is required for the selected scoring method."))
        return cleaned


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


class CriticalServiceForm(forms.ModelForm):
    class Meta:
        model = CriticalService
        fields = ["code", "name", "description", "owner", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class ServiceBIAProfileForm(forms.ModelForm):
    impact_escalation_curve = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("JSON array of steps with time_minutes and level."),
    )
    crisis_trigger_rules = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=_("JSON object with crisis trigger thresholds."),
    )

    class Meta:
        model = ServiceBIAProfile
        fields = [
            "service",
            "mao_hours",
            "rto_hours",
            "rpo_hours",
            "service_criticality",
            "impact_operational",
            "impact_financial",
            "impact_environmental",
            "impact_safety",
            "impact_legal",
            "impact_reputation",
            "impact_escalation_curve",
            "crisis_trigger_rules",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = CriticalService.objects.order_by("name")
        _apply_bootstrap(self)


class HazardForm(forms.ModelForm):
    class Meta:
        model = Hazard
        fields = ["code", "name", "hazard_type", "description", "default_likelihood"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class HazardLinkForm(forms.ModelForm):
    class Meta:
        model = HazardLink
        fields = ["hazard", "asset", "service", "impact_multiplier"]

    def __init__(self, *args, **kwargs):
        hazard = kwargs.pop("hazard", None)
        super().__init__(*args, **kwargs)
        self.fields["hazard"].queryset = Hazard.objects.order_by("name")
        self.fields["asset"].queryset = Asset.objects.order_by("asset_code")
        self.fields["service"].queryset = CriticalService.objects.order_by("name")
        if hazard:
            self.fields["hazard"].initial = hazard
            self.fields["hazard"].widget = forms.HiddenInput()
        _apply_bootstrap(self)

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        service = cleaned.get("service")
        if not asset and not service:
            raise forms.ValidationError(_("Select an asset or service to link."))
        return cleaned


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ["name", "hazard", "duration_hours", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hazard"].queryset = Hazard.objects.order_by("name")
        _apply_bootstrap(self)


class ContinuityStrategyForm(forms.ModelForm):
    class Meta:
        model = ContinuityStrategy
        fields = [
            "code",
            "name",
            "strategy_type",
            "status",
            "readiness_level",
            "service",
            "bia_profile",
            "scenario",
            "rto_target_hours",
            "rpo_target_hours",
            "owner",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = CriticalService.objects.order_by("name")
        self.fields["bia_profile"].queryset = ServiceBIAProfile.objects.select_related("service").order_by("service__name")
        self.fields["scenario"].queryset = Scenario.objects.order_by("-created_at")
        _apply_bootstrap(self)

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
