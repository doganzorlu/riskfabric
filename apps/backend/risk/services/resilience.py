from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.utils import timezone

from asset.models import AssetDependency

from risk.models import (
    Hazard,
    RiskIssue,
    RiskAsset,
    Scenario,
    ServiceAssetMapping,
    ServiceBIAProfile,
)


def propagate_asset_failures(asset_ids: Iterable[int]) -> Set[int]:
    """Propagate failures using the asset dependency graph (legacy loop-based)."""
    failed: Set[int] = set(asset_ids)
    frontier: Set[int] = set(asset_ids)

    while frontier:
        dependents = set(
            AssetDependency.objects.filter(source_asset_id__in=frontier)
            .values_list("target_asset_id", flat=True)
        )
        next_assets = dependents - failed
        if not next_assets:
            break
        failed.update(next_assets)
        frontier = next_assets

    return failed


def _impact_for_duration(curve, duration_hours: int) -> Dict[str, Any]:
    """Resolve legacy escalation curve labels for a given duration in hours."""
    thresholds = [
        (curve.t1_hours, curve.t1_label, 1),
        (curve.t2_hours, curve.t2_label, 2),
        (curve.t3_hours, curve.t3_label, 3),
        (curve.t4_hours, curve.t4_label, 4),
        (curve.t5_hours, curve.t5_label, 5),
    ]
    thresholds.sort(key=lambda item: item[0])

    selected = thresholds[-1]
    for hours, label, level in thresholds:
        if duration_hours <= hours:
            selected = (hours, label, level)
            break

    _, label, level = selected
    return {"label": label, "level": level}


def build_bia_impact(bia_profile: Optional[ServiceBIAProfile], duration_hours: int) -> Dict[str, Any]:
    """Build legacy BIA impact dictionary using category-based curves."""
    if not bia_profile:
        return {}

    impact: Dict[str, Any] = {}
    for curve in bia_profile.impact_curves.all():
        impact[curve.impact_category] = _impact_for_duration(curve, duration_hours)

    return impact


def simulate_scenario(scenario: Scenario, duration_hours: Optional[int] = None) -> Dict[str, Any]:
    """Simulate a hazard scenario impact using legacy BIA curves."""
    duration = duration_hours if duration_hours is not None else scenario.duration_hours
    hazard: Hazard = scenario.hazard

    links = hazard.links.select_related("asset", "service")
    asset_ids = {link.asset_id for link in links if link.asset_id}
    service_ids = {link.service_id for link in links if link.service_id}

    if service_ids:
        asset_ids.update(
            ServiceAssetMapping.objects.filter(service_id__in=service_ids)
            .values_list("asset_id", flat=True)
        )

    failed_asset_ids = propagate_asset_failures(asset_ids)

    service_to_assets: Dict[Any, Set[int]] = defaultdict(set)
    mappings = ServiceAssetMapping.objects.filter(asset_id__in=failed_asset_ids).select_related("service")
    for mapping in mappings:
        service_to_assets[mapping.service].add(mapping.asset_id)

    services: List[Dict[str, Any]] = []
    for service, assets in service_to_assets.items():
        bia_profile = getattr(service, "bia_profile", None)
        impact = build_bia_impact(bia_profile, duration)
        services.append(
            {
                "service": service,
                "impact": impact,
                "failed_asset_ids": sorted(assets),
            }
        )

    return {
        "scenario": scenario,
        "hazard": hazard,
        "duration_hours": duration,
        "failed_asset_ids": sorted(failed_asset_ids),
        "services": services,
    }


IMPACT_LEVEL_SEVERITY: Dict[str, int] = {
    ServiceBIAProfile.IMPACT_LEVEL_MINOR: 1,
    ServiceBIAProfile.IMPACT_LEVEL_DEGRADED: 2,
    ServiceBIAProfile.IMPACT_LEVEL_SEVERE: 3,
    ServiceBIAProfile.IMPACT_LEVEL_CRITICAL: 4,
    ServiceBIAProfile.IMPACT_LEVEL_CATASTROPHIC: 5,
    "UNKNOWN": 0,
}


def _build_dependency_map() -> Dict[int, Set[int]]:
    """Build a full dependency adjacency map in one query."""
    adjacency: Dict[int, Set[int]] = defaultdict(set)
    for source_id, target_id in AssetDependency.objects.values_list("source_asset_id", "target_asset_id"):
        adjacency[source_id].add(target_id)
    return adjacency


def _propagate_asset_failures_cached(asset_ids: Iterable[int], dependency_map: Dict[int, Set[int]]) -> Set[int]:
    """Propagate failures using a precomputed dependency map."""
    failed: Set[int] = set(asset_ids)
    frontier: List[int] = list(asset_ids)

    while frontier:
        current = frontier.pop()
        for target_id in dependency_map.get(current, set()):
            if target_id not in failed:
                failed.add(target_id)
                frontier.append(target_id)

    return failed


def _derive_default_curve(mtpd_minutes: int) -> List[Dict[str, Any]]:
    """Derive a default escalation curve from MTPD when none is provided."""
    if mtpd_minutes <= 0:
        return []
    steps = [
        (0.25, ServiceBIAProfile.IMPACT_LEVEL_MINOR),
        (0.50, ServiceBIAProfile.IMPACT_LEVEL_DEGRADED),
        (0.75, ServiceBIAProfile.IMPACT_LEVEL_SEVERE),
        (1.00, ServiceBIAProfile.IMPACT_LEVEL_CRITICAL),
    ]
    curve: List[Dict[str, Any]] = []
    last_time = 0
    for ratio, level in steps:
        time_minutes = int((mtpd_minutes * ratio) + 0.999)
        if time_minutes <= last_time:
            time_minutes = last_time + 1
        curve.append({"time_minutes": time_minutes, "level": level})
        last_time = time_minutes
    return curve


def _normalize_crisis_rules(rules: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize crisis trigger rules by applying defaults and returning warnings."""
    warnings: List[str] = []
    if not rules:
        warnings.append("MISSING_CRISIS_RULES_DEFAULTS_APPLIED")
        return {
            "mtpd_percentage_trigger": 0.75,
            "impact_level_trigger": ServiceBIAProfile.IMPACT_LEVEL_CRITICAL,
            "environmental_severity_trigger": None,
            "safety_severity_trigger": None,
        }, warnings

    normalized = {
        "mtpd_percentage_trigger": rules.get("mtpd_percentage_trigger", 0.75),
        "impact_level_trigger": rules.get("impact_level_trigger", ServiceBIAProfile.IMPACT_LEVEL_CRITICAL),
        "environmental_severity_trigger": rules.get("environmental_severity_trigger"),
        "safety_severity_trigger": rules.get("safety_severity_trigger"),
    }
    missing_keys = {"mtpd_percentage_trigger", "impact_level_trigger"} - set(rules.keys())
    if missing_keys:
        warnings.append("MISSING_CRISIS_RULES_DEFAULTS_APPLIED")
    return normalized, warnings


def evaluate_service_impact(bia_profile: ServiceBIAProfile, outage_minutes: int) -> Dict[str, Any]:
    """Evaluate service impact and crisis recommendation for a single service.

    BIA time thresholds are stored in hours and converted to minutes for evaluation.
    """
    warnings: List[str] = []
    breaches: List[str] = []

    mtpd_minutes = bia_profile.mtpd_minutes
    rto_minutes = bia_profile.rto_minutes

    if rto_minutes > 0 and outage_minutes >= rto_minutes:
        breaches.append("RTO_BREACH")

    curve = bia_profile.impact_escalation_curve
    if curve and not isinstance(curve, list):
        curve = None
        warnings.append("INVALID_ESCALATION_CURVE_DEFAULT_APPLIED")
    if not curve:
        curve = _derive_default_curve(mtpd_minutes)
        warnings.append("MISSING_ESCALATION_CURVE_DERIVED_DEFAULT")

    impact_level = "UNKNOWN"
    next_threshold_minutes = None
    next_threshold_level = None

    if mtpd_minutes <= 0:
        warnings.append("MISSING_MTPD")
    else:
        if outage_minutes > mtpd_minutes:
            impact_level = ServiceBIAProfile.IMPACT_LEVEL_CATASTROPHIC
        elif curve:
            try:
                sorted_curve = sorted(curve, key=lambda step: step["time_minutes"])
                for step in sorted_curve:
                    if outage_minutes >= step["time_minutes"]:
                        impact_level = step["level"]
                for step in sorted_curve:
                    if outage_minutes < step["time_minutes"]:
                        next_threshold_minutes = step["time_minutes"]
                        next_threshold_level = step["level"]
                        break
            except (KeyError, TypeError):
                warnings.append("INVALID_ESCALATION_CURVE_DEFAULT_APPLIED")
                curve = _derive_default_curve(mtpd_minutes)
                if curve:
                    sorted_curve = sorted(curve, key=lambda step: step["time_minutes"])
                    for step in sorted_curve:
                        if outage_minutes >= step["time_minutes"]:
                            impact_level = step["level"]

    rules, rules_warnings = _normalize_crisis_rules(bia_profile.crisis_trigger_rules)
    warnings.extend(rules_warnings)

    level_severity = IMPACT_LEVEL_SEVERITY.get(impact_level, 0)
    trigger_level_severity = IMPACT_LEVEL_SEVERITY.get(rules["impact_level_trigger"], 0)

    crisis_recommended = False
    if mtpd_minutes > 0 and outage_minutes >= mtpd_minutes * float(rules["mtpd_percentage_trigger"]):
        crisis_recommended = True
    if level_severity >= trigger_level_severity:
        crisis_recommended = True

    environmental_threshold = rules.get("environmental_severity_trigger")
    if environmental_threshold is not None and bia_profile.impact_environmental >= environmental_threshold and level_severity >= 3:
        crisis_recommended = True

    safety_threshold = rules.get("safety_severity_trigger")
    if safety_threshold is not None and bia_profile.impact_safety >= safety_threshold and level_severity >= 2:
        crisis_recommended = True

    mtpd_progress = (outage_minutes / mtpd_minutes) if mtpd_minutes > 0 else 0

    return {
        "impact_level": impact_level,
        "mtpd_progress": round(mtpd_progress, 4),
        "crisis_recommended": crisis_recommended,
        "warnings": warnings,
        "next_threshold_minutes": next_threshold_minutes,
        "next_threshold_level": next_threshold_level,
        "breaches": breaches,
    }


def evaluate_incident_services(
    incident_start_time: datetime,
    current_time: datetime,
    affected_asset_ids: Iterable[int],
) -> List[Dict[str, Any]]:
    """Evaluate impact for services affected by an incident based on assets."""
    if timezone.is_naive(incident_start_time):
        incident_start_time = timezone.make_aware(incident_start_time)
    if timezone.is_naive(current_time):
        current_time = timezone.make_aware(current_time)
    outage_minutes = max(0, int((current_time - incident_start_time).total_seconds() // 60))
    dependency_map = _build_dependency_map()
    impacted_assets = _propagate_asset_failures_cached(affected_asset_ids, dependency_map)

    service_assets: Dict[int, Set[int]] = defaultdict(set)
    services: Dict[int, Any] = {}
    mappings = (
        ServiceAssetMapping.objects.filter(asset_id__in=impacted_assets)
        .select_related("service", "service__bia_profile")
    )
    for mapping in mappings:
        service_assets[mapping.service_id].add(mapping.asset_id)
        services[mapping.service_id] = mapping.service

    results: List[Dict[str, Any]] = []
    for service_id, service in services.items():
        bia_profile = getattr(service, "bia_profile", None)
        if not bia_profile:
            continue
        impact = evaluate_service_impact(bia_profile, outage_minutes)
        results.append(
            {
                "service_id": service_id,
                "name": service.name,
                "impact_level": impact["impact_level"],
                "mtpd_progress": impact["mtpd_progress"],
                "crisis_recommended": impact["crisis_recommended"],
                "warnings": impact["warnings"],
                "next_threshold_minutes": impact["next_threshold_minutes"],
                "next_threshold_level": impact["next_threshold_level"],
                "breaches": impact["breaches"],
            }
        )
    return results


def evaluate_incident_by_id(incident_id: int) -> Optional[List[Dict[str, Any]]]:
    """Evaluate impact for a recorded incident (RiskIssue) by ID."""
    issue = (
        RiskIssue.objects.select_related("risk", "risk__primary_asset")
        .filter(id=incident_id)
        .first()
    )
    if not issue or not issue.risk:
        return None

    affected_asset_ids: Set[int] = set()
    if issue.risk.primary_asset_id:
        affected_asset_ids.add(issue.risk.primary_asset_id)
    affected_asset_ids.update(
        RiskAsset.objects.filter(risk_id=issue.risk_id).values_list("asset_id", flat=True)
    )

    return evaluate_incident_services(issue.created_at, timezone.now(), affected_asset_ids)
