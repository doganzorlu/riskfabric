# RiskFabric Resilience Architecture Expansion

## 1. Strategic Shift Summary

RiskFabric evolves from an IT-centric risk tool into a Service-Oriented Organizational Resilience Platform.
The new model centers on Critical Services, their business processes, assets, and dependencies. Risk and BIA attach to services and propagate through the dependency graph.

Key impacts:
- Service-based modeling is the primary lens for continuity.
- Impact is time-based and multi-dimensional.
- Hazard-based scenarios drive simulation and cascading failure analysis.
- Asset-based risk remains supported for backward compatibility.

## 2. Domain Model Diagram (Textual)

CriticalService
- has many ServiceProcess
- has many ServiceBIAProfile
- maps to many Assets through ServiceAssetMapping
- has many Risks (optional direct link)

ServiceProcess
- belongs to CriticalService
- maps to many Assets through ServiceAssetMapping

Asset
- has many AssetDependencies (existing)
- has Location metadata (existing + extended)

Hazard
- links to Locations, Assets, and CriticalServices via HazardLink

Scenario
- references a Hazard
- references a CriticalService (optional) and/or Location scope
- uses ImpactEscalationCurve from ServiceBIAProfile

ServiceBIAProfile
- belongs to CriticalService
- has many ImpactEscalationCurve entries

ImpactEscalationCurve
- defines time-based impact per category

Risk
- may link to CriticalService (new)
- still links to Asset (existing)

## 3. Database Schema Proposal

### 3.1 New Tables

`risk_criticalservice`
- id, code, name, description, owner (FK User), status, created_at, updated_at

`risk_serviceprocess`
- id, critical_service_id (FK), name, description, owner (FK User), status

`risk_serviceassetmapping`
- id, critical_service_id (FK), service_process_id (FK, nullable), asset_id (FK)
- role (primary, supporting), notes

`risk_hazard`
- id, code, name, hazard_type, description, active

`risk_hazardlink`
- id, hazard_id (FK), location_id (FK nullable), asset_id (FK nullable), critical_service_id (FK nullable)
- scope (location, asset, service)

`risk_servicebiaprofile`
- id, critical_service_id (FK)
- mao_hours, rto_hours, rpo_hours
- owner (FK User), notes

`risk_impactescalationcurve`
- id, bia_profile_id (FK)
- duration_hours
- impact_financial, impact_operational, impact_legal, impact_reputational, impact_environmental, impact_human_safety

`risk_scenario`
- id, name, hazard_id (FK)
- critical_service_id (FK nullable), location_id (FK nullable)
- duration_hours, assumptions, status

### 3.2 Existing Table Extensions

`asset_asset`
- geo_zone (text)
- seismic_risk_coefficient (decimal)
- infrastructure_criticality (int)

`risk_risk`
- critical_service_id (FK nullable)
- dynamic_risk_score (decimal, nullable)

## 4. Migration Strategy

Phase 1: Schema introduction
- Add new tables and nullable fields.
- No changes to existing risk workflows.

Phase 2: Data backfill
- Create baseline CriticalService entries for top business services.
- Map existing assets to services via ServiceAssetMapping.
- Create BIA profiles per critical service with initial curves.

Phase 3: Dual-mode operation
- Risk can attach to Asset only, Service only, or both.
- DynamicRiskScore computed only when BIA data exists.

Phase 4: Operational adoption
- Enforce Service selection for new continuity-centric risks.
- Integrate scenario simulation into reporting.

## 5. Scenario Simulation Algorithm (Pseudocode)

```
function simulateScenario(hazard_id, duration_hours, location_scope = null, service_scope = null):
    affected_assets = set()

    if location_scope:
        affected_assets += assets_at_location(location_scope)

    if hazard_links for assets:
        affected_assets += linked_assets(hazard_id)

    if service_scope:
        affected_assets += assets_linked_to_service(service_scope)

    # Propagate cascading failures through dependencies
    failed_assets = propagate_dependencies(affected_assets)

    impacted_services = services_linked_to_assets(failed_assets)

    results = []
    for service in impacted_services:
        bia = get_bia_profile(service)
        impact = time_weighted_impact(bia.curve, duration_hours)
        results.append({
            "service": service,
            "duration_hours": duration_hours,
            "impact": impact,
            "failed_assets": failed_assets_for(service),
        })

    return results
```

## 6. Risk Score Enhancement

DynamicRiskScore = Likelihood x TimeWeightedImpact(Service, Duration)

TimeWeightedImpact uses the ServiceBIAProfile escalation curve and aggregates all impact dimensions based on business rules:
- default: max dimension
- optional: weighted sum

## 7. Updated User Manual Outline

### Part 1: Foundations
- What is resilience and continuity
- Critical services vs assets
- Hazard-based risk thinking

### Part 2: Core Modeling
- Critical Services
- Business Processes
- Service-Asset Mapping
- Asset Dependencies

### Part 3: Business Impact Analysis (BIA)
- MAO/MTPD, RTO, RPO
- Impact categories and escalation curves
- Example BIA profile

### Part 4: Hazards and Scenarios
- Hazard library
- Location-based hazards
- Scenario definition and assumptions

### Part 5: Risk and Continuity Workflows
- Service-based risk creation
- Dynamic scoring
- Treatments, approvals, reviews

### Part 6: Reporting
- Service resilience dashboard
- BIA summary
- Scenario simulation outputs

### Part 7: Case Study
- Wastewater Pump Station Failure After Earthquake
- Cascading failure and time-based impact

## 8. Backward Compatibility

- Existing asset-based risk flows remain unchanged.
- Service-based fields are optional at first.
- New modules extend, not replace, current workflows.
