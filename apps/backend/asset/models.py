from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class BusinessUnit(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class CostCenter(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="cost_centers")

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Section(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.PROTECT, related_name="sections")

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class AssetType(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class AssetStatus(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class AssetGroup(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class AssetAccessTeam(models.Model):
    name = models.CharField(max_length=255, unique=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="asset_access_teams", blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Asset(models.Model):
    asset_code = models.CharField(max_length=128, unique=True)
    asset_name = models.CharField(max_length=255)
    parent_asset = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_assets",
    )
    asset_type = models.ForeignKey(AssetType, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    asset_status = models.ForeignKey(AssetStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    asset_group = models.ForeignKey(AssetGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    access_teams = models.ManyToManyField(AssetAccessTeam, related_name="assets", blank=True)
    access_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="asset_access", blank=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")

    brand = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=128, blank=True)
    serial_number = models.CharField(max_length=128, blank=True)
    is_mobile_equipment = models.BooleanField(default=False)
    default_work_type = models.CharField(max_length=128, blank=True)
    integration_source = models.CharField(max_length=64, default="eam")
    geo_zone = models.CharField(max_length=128, blank=True)
    seismic_risk_coefficient = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    infrastructure_criticality = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_code"]

    def __str__(self) -> str:
        return f"{self.asset_code} - {self.asset_name}"


class AssetDependency(models.Model):
    DEPENDENCY_TYPE_HARD = "hard"
    DEPENDENCY_TYPE_SOFT = "soft"
    DEPENDENCY_TYPE_LOGICAL = "logical"
    DEPENDENCY_TYPE_CHOICES = [
        (DEPENDENCY_TYPE_HARD, "Hard"),
        (DEPENDENCY_TYPE_SOFT, "Soft"),
        (DEPENDENCY_TYPE_LOGICAL, "Logical"),
    ]

    source_asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="outbound_dependencies")
    target_asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="inbound_dependencies")
    dependency_type = models.CharField(max_length=32, choices=DEPENDENCY_TYPE_CHOICES, default=DEPENDENCY_TYPE_HARD)
    strength = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_asset", "target_asset", "dependency_type"],
                name="uq_asset_dependency_edge",
            )
        ]

    def clean(self) -> None:
        if self.source_asset_id and self.source_asset_id == self.target_asset_id:
            raise ValidationError("Source and target assets must be different")

    def __str__(self) -> str:
        return f"{self.source_asset.asset_code} -> {self.target_asset.asset_code} ({self.dependency_type})"
