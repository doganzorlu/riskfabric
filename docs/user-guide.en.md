# Riskfabric User Manual (EN)

This manual teaches enterprise risk management from zero and explains how Riskfabric implements each concept. It follows the menu and is intended to be read like a training book.

## Foundations

### What Is Risk?

Risk is the possibility that an event will affect objectives.
A complete risk statement includes cause, event, and impact.
Example: Because of incomplete access reviews (cause), privileged access misuse (event) could occur, leading to service outage or data loss (impact).
- Risk has uncertainty. If it is certain, it is an issue, not a risk.
- Risk is always tied to objectives and assets.
- Risk is owned by a person or team, not by a system.
- Risk statements should be specific and actionable.

### Risk Analysis

Risk analysis evaluates likelihood and impact to derive a risk level.
It can be qualitative, quantitative, or hybrid.
- Likelihood: probability of the event.
- Impact: severity if the event occurs.
- Existing controls: reduce probability or impact.
- Treatment effectiveness: expected reduction from planned actions.
- Assumptions should be documented.

### Risk Assessment Lifecycle

1. Identify risks on assets and processes.
2. Analyze likelihood and impact using a scoring method.
3. Evaluate risk acceptability against criteria.
4. Treat risks with controls or mitigation plans.
5. Monitor risk status and key indicators.
6. Review periodically and update decisions.

### Vulnerability Management

A vulnerability is a weakness that can be exploited.
Vulnerability analysis examines exposure, likelihood, and controls for a weakness.
- Vulnerabilities are linked to assets.
- Vulnerabilities can be mapped to risks.
- A vulnerability can exist without a realized incident.
- Vulnerability prioritization should consider asset criticality.

### Governance and Compliance

Governance defines who decides, who approves, and how compliance is monitored.
Compliance proves alignment with standards and regulations.
- Governance programs set policy and oversight.
- Compliance frameworks define requirements.
- Controls and tests provide evidence.


## Risk Management Concepts

### Risk Appetite and Tolerance

Risk appetite describes how much risk the organization is willing to accept.
Risk tolerance defines acceptable variation around objectives.
- Set appetite at leadership level.
- Translate appetite to thresholds in scoring methods.
- Use tolerance to define treatment triggers.

### Risk Categories

- Strategic
- Operational
- Financial
- Compliance
- Technology
- Third-party

### Inherent vs Residual Risk

Inherent risk is the risk before controls.
Residual risk is what remains after controls and treatments.
- Record both when possible.
- Residual risk drives decisions.

### Business Impact Analysis (BIA)

Business Impact Analysis captures service tolerance for disruption.
- MTPD (MAO), RTO, and RPO define the maximum tolerable downtime, recovery time, and data loss objectives.
- Time values are entered in hours but evaluated in minutes for escalation modeling.
- Impact dimensions (operational, financial, environmental, safety, legal, reputation) represent maximum potential severity, not current impact.
- Escalation curves map outage duration to impact levels over time.
- Crisis rules define when the system should recommend a crisis response based on time thresholds and impact level.


## Menu Overview

### Dashboard

The landing page provides metrics, charts, and trends based on your access scope.
Use it for situational awareness and quick navigation.

### Assets

- Asset Classes
- Assets
- Asset Dependencies
- Location Tree

### Risks

- Risk List
- Risk Detail (single operations center)
- Treatments
- Reviews
- Issues and Exceptions

### Assessments

- Assessment List
- Assessment Detail

### Vulnerabilities

- Vulnerability List
- Vulnerability Detail

### Governance

- Governance Programs
- Policies and Standards

### Compliance

- Compliance Frameworks
- Compliance Requirements
- Control Test Plans
- Control Test Runs

### Reports

- Risk Overview
- Vulnerability Summary
- Compliance Coverage
- Control Effectiveness
- CSV Export

### System Parameters

- Risk Scoring Methods
- Categories
- Tags
- Status Catalogs


## Field-by-Field Guides

### Risk Fields

This section provides a field-by-field guide for the Risk screen.

- Title: Short summary of the risk.
  Tips: Use a verb and object, e.g., Unauthorized access to ERP.
- Description: Full risk statement including cause, event, impact.
  Tips: Use cause-event-impact structure.
- Asset: Asset where the risk exists.
  Tips: Select the most specific asset.
- Likelihood: Probability rating.
  Tips: Base on historical frequency and exposure.
- Impact: Severity rating.
  Tips: Consider financial, operational, compliance impact.
- Score: Calculated by scoring method.
  Tips: Check which scoring method is selected.
- Status: Lifecycle state.
  Tips: Use Draft while analysis is incomplete.
- Owner: Accountable person or team.
  Tips: Assign to someone who can drive actions.
- Treatment Effectiveness: Expected reduction in score.
  Tips: Keep conservative assumptions.


## Additional Field Guides

### Vulnerability Fields

This section provides a field-by-field guide for the Vulnerability screen.

- Title: Short summary of the weakness.
  Tips: Use the affected component name.
- Description: Detailed explanation and evidence.
  Tips: Reference scanner output or findings.
- Asset: Affected asset.
  Tips: Map to the precise asset.
- Severity: Impact of exploitation.
  Tips: Align with scoring standard.
- Status: Open, In Review, Closed.
  Tips: Use Closed only after verification.
- Related Risks: Mapped risks.
  Tips: Create a risk if one does not exist.

### Assessment Fields

This section provides a field-by-field guide for the Assessment screen.

- Scope: What is being assessed.
  Tips: Define boundaries clearly.
- Method: Methodology used.
  Tips: Document frameworks used.
- Owner: Person leading the assessment.
  Tips: Ensure accountability.
- Findings: Key results and observations.
  Tips: Include evidence and references.
- Linked Risks: Risks created or updated.
  Tips: Maintain traceability.

### Control Test Plan Fields

This section provides a field-by-field guide for the Control Test Plan screen.

- Name: Plan title.
  Tips: Use control name + frequency.
- Control: Control being tested.
  Tips: Match to control library.
- Frequency: How often to test.
  Tips: Align with risk criticality.
- Owner: Test owner.
  Tips: Assign to compliance role.
- Procedure: Steps to execute test.
  Tips: Write step-by-step instructions.


## Process Chapters

### Process Chapter 1: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 2: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 3: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 4: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 5: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 6: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 7: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 8: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 9: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.

### Process Chapter 10: Operational Risk Workflow

Objective: explain end-to-end workflow with roles and approvals.
Steps:
- Initiate risk identification for new assets.
- Analyze likelihood and impact.
- Apply scoring method and capture evidence.
- Propose treatment and route approval.
- Schedule review and monitor KRIs.
Quality checks:
- Verify ownership and accountability.
- Ensure controls are mapped.
- Confirm residual risk is documented.



## Appendix

### Glossary

- Asset: Anything of value that must be protected.
- Risk: Potential negative event impacting objectives.
- Treatment: Action to reduce or accept risk.
- Control: Safeguard or process to reduce risk.
- Compliance: Adherence to standards and regulations.

### Example Templates

Example risk register row: Asset, Risk, Likelihood, Impact, Score, Status, Owner, Treatment.
Example control test record: Control, Test Date, Evidence, Result.



## Case Studies

### Case Study 1: ERP Access Review Failure

Context: Quarterly access reviews for ERP were delayed, and privileged accounts accumulated.

Actions:
- Map ERP as a critical asset and list dependencies.
- Create a risk with cause-event-impact statement.
- Score likelihood using review delay evidence.
- Add treatment: automated access reviews and approvals.
- Set review cadence to quarterly with audit evidence.

Outcome: Residual risk reduced; compliance audit passed with evidence.

### Case Study 2: Unpatched OT Systems

Context: Production floor PLCs missed critical patches due to downtime constraints.

Actions:
- Register OT assets with location metadata.
- Create vulnerability entries for missing patches.
- Link vulnerabilities to operational risk.
- Plan maintenance windows as treatment.
- Track KRIs for patch compliance.

Outcome: Patch compliance improved to 90% and risk score decreased.

### Case Study 3: Third-Party Logistics Outage

Context: Logistics provider outage caused shipment delays and revenue impact.

Actions:
- Add third-party asset and dependency mapping.
- Create risk and score impact based on revenue loss.
- Define treatment: secondary provider onboarding.
- Document governance approvals and contracts.

Outcome: Supplier diversification reduced impact and improved resilience.

### Case Study 4: Data Center Power Instability

Context: Power fluctuations increased failure rate for storage arrays.

Actions:
- Log asset and dependency on power systems.
- Create risk and link to incident evidence.
- Add treatment: UPS upgrade and monitoring.
- Schedule monthly reviews until stabilization.

Outcome: Incident frequency dropped and residual risk accepted.

### Case Study 5: Identity Phishing Campaign

Context: Multiple users reported suspicious emails targeting MFA tokens.

Actions:
- Open vulnerability record for phishing exposure.
- Update risk scoring due to increased likelihood.
- Add treatment: phishing simulation and awareness training.
- Track KRI: phishing click rate.

Outcome: Click rate reduced by 60% and risk lowered.

### Case Study 6: Compliance Gap in ISO 27001 Control

Context: Audit found incomplete evidence for access logging control.

Actions:
- Map control requirement to compliance framework.
- Create control test plan and run.
- Capture missing evidence and remediation steps.
- Schedule retest within 30 days.

Outcome: Control passed on retest with documented evidence.

### Case Study 7: Cloud Cost Overrun

Context: Unexpected cloud spend exceeded budget by 30%.

Actions:
- Register cloud platform as asset.
- Create financial risk with likelihood based on trend.
- Define treatment: cost guardrails and alerts.
- Set monthly review and KPI reporting.

Outcome: Spend stabilized within budget in two months.

### Case Study 8: ERP Access Review Failure

Context: Quarterly access reviews for ERP were delayed, and privileged accounts accumulated.

Actions:
- Map ERP as a critical asset and list dependencies.
- Create a risk with cause-event-impact statement.
- Score likelihood using review delay evidence.
- Add treatment: automated access reviews and approvals.
- Set review cadence to quarterly with audit evidence.

Outcome: Residual risk reduced; compliance audit passed with evidence.

### Case Study 9: Unpatched OT Systems

Context: Production floor PLCs missed critical patches due to downtime constraints.

Actions:
- Register OT assets with location metadata.
- Create vulnerability entries for missing patches.
- Link vulnerabilities to operational risk.
- Plan maintenance windows as treatment.
- Track KRIs for patch compliance.

Outcome: Patch compliance improved to 90% and risk score decreased.

### Case Study 10: Third-Party Logistics Outage

Context: Logistics provider outage caused shipment delays and revenue impact.

Actions:
- Add third-party asset and dependency mapping.
- Create risk and score impact based on revenue loss.
- Define treatment: secondary provider onboarding.
- Document governance approvals and contracts.

Outcome: Supplier diversification reduced impact and improved resilience.

### Case Study 11: Data Center Power Instability

Context: Power fluctuations increased failure rate for storage arrays.

Actions:
- Log asset and dependency on power systems.
- Create risk and link to incident evidence.
- Add treatment: UPS upgrade and monitoring.
- Schedule monthly reviews until stabilization.

Outcome: Incident frequency dropped and residual risk accepted.

### Case Study 12: Identity Phishing Campaign

Context: Multiple users reported suspicious emails targeting MFA tokens.

Actions:
- Open vulnerability record for phishing exposure.
- Update risk scoring due to increased likelihood.
- Add treatment: phishing simulation and awareness training.
- Track KRI: phishing click rate.

Outcome: Click rate reduced by 60% and risk lowered.

### Case Study 13: Compliance Gap in ISO 27001 Control

Context: Audit found incomplete evidence for access logging control.

Actions:
- Map control requirement to compliance framework.
- Create control test plan and run.
- Capture missing evidence and remediation steps.
- Schedule retest within 30 days.

Outcome: Control passed on retest with documented evidence.

### Case Study 14: Cloud Cost Overrun

Context: Unexpected cloud spend exceeded budget by 30%.

Actions:
- Register cloud platform as asset.
- Create financial risk with likelihood based on trend.
- Define treatment: cost guardrails and alerts.
- Set monthly review and KPI reporting.

Outcome: Spend stabilized within budget in two months.

### Case Study 15: ERP Access Review Failure

Context: Quarterly access reviews for ERP were delayed, and privileged accounts accumulated.

Actions:
- Map ERP as a critical asset and list dependencies.
- Create a risk with cause-event-impact statement.
- Score likelihood using review delay evidence.
- Add treatment: automated access reviews and approvals.
- Set review cadence to quarterly with audit evidence.

Outcome: Residual risk reduced; compliance audit passed with evidence.

### Case Study 16: Unpatched OT Systems

Context: Production floor PLCs missed critical patches due to downtime constraints.

Actions:
- Register OT assets with location metadata.
- Create vulnerability entries for missing patches.
- Link vulnerabilities to operational risk.
- Plan maintenance windows as treatment.
- Track KRIs for patch compliance.

Outcome: Patch compliance improved to 90% and risk score decreased.

### Case Study 17: Third-Party Logistics Outage

Context: Logistics provider outage caused shipment delays and revenue impact.

Actions:
- Add third-party asset and dependency mapping.
- Create risk and score impact based on revenue loss.
- Define treatment: secondary provider onboarding.
- Document governance approvals and contracts.

Outcome: Supplier diversification reduced impact and improved resilience.

### Case Study 18: Data Center Power Instability

Context: Power fluctuations increased failure rate for storage arrays.

Actions:
- Log asset and dependency on power systems.
- Create risk and link to incident evidence.
- Add treatment: UPS upgrade and monitoring.
- Schedule monthly reviews until stabilization.

Outcome: Incident frequency dropped and residual risk accepted.

### Case Study 19: Identity Phishing Campaign

Context: Multiple users reported suspicious emails targeting MFA tokens.

Actions:
- Open vulnerability record for phishing exposure.
- Update risk scoring due to increased likelihood.
- Add treatment: phishing simulation and awareness training.
- Track KRI: phishing click rate.

Outcome: Click rate reduced by 60% and risk lowered.

### Case Study 20: Compliance Gap in ISO 27001 Control

Context: Audit found incomplete evidence for access logging control.

Actions:
- Map control requirement to compliance framework.
- Create control test plan and run.
- Capture missing evidence and remediation steps.
- Schedule retest within 30 days.

Outcome: Control passed on retest with documented evidence.
