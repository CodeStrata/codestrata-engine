# Recommendation Prioritization Calibration

Priority answers:

> Given the supported deterministic Findings, which recommended actions should
> be addressed earlier?

Priority is **not** Finding Severity, Finding Confidence, Recommendation
Confidence, business value, ROI, remediation success probability, exact urgency,
implementation effort, roadmap commitment, customer preference, or AI judgment.

Severity is one input. Severity alone must not determine priority.

## Score purpose and bands

Internal score range: **0–100**.

- Ordering utility only
- Not probability
- Not business impact
- Not ROI

Bands:

| Priority (customer) | Score |
| --- | --- |
| Immediate (critical band) | 90–100 |
| High | 70–89 |
| Medium | 40–69 |
| Low | 0–39 |

Compatibility fields `priority` and `priority_score` remain projections of the
canonical `priority_assessment`.

## Policy catalog

Every builtin deterministic Recommendation provider resolves to one explicit
`RecommendationPriorityPolicy`. Policies are deterministic, reviewable, and
testable. There is no title matching and no Precision/Recall/FP/FN input.

Legacy Recommendations use `priority.legacy.compatibility` with a conservative
cap (no Immediate/Critical).

## Confidence caps

Recommendation Confidence constrains urgency; it does not generate urgency.

- High — full policy range
- Moderate — generally cannot be Immediate unless an explicit direct-exposure
  policy allows it
- Limited — capped per policy (typically Medium or below)
- Unavailable — legacy/provisional; no Immediate

Finding Confidence is not double-counted after Recommendation Confidence is
known. Assessment-Head Confidence does not directly score an individual
Recommendation.

## Severity contribution

Uses calibrated Finding Severity (Slice 5.13).

- Preserve highest material severity
- Do not sum severity values
- Do not multiply by Finding count
- Do not copy severity into priority

## Scope and correlation

Scope and correlation adjustments are bounded and policy-gated.

- Duplicate member count never increases priority
- Raw correlation count never increases priority
- Only reviewed correlation-aware providers receive a bounded adjustment

## Effort and sequencing

Effort remains separate from priority.

- priority = importance / order
- effort = implementation size
- roadmap phase = sequencing (Secure / Stabilize / Modernize / Optimize)

Effort may influence phase/bucket through explicit policy, but a large high-
priority action may remain High while sequencing later.

## Priority Actions and roadmap

Priority Actions derive from calibrated Recommendations:

- primary Recommendation selected by calibrated priority/score
- action priority/score from supporting Recommendations
- no direct Finding scoring
- no title heuristics

Roadmap phase uses category, prerequisites, calibrated priority, effort, and
explicit phase preference — not numeric score alone.

## Customer presentation

Additive Recommendation JSON may include `priority_assessment` with basis,
calibration status, policy id, and component summary.

HTML recommendation detail may show:

- Recommendation priority
- Priority basis (short labels only)

Leadership sections must not expose formula internals, Precision/Recall, or
FP/FN data.

## Exclusions

PrecisionMetric, RecallMetric, FP/FN totals, title wording, duplicate count,
raw correlation count, customer identity, assumed ROI, and AI output are
excluded from runtime priority calculation. Validation history may inform future
policy review only.
