from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from asset.models import Asset, AssetType, BusinessUnit, CostCenter, Section


class RiskScoringMethod(models.Model):
    METHOD_INHERENT = "inherent"
    METHOD_RESIDUAL = "residual"
    METHOD_CUSTOM = "custom"
    METHOD_CVSS = "cvss"
    METHOD_DREAD = "dread"
    METHOD_CLASSIC = "classic"
    METHOD_OWASP = "owasp"
    METHOD_CIA = "cia"
    METHOD_TYPE_CHOICES = [
        (METHOD_INHERENT, "Inherent"),
        (METHOD_RESIDUAL, "Residual"),
        (METHOD_CUSTOM, "Custom"),
        (METHOD_CVSS, "CVSS"),
        (METHOD_DREAD, "DREAD"),
        (METHOD_CLASSIC, "Classic"),
        (METHOD_OWASP, "OWASP"),
        (METHOD_CIA, "CIA"),
    ]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    method_type = models.CharField(max_length=32, choices=METHOD_TYPE_CHOICES, default=METHOD_CUSTOM)
    likelihood_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    impact_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    treatment_effectiveness_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class RiskCategory(models.Model):
    TYPE_RISK = "risk"
    TYPE_CONTROL = "control"
    TYPE_CHOICES = [
        (TYPE_RISK, "Risk"),
        (TYPE_CONTROL, "Control"),
    ]

    category_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["category_type", "name"], name="uq_risk_category_type_name")
        ]

    def __str__(self) -> str:
        return f"{self.category_type}:{self.name}"


class RiskControl(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class RiskSource(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CriticalService(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
    ]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ServiceProcess(models.Model):
    CRITICALITY_LOW = "low"
    CRITICALITY_MEDIUM = "medium"
    CRITICALITY_HIGH = "high"
    CRITICALITY_CHOICES = [
        (CRITICALITY_LOW, "Low"),
        (CRITICALITY_MEDIUM, "Medium"),
        (CRITICALITY_HIGH, "High"),
    ]

    service = models.ForeignKey(CriticalService, on_delete=models.CASCADE, related_name="processes")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    criticality = models.CharField(max_length=16, choices=CRITICALITY_CHOICES, default=CRITICALITY_MEDIUM)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["service", "code"], name="uq_service_process_code")
        ]

    def __str__(self) -> str:
        return f"{self.service.code}:{self.code}"


class ServiceAssetMapping(models.Model):
    ROLE_PRIMARY = "primary"
    ROLE_SUPPORT = "support"
    ROLE_CHOICES = [
        (ROLE_PRIMARY, "Primary"),
        (ROLE_SUPPORT, "Support"),
    ]

    service = models.ForeignKey(CriticalService, on_delete=models.CASCADE, related_name="asset_mappings")
    process = models.ForeignKey(ServiceProcess, on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_mappings")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="service_mappings")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_SUPPORT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["service", "process", "asset"], name="uq_service_process_asset")
        ]

    def __str__(self) -> str:
        return f"{self.service.code}:{self.asset.asset_code}"


class Hazard(models.Model):
    TYPE_NATURAL = "natural"
    TYPE_INDUSTRIAL = "industrial"
    TYPE_UTILITY = "utility"
    TYPE_CYBER = "cyber"
    TYPE_CHOICES = [
        (TYPE_NATURAL, "Natural"),
        (TYPE_INDUSTRIAL, "Industrial"),
        (TYPE_UTILITY, "Utility"),
        (TYPE_CYBER, "Cyber"),
    ]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    hazard_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_UTILITY)
    description = models.TextField(blank=True)
    default_likelihood = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class HazardLink(models.Model):
    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="links")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="hazard_links")
    service = models.ForeignKey(CriticalService, on_delete=models.CASCADE, null=True, blank=True, related_name="hazard_links")
    impact_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(asset__isnull=False)
                    | models.Q(service__isnull=False)
                ),
                name="ck_hazard_link_target",
            )
        ]

    def __str__(self) -> str:
        target = self.asset.asset_code if self.asset_id else self.service.code
        return f"{self.hazard.code}:{target}"


class ServiceBIAProfile(models.Model):
    CRITICALITY_LIFE = "LIFE_CRITICAL"
    CRITICALITY_ENVIRONMENT = "ENVIRONMENT_CRITICAL"
    CRITICALITY_INFRASTRUCTURE = "INFRASTRUCTURE_CRITICAL"
    CRITICALITY_BUSINESS = "BUSINESS_CRITICAL"
    CRITICALITY_SUPPORT = "SUPPORT_SERVICE"
    CRITICALITY_CHOICES = [
        (CRITICALITY_LIFE, _("Life critical")),
        (CRITICALITY_ENVIRONMENT, _("Environment critical")),
        (CRITICALITY_INFRASTRUCTURE, _("Infrastructure critical")),
        (CRITICALITY_BUSINESS, _("Business critical")),
        (CRITICALITY_SUPPORT, _("Support service")),
    ]

    IMPACT_LEVEL_MINOR = "MINOR"
    IMPACT_LEVEL_DEGRADED = "DEGRADED"
    IMPACT_LEVEL_SEVERE = "SEVERE"
    IMPACT_LEVEL_CRITICAL = "CRITICAL"
    IMPACT_LEVEL_CATASTROPHIC = "CATASTROPHIC"
    IMPACT_LEVEL_CHOICES = [
        IMPACT_LEVEL_MINOR,
        IMPACT_LEVEL_DEGRADED,
        IMPACT_LEVEL_SEVERE,
        IMPACT_LEVEL_CRITICAL,
        IMPACT_LEVEL_CATASTROPHIC,
    ]

    service = models.OneToOneField(
        CriticalService,
        on_delete=models.CASCADE,
        related_name="bia_profile",
        verbose_name=_("Service"),
    )
    mao_hours = models.PositiveIntegerField(default=24, verbose_name=_("MAO/MTPD (h)"))
    rto_hours = models.PositiveIntegerField(default=8, verbose_name=_("RTO (h)"))
    rpo_hours = models.PositiveIntegerField(default=4, verbose_name=_("RPO (h)"))
    service_criticality = models.CharField(
        max_length=32,
        choices=CRITICALITY_CHOICES,
        default=CRITICALITY_SUPPORT,
        verbose_name=_("Service criticality"),
    )
    impact_operational = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Operational impact"),
    )
    impact_financial = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Financial impact"),
    )
    impact_environmental = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Environmental impact"),
    )
    impact_safety = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Safety impact"),
    )
    impact_legal = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Legal impact"),
    )
    impact_reputation = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Reputation impact"),
    )
    impact_escalation_curve = models.JSONField(null=True, blank=True, verbose_name=_("Impact escalation curve"))
    crisis_trigger_rules = models.JSONField(null=True, blank=True, verbose_name=_("Crisis trigger rules"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    @staticmethod
    def validate_impact_escalation_curve(curve, mtpd_minutes: int) -> None:
        if curve is None or curve == []:
            return
        if isinstance(curve, str):
            try:
                import json

                curve = json.loads(curve)
            except json.JSONDecodeError as exc:
                raise ValidationError(_("Invalid escalation curve JSON.")) from exc
        if not isinstance(curve, list):
            raise ValidationError(_("Escalation curve must be a list of steps."))

        seen_times = set()
        previous_time = None
        for idx, step in enumerate(curve, start=1):
            if not isinstance(step, dict):
                raise ValidationError(_("Escalation step %(step)s must be an object."), params={"step": idx})
            time_minutes = step.get("time_minutes")
            level = step.get("level")
            if time_minutes is None or level is None:
                raise ValidationError(_("Escalation step %(step)s must include time_minutes and level."), params={"step": idx})
            if not isinstance(time_minutes, int):
                raise ValidationError(_("Escalation step %(step)s time must be integer minutes."), params={"step": idx})
            if time_minutes <= 0:
                raise ValidationError(_("Escalation step %(step)s time must be greater than 0."), params={"step": idx})
            if time_minutes in seen_times:
                raise ValidationError(_("Escalation step times must be unique."))
            if previous_time is not None and time_minutes <= previous_time:
                raise ValidationError(_("Escalation step times must be strictly increasing."))
            if level not in ServiceBIAProfile.IMPACT_LEVEL_CHOICES:
                raise ValidationError(_("Escalation level must be one of: %(levels)s."), params={"levels": ", ".join(ServiceBIAProfile.IMPACT_LEVEL_CHOICES)})
            seen_times.add(time_minutes)
            previous_time = time_minutes

        if mtpd_minutes <= 0:
            raise ValidationError(_("MTPD must be greater than 0 to validate escalation curve."))
        if previous_time is not None and previous_time < mtpd_minutes:
            raise ValidationError(_("Last escalation step must be greater than or equal to MTPD."))

    @staticmethod
    def validate_crisis_trigger_rules(rules) -> None:
        if rules is None or rules == {}:
            return
        if isinstance(rules, str):
            try:
                import json

                rules = json.loads(rules)
            except json.JSONDecodeError as exc:
                raise ValidationError(_("Invalid crisis trigger rules JSON.")) from exc
        if not isinstance(rules, dict):
            raise ValidationError(_("Crisis trigger rules must be an object."))

        allowed_keys = {
            "mtpd_percentage_trigger",
            "impact_level_trigger",
            "environmental_severity_trigger",
            "safety_severity_trigger",
        }
        unknown_keys = set(rules.keys()) - allowed_keys
        if unknown_keys:
            raise ValidationError(_("Crisis trigger rules contain unsupported keys: %(keys)s."), params={"keys": ", ".join(sorted(unknown_keys))})

        if "mtpd_percentage_trigger" in rules:
            value = rules["mtpd_percentage_trigger"]
            if not isinstance(value, (int, float)):
                raise ValidationError(_("mtpd_percentage_trigger must be a number."))
            if value <= 0 or value > 1:
                raise ValidationError(_("mtpd_percentage_trigger must be between 0 and 1."))
        if "impact_level_trigger" in rules:
            value = rules["impact_level_trigger"]
            if not isinstance(value, str):
                raise ValidationError(_("impact_level_trigger must be a string."))
            if value not in ServiceBIAProfile.IMPACT_LEVEL_CHOICES:
                raise ValidationError(_("impact_level_trigger must be one of: %(levels)s."), params={"levels": ", ".join(ServiceBIAProfile.IMPACT_LEVEL_CHOICES)})
        if "environmental_severity_trigger" in rules:
            value = rules["environmental_severity_trigger"]
            if value is not None and not isinstance(value, int):
                raise ValidationError(_("environmental_severity_trigger must be an integer."))
            if value is not None and not (0 <= value <= 5):
                raise ValidationError(_("environmental_severity_trigger must be between 0 and 5."))
        if "safety_severity_trigger" in rules:
            value = rules["safety_severity_trigger"]
            if value is not None and not isinstance(value, int):
                raise ValidationError(_("safety_severity_trigger must be an integer."))
            if value is not None and not (0 <= value <= 5):
                raise ValidationError(_("safety_severity_trigger must be between 0 and 5."))

    def clean(self) -> None:
        super().clean()
        mtpd_minutes = int(self.mao_hours) * 60
        self.validate_impact_escalation_curve(self.impact_escalation_curve, mtpd_minutes)
        self.validate_crisis_trigger_rules(self.crisis_trigger_rules)

    @property
    def mtpd_minutes(self) -> int:
        return int(self.mao_hours) * 60

    @property
    def rto_minutes(self) -> int:
        return int(self.rto_hours) * 60

    @property
    def rpo_minutes(self) -> int:
        return int(self.rpo_hours) * 60

    def __str__(self) -> str:
        return f"{self.service.code} BIA"


class ImpactEscalationCurve(models.Model):
    CATEGORY_FINANCIAL = "financial"
    CATEGORY_OPERATIONAL = "operational"
    CATEGORY_LEGAL = "legal"
    CATEGORY_REPUTATIONAL = "reputational"
    CATEGORY_ENVIRONMENTAL = "environmental"
    CATEGORY_HUMAN_SAFETY = "human_safety"
    CATEGORY_CHOICES = [
        (CATEGORY_FINANCIAL, "Financial"),
        (CATEGORY_OPERATIONAL, "Operational"),
        (CATEGORY_LEGAL, "Legal"),
        (CATEGORY_REPUTATIONAL, "Reputational"),
        (CATEGORY_ENVIRONMENTAL, "Environmental"),
        (CATEGORY_HUMAN_SAFETY, "Human Safety"),
    ]

    bia_profile = models.ForeignKey(ServiceBIAProfile, on_delete=models.CASCADE, related_name="impact_curves")
    impact_category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    t1_hours = models.PositiveIntegerField(default=1)
    t1_label = models.CharField(max_length=255)
    t2_hours = models.PositiveIntegerField(default=4)
    t2_label = models.CharField(max_length=255)
    t3_hours = models.PositiveIntegerField(default=8)
    t3_label = models.CharField(max_length=255)
    t4_hours = models.PositiveIntegerField(default=24)
    t4_label = models.CharField(max_length=255)
    t5_hours = models.PositiveIntegerField(default=72)
    t5_label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bia_profile", "impact_category"], name="uq_bia_category")
        ]

    def __str__(self) -> str:
        return f"{self.bia_profile.service.code}:{self.impact_category}"


class Scenario(models.Model):
    name = models.CharField(max_length=255)
    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="scenarios")
    duration_hours = models.PositiveIntegerField(default=4)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class ContinuityStrategy(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RETIRED, _("Retired")),
    ]

    READINESS_PLANNED = "planned"
    READINESS_IN_PROGRESS = "in_progress"
    READINESS_READY = "ready"
    READINESS_TESTED = "tested"
    READINESS_CHOICES = [
        (READINESS_PLANNED, _("Planned")),
        (READINESS_IN_PROGRESS, _("In Progress")),
        (READINESS_READY, _("Ready")),
        (READINESS_TESTED, _("Tested")),
    ]

    TYPE_REDUNDANCY = "redundancy"
    TYPE_BACKUP = "backup"
    TYPE_MANUAL = "manual"
    TYPE_VENDOR = "vendor"
    TYPE_WORKAROUND = "workaround"
    TYPE_CHOICES = [
        (TYPE_REDUNDANCY, _("Redundancy")),
        (TYPE_BACKUP, _("Backup")),
        (TYPE_MANUAL, _("Manual")),
        (TYPE_VENDOR, _("Vendor")),
        (TYPE_WORKAROUND, _("Workaround")),
    ]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    strategy_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_BACKUP)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    readiness_level = models.CharField(max_length=32, choices=READINESS_CHOICES, default=READINESS_PLANNED)
    service = models.ForeignKey(CriticalService, on_delete=models.PROTECT, related_name="continuity_strategies")
    bia_profile = models.ForeignKey(ServiceBIAProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="continuity_strategies")
    scenario = models.ForeignKey(Scenario, on_delete=models.SET_NULL, null=True, blank=True, related_name="continuity_strategies")
    rto_target_hours = models.PositiveIntegerField(default=8)
    rpo_target_hours = models.PositiveIntegerField(default=4)
    owner = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Risk(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_CLOSED, "Closed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=128, blank=True)
    category = models.CharField(max_length=128, blank=True)

    likelihood = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    impact = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    confidentiality = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Confidentiality"),
    )
    integrity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Integrity"),
    )
    availability = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Availability"),
    )
    inherent_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    residual_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)

    owner = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)

    primary_asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="primary_risks")

    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="risks")
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name="risks")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="risks")
    asset_type = models.ForeignKey(AssetType, on_delete=models.SET_NULL, null=True, blank=True, related_name="risks")

    scoring_method = models.ForeignKey(
        RiskScoringMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risks",
    )
    critical_service = models.ForeignKey(
        CriticalService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risks",
    )
    dynamic_risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    STATUS_TRANSITIONS = {
        STATUS_OPEN: {STATUS_IN_PROGRESS, STATUS_CLOSED},
        STATUS_IN_PROGRESS: {STATUS_OPEN, STATUS_CLOSED},
        STATUS_CLOSED: {STATUS_OPEN},
    }

    def __str__(self) -> str:
        return self.title

    def sync_context_from_primary_asset(self) -> None:
        self.business_unit = self.primary_asset.business_unit
        self.cost_center = self.primary_asset.cost_center
        self.section = self.primary_asset.section
        self.asset_type = self.primary_asset.asset_type

    def calculate_scores(self) -> tuple[float, float]:
        method = self.scoring_method
        if not method:
            inherent = float(self.likelihood * self.impact)
            residual = inherent
            return inherent, residual

        inherent = float(self.likelihood) * float(method.likelihood_weight) * float(self.impact) * float(method.impact_weight)

        active_treatments = self.treatments.filter(status__in=[RiskTreatment.STATUS_PLANNED, RiskTreatment.STATUS_IN_PROGRESS])
        avg_progress = 0.0
        if active_treatments.exists():
            avg_progress = sum(t.progress_percent for t in active_treatments) / active_treatments.count()

        treatment_effect = (avg_progress / 100.0) * float(method.treatment_effectiveness_weight)
        residual = max(inherent * (1.0 - min(treatment_effect, 0.95)), 0.0)
        return inherent, residual

    def _calculate_cia_impact(self) -> int | None:
        if self.confidentiality is None or self.integrity is None or self.availability is None:
            return None
        avg = (self.confidentiality + self.integrity + self.availability) / 3.0
        score = int(round(avg))
        return min(max(score, 1), 5)

    def refresh_scores(self, actor: str = "system") -> None:
        inherent, residual = self.calculate_scores()
        self.inherent_score = round(inherent, 2)
        self.residual_score = round(residual, 2)
        self.save(update_fields=["inherent_score", "residual_score", "updated_at"])

        RiskScoringSnapshot.objects.create(
            risk=self,
            scoring_method=self.scoring_method,
            inherent_score=self.inherent_score,
            residual_score=self.residual_score,
            calculated_by=actor,
        )

    def save(self, *args, **kwargs):
        if self.primary_asset_id:
            self.sync_context_from_primary_asset()
        if self.scoring_method and self.scoring_method.method_type == RiskScoringMethod.METHOD_CIA:
            cia_impact = self._calculate_cia_impact()
            if cia_impact is not None:
                self.impact = cia_impact
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status: str) -> bool:
        if new_status == self.status:
            return True
        return new_status in self.STATUS_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: str) -> None:
        if not self.can_transition_to(new_status):
            raise ValidationError(f"Invalid transition from {self.status} to {new_status}.")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])


class RiskScoringSnapshot(models.Model):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="scoring_history")
    scoring_method = models.ForeignKey(RiskScoringMethod, on_delete=models.SET_NULL, null=True, blank=True, related_name="snapshots")
    inherent_score = models.DecimalField(max_digits=8, decimal_places=2)
    residual_score = models.DecimalField(max_digits=8, decimal_places=2)
    calculated_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RiskScoringDread(models.Model):
    risk = models.OneToOneField(Risk, on_delete=models.CASCADE, related_name="dread_inputs")
    damage = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    reproducibility = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    exploitability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    affected_users = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    discoverability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RiskScoringOwasp(models.Model):
    risk = models.OneToOneField(Risk, on_delete=models.CASCADE, related_name="owasp_inputs")
    skill_level = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    motive = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    opportunity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    size = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    ease_of_discovery = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    ease_of_exploit = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    awareness = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    intrusion_detection = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    loss_confidentiality = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    loss_integrity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    loss_availability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    loss_accountability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    financial_damage = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    reputation_damage = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    non_compliance = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    privacy_violation = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RiskScoringCvss(models.Model):
    risk = models.OneToOneField(Risk, on_delete=models.CASCADE, related_name="cvss_inputs")
    attack_vector = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    attack_complexity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    authentication = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    confidentiality_impact = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    integrity_impact = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    availability_impact = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    exploitability = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    remediation_level = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    report_confidence = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    collateral_damage_potential = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    target_distribution = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    confidentiality_requirement = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    integrity_requirement = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    availability_requirement = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RiskTreatment(models.Model):
    STRATEGY_MITIGATE = "mitigate"
    STRATEGY_ACCEPT = "accept"
    STRATEGY_TRANSFER = "transfer"
    STRATEGY_AVOID = "avoid"
    STRATEGY_CHOICES = [
        (STRATEGY_MITIGATE, "Mitigate"),
        (STRATEGY_ACCEPT, "Accept"),
        (STRATEGY_TRANSFER, "Transfer"),
        (STRATEGY_AVOID, "Avoid"),
    ]

    STATUS_PLANNED = "planned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="treatments")
    control = models.ForeignKey(RiskControl, on_delete=models.SET_NULL, null=True, blank=True, related_name="treatments")
    title = models.CharField(max_length=255)
    strategy = models.CharField(max_length=32, choices=STRATEGY_CHOICES, default=STRATEGY_MITIGATE)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    owner = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.risk_id} - {self.title}"


class RiskReview(models.Model):
    DECISION_ACCEPT = "accept"
    DECISION_REJECT = "reject"
    DECISION_REVISIT = "revisit"
    DECISION_CHOICES = [
        (DECISION_ACCEPT, "Accept"),
        (DECISION_REJECT, "Reject"),
        (DECISION_REVISIT, "Revisit"),
    ]

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="risk_reviews")
    decision = models.CharField(max_length=32, choices=DECISION_CHOICES, default=DECISION_REVISIT)
    comments = models.TextField(blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]


class RiskApproval(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="approvals")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="risk_approvals_requested",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="risk_approvals_decided",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RiskAsset(models.Model):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="risk_assets")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="asset_risks")
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["risk", "asset"], name="uq_risk_asset")]

    def __str__(self) -> str:
        return f"risk={self.risk_id}, asset={self.asset_id}"


class RiskNotification(models.Model):
    TYPE_APPROVAL_REQUESTED = "approval_requested"
    TYPE_APPROVAL_DECIDED = "approval_decided"
    TYPE_REPORT_READY = "report_ready"
    TYPE_CHOICES = [
        (TYPE_APPROVAL_REQUESTED, "Approval Requested"),
        (TYPE_APPROVAL_DECIDED, "Approval Decided"),
        (TYPE_REPORT_READY, "Report Ready"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_notifications")
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    notification_type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    message = models.CharField(max_length=255)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RiskIssue(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    ]

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="issues")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    owner = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class RiskException(models.Model):
    STATUS_OPEN = "open"
    STATUS_APPROVED = "approved"
    STATUS_EXPIRED = "expired"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REJECTED, "Rejected"),
    ]

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="exceptions")
    title = models.CharField(max_length=255)
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    owner = models.CharField(max_length=255, blank=True)
    approved_by = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class RiskReportSchedule(models.Model):
    FREQUENCY_DAILY = "daily"
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, "Daily"),
        (FREQUENCY_WEEKLY, "Weekly"),
        (FREQUENCY_MONTHLY, "Monthly"),
    ]

    REPORT_RISK_REGISTER = "risk_register"
    REPORT_TYPE_CHOICES = [
        (REPORT_RISK_REGISTER, "Risk Register"),
    ]

    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=64, choices=REPORT_TYPE_CHOICES, default=REPORT_RISK_REGISTER)
    frequency = models.CharField(max_length=32, choices=FREQUENCY_CHOICES, default=FREQUENCY_WEEKLY)
    day_of_week = models.PositiveSmallIntegerField(null=True, blank=True)  # 0=Mon .. 6=Sun
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..28/30/31
    hour = models.PositiveSmallIntegerField(default=9)
    minute = models.PositiveSmallIntegerField(default=0)
    recipients = models.TextField(blank=True, help_text="Comma-separated emails or usernames.")
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class RiskReportRun(models.Model):
    schedule = models.ForeignKey(RiskReportSchedule, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=32, default="success")
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ThirdPartyVendor(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    CRITICALITY_LOW = "low"
    CRITICALITY_MEDIUM = "medium"
    CRITICALITY_HIGH = "high"
    CRITICALITY_CHOICES = [
        (CRITICALITY_LOW, "Low"),
        (CRITICALITY_MEDIUM, "Medium"),
        (CRITICALITY_HIGH, "High"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=128, blank=True)
    contact_email = models.EmailField(blank=True)
    owner = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    criticality = models.CharField(max_length=32, choices=CRITICALITY_CHOICES, default=CRITICALITY_MEDIUM)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ThirdPartyRisk(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_CLOSED, "Closed"),
    ]

    vendor = models.ForeignKey(ThirdPartyVendor, on_delete=models.CASCADE, related_name="risks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    owner = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)

    likelihood = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    impact = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    inherent_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    residual_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        inherent = float(self.likelihood * self.impact)
        self.inherent_score = inherent
        self.residual_score = inherent
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class PolicyStandard(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RETIRED, _("Retired")),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    code = models.CharField(max_length=64, unique=True, verbose_name=_("Code"))
    category = models.CharField(max_length=128, blank=True, verbose_name=_("Category"))
    owner = models.CharField(max_length=255, blank=True, verbose_name=_("Owner"))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name=_("Status"))
    effective_date = models.DateField(null=True, blank=True, verbose_name=_("Effective date"))
    review_date = models.DateField(null=True, blank=True, verbose_name=_("Review date"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class PolicyControlMapping(models.Model):
    policy = models.ForeignKey(PolicyStandard, on_delete=models.CASCADE, related_name="control_mappings", verbose_name=_("Policy"))
    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, related_name="policy_mappings", verbose_name=_("Control"))
    notes = models.CharField(max_length=255, blank=True, verbose_name=_("Notes"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy", "control"], name="uq_policy_control_mapping")
        ]

    def __str__(self) -> str:
        return f"{self.policy_id}:{self.control_id}"


class PolicyRiskMapping(models.Model):
    policy = models.ForeignKey(PolicyStandard, on_delete=models.CASCADE, related_name="risk_mappings", verbose_name=_("Policy"))
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="policy_mappings", verbose_name=_("Risk"))
    notes = models.CharField(max_length=255, blank=True, verbose_name=_("Notes"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy", "risk"], name="uq_policy_risk_mapping")
        ]

    def __str__(self) -> str:
        return f"{self.policy_id}:{self.risk_id}"


class ControlTestPlan(models.Model):
    FREQUENCY_QUARTERLY = "quarterly"
    FREQUENCY_SEMI_ANNUAL = "semi_annual"
    FREQUENCY_ANNUAL = "annual"
    FREQUENCY_CHOICES = [
        (FREQUENCY_QUARTERLY, _("Quarterly")),
        (FREQUENCY_SEMI_ANNUAL, _("Semi-Annual")),
        (FREQUENCY_ANNUAL, _("Annual")),
    ]

    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, related_name="test_plans", verbose_name=_("Control"))
    owner = models.CharField(max_length=255, blank=True, verbose_name=_("Owner"))
    frequency = models.CharField(max_length=32, choices=FREQUENCY_CHOICES, default=FREQUENCY_ANNUAL, verbose_name=_("Frequency"))
    next_due_date = models.DateField(null=True, blank=True, verbose_name=_("Next due date"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.control_id}:{self.frequency}"


class ControlTestRun(models.Model):
    RESULT_PASS = "pass"
    RESULT_FAIL = "fail"
    RESULT_INCONCLUSIVE = "inconclusive"
    RESULT_CHOICES = [
        (RESULT_PASS, _("Pass")),
        (RESULT_FAIL, _("Fail")),
        (RESULT_INCONCLUSIVE, _("Inconclusive")),
    ]

    plan = models.ForeignKey(ControlTestPlan, on_delete=models.CASCADE, related_name="runs", verbose_name=_("Plan"))
    tested_at = models.DateField(verbose_name=_("Tested at"))
    tester = models.CharField(max_length=255, blank=True, verbose_name=_("Tester"))
    result = models.CharField(max_length=32, choices=RESULT_CHOICES, verbose_name=_("Result"))
    effectiveness_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Effectiveness score"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-tested_at"]

    def __str__(self) -> str:
        return f"{self.plan_id}:{self.tested_at}:{self.result}"


class GovernanceProgram(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RETIRED, _("Retired")),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    owner = models.CharField(max_length=255, blank=True, verbose_name=_("Owner"))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name=_("Status"))
    objective = models.TextField(blank=True, verbose_name=_("Objective"))
    review_date = models.DateField(null=True, blank=True, verbose_name=_("Review date"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Assessment(models.Model):
    TYPE_INTERNAL = "internal"
    TYPE_EXTERNAL = "external"
    TYPE_CHOICES = [
        (TYPE_INTERNAL, "Internal"),
        (TYPE_EXTERNAL, "External"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETE = "complete"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETE, "Complete"),
    ]

    title = models.CharField(max_length=255)
    assessment_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_INTERNAL)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    owner = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    scope = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Vulnerability(models.Model):
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    STATUS_OPEN = "open"
    STATUS_MITIGATED = "mitigated"
    STATUS_ACCEPTED = "accepted"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_MITIGATED, "Mitigated"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_CLOSED, "Closed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=32, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    owner = models.CharField(max_length=255, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="vulnerabilities")
    risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="vulnerabilities")
    discovered_at = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class ComplianceFramework(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RETIRED, _("Retired")),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    code = models.CharField(max_length=64, unique=True, verbose_name=_("Code"))
    owner = models.CharField(max_length=255, blank=True, verbose_name=_("Owner"))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name=_("Status"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ComplianceRequirement(models.Model):
    STATUS_COMPLIANT = "compliant"
    STATUS_PARTIAL = "partial"
    STATUS_NONCOMPLIANT = "noncompliant"
    STATUS_NA = "not_applicable"
    STATUS_UNKNOWN = "unknown"
    STATUS_CHOICES = [
        (STATUS_COMPLIANT, _("Compliant")),
        (STATUS_PARTIAL, _("Partially Compliant")),
        (STATUS_NONCOMPLIANT, _("Non-Compliant")),
        (STATUS_NA, _("Not Applicable")),
        (STATUS_UNKNOWN, _("Unknown")),
    ]

    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE, related_name="requirements", verbose_name=_("Framework"))
    code = models.CharField(max_length=64, verbose_name=_("Code"))
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UNKNOWN, verbose_name=_("Status"))
    control = models.ForeignKey(RiskControl, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_requirements", verbose_name=_("Control"))
    evidence = models.TextField(blank=True, verbose_name=_("Evidence"))
    last_reviewed = models.DateField(null=True, blank=True, verbose_name=_("Last reviewed"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["framework__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["framework", "code"], name="uq_compliance_requirement_code")
        ]

    def __str__(self) -> str:
        return f"{self.framework_id}:{self.code}"
