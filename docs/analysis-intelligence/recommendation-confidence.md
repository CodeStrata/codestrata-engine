# Recommendation Confidence

Recommendation Confidence describes how strongly the deterministic Findings
support a specific recommended action.

It answers: “How strongly do the deterministic findings support this specific
recommended action?”

## What it is not

- Recommendation priority, priority score, or presentation horizon
  (see [Recommendation Prioritization Calibration](./recommendation-prioritization-calibration.md);
  confidence may *cap* priority but does not define it)
- Finding severity or business impact
- Expected ROI, delivery certainty, or remediation success probability
- Assessment-Head Confidence
- Validation-set precision / product accuracy
- AI confidence or a customer risk score

A high-priority Recommendation may have Limited Recommendation Confidence. A
low-priority Recommendation may have High Recommendation Confidence.

## Levels

| Level | Meaning |
| ----- | ------- |
| `high` | All supporting Findings High, complete finding traceability, finding-backed (or merged) support |
| `moderate` | Meaningful support capped by at least one Moderate supporting Finding |
| `limited` | Partial traceability, Limited supporting Finding, Unavailable Finding Confidence cap, or fact-based without a Finding contract |
| `unavailable` | Legacy Recommendation, missing/unresolved supporting Findings, or contradictory support |

## Weakest-support principle

Recommendation Confidence never exceeds the weakest materially required
supporting Finding Confidence. Levels are not averaged. Multiple High Findings
cannot compensate for one materially required Limited Finding.

All canonical `supporting_finding_ids` are materially required. Optional-support
semantics are not introduced in this slice.

## Derivation components

- supporting Finding Confidence values
- primary Finding Confidence (recorded; does not override weaker support)
- `supporting_finding_ids` / `primary_finding_id`
- evidence completeness and finding traceability completeness
- recommendation type (`finding_backed`, `merged`, `fact_based`, `legacy`)
- assessment-head ownership of supporting Findings
- Recommendation limitations

Do not derive from priority, effort, severity, title wording, roadmap phase, AI
output, or Epic 4 aggregate precision.

## Primary Finding

`primary_finding_id` must resolve and belong to `supporting_finding_ids`. A
stronger primary Finding does not raise Recommendation Confidence above the
weakest supporting Finding.

## Finding-backed / merged / legacy / fact-based

| Type | Behavior |
| ---- | -------- |
| `finding_backed` | Derive after Findings resolve; unresolved support fails closed |
| `merged` | Union supporting IDs; recompute; weakest support wins; no first-wins |
| `legacy` | Unavailable; no priority/title fallback |
| `fact_based` | Limited or Unavailable with explicit limitation unless a Finding support contract exists |

## Cross-head support

Findings from more than one assessment head are preserved. Confidence remains
bounded by weakest supporting Finding. Basis includes `cross_head_support`.
Multiple heads do not raise or lower confidence by themselves.

## Relationship to Assessment-Head Confidence

Recommendation Confidence derives from Findings, not from Assessment-Head
Confidence. A head may remain lower because of broader coverage limitations
even when a specific Recommendation has High Finding support.

## Priority Actions and Roadmap

Priority Action Confidence and roadmap confidence are out of scope for this
slice. Recommendation Confidence is preserved so later prioritization can
consume it. Priority Action IDs and ranking are unchanged.

## Report and HTML

Recommendations serialize additive `recommendation_confidence`. HTML detail
cards may show an explicit **Recommendation confidence** label separately from
priority and Finding Confidence. Leadership Priority Action cards are not
redesigned.
