from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from asset.models import Asset, AssetType, BusinessUnit, CostCenter, Section


class RiskScoringMethod(models.Model):
    METHOD_INHERENT = "inherent"
    METHOD_RESIDUAL = "residual"
    METHOD_CUSTOM = "custom"
    METHOD_TYPE_CHOICES = [
        (METHOD_INHERENT, "Inherent"),
        (METHOD_RESIDUAL, "Residual"),
        (METHOD_CUSTOM, "Custom"),
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
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=128, blank=True)
    owner = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    effective_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class PolicyControlMapping(models.Model):
    policy = models.ForeignKey(PolicyStandard, on_delete=models.CASCADE, related_name="control_mappings")
    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, related_name="policy_mappings")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy", "control"], name="uq_policy_control_mapping")
        ]

    def __str__(self) -> str:
        return f"{self.policy_id}:{self.control_id}"


class PolicyRiskMapping(models.Model):
    policy = models.ForeignKey(PolicyStandard, on_delete=models.CASCADE, related_name="risk_mappings")
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="policy_mappings")
    notes = models.CharField(max_length=255, blank=True)

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
        (FREQUENCY_QUARTERLY, "Quarterly"),
        (FREQUENCY_SEMI_ANNUAL, "Semi-Annual"),
        (FREQUENCY_ANNUAL, "Annual"),
    ]

    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, related_name="test_plans")
    owner = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=32, choices=FREQUENCY_CHOICES, default=FREQUENCY_ANNUAL)
    next_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

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
        (RESULT_PASS, "Pass"),
        (RESULT_FAIL, "Fail"),
        (RESULT_INCONCLUSIVE, "Inconclusive"),
    ]

    plan = models.ForeignKey(ControlTestPlan, on_delete=models.CASCADE, related_name="runs")
    tested_at = models.DateField()
    tester = models.CharField(max_length=255, blank=True)
    result = models.CharField(max_length=32, choices=RESULT_CHOICES)
    effectiveness_score = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True)

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
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
    ]

    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    objective = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)

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
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True)
    owner = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    description = models.TextField(blank=True)

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
        (STATUS_COMPLIANT, "Compliant"),
        (STATUS_PARTIAL, "Partially Compliant"),
        (STATUS_NONCOMPLIANT, "Non-Compliant"),
        (STATUS_NA, "Not Applicable"),
        (STATUS_UNKNOWN, "Unknown"),
    ]

    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE, related_name="requirements")
    code = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    control = models.ForeignKey(RiskControl, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_requirements")
    evidence = models.TextField(blank=True)
    last_reviewed = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["framework__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["framework", "code"], name="uq_compliance_requirement_code")
        ]

    def __str__(self) -> str:
        return f"{self.framework_id}:{self.code}"
