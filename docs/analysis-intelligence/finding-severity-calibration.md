# Finding Severity Calibration

Severity answers:

> How significant is the observed technical condition if it is valid within the
> assessed repository scope?

Severity is **not** confidence, probability, Precision, Recall, Assessment
Coverage, customer business impact, remediation effort, Recommendation priority,
duplicate count, correlation count, or AI judgment.

A Finding may be High severity with Limited confidence, or Low severity with
High confidence. That independence is intentional.

## Base versus calibrated severity

- **Base severity** — rule default significance from the severity policy catalog
- **Calibrated severity** — repository-specific deterministic adjustment
  (context caps, measurement bands, allowed-severity clamp)

Customer-facing `Finding.severity` is the calibrated value.

## Inputs allowed

Rule identity and explicit policy, evidence kind/directness, production vs
test/fixture/docs/generated/vendor/CI context, measurement value and threshold,
magnitude ratio, affected subject count when the rule models aggregation, graph
identity when known, and explicit configuration state.

## Inputs forbidden

Rule / Evidence / Finding / Assessment-Head / Recommendation Confidence,
PrecisionMetric, RecallMetric, FP/FN counts, title wording, Recommendation
priority, roadmap phase, AI output, correlation count alone, duplicate count
alone, and speculative business or exploit impact.

## Context caps

Shared classifier classes: production, test, fixture, generated, vendor,
example, documentation, CI, unknown.

Non-production contexts are capped per policy. Unknown context does not assume
production where context materially matters.

## Measurement bands (Technical Debt)

For typed complexity metrics:

- equal to threshold → no Finding (rule match gate)
- threshold < value ≤ 2×threshold → medium
- value > 2×threshold → high
- Critical is not used for complexity

## Pack policies

Every registered Shared Rule has an explicit `FindingSeverityPolicy`. Cloud, AI
Readiness, and Performance static readiness signals are capped at
informational/low/medium. Security placeholder credentials stay below production
credential severity. Architecture enterprise mismatch is provisional Low.

`RuleMetadata.severity_policy_id` references the catalog entry
(`severity.{rule_id}`). RuleMatch may optionally carry `base_severity`,
`calibrated_severity`, and `severity_basis`; Finding mapper remains the
authority for customer-facing calibrated severity.

## Duplicate and correlation boundaries

Slice 5.11 consolidation may provisionally keep the highest member severity,
then recalibrates via policy. Duplicate count does not escalate severity.

Slice 5.12 correlations never change Finding severity and do not create cluster
severity.

## Recommendation boundary

Calibrated Finding severity is an input to Recommendation prioritization
(Slice 5.14). Severity is not copied into Recommendation priority.

## Legacy

Phase-1 Findings preserve severity with `calibration_status=legacy`.

## Why business impact and probability are excluded

Static repository assessment cannot establish customer outage cost, exploit
likelihood, or organizational risk. Those belong outside Finding severity.
