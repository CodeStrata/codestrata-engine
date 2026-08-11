# Recall Metrics

Recall is an internal validation/calibration metric. It answers:

> Of the expected supported positive conditions within a defined validation
> scope, what proportion were detected?

## Formula

```text
recall = true_positives / (true_positives + false_negatives)
```

Counts are authoritative. The metric value is always derived from TP and FN —
callers cannot supply a contradictory precomputed value.

- False positives are excluded from the recall denominator.
- Ambiguous observations are excluded from TP and FN unless adjudicated.
- Not-applicable observations are excluded and do not become FN.
- When TP+FN = 0, `value` is null and availability is `unavailable` or
  `not_applicable` — never an artificial 0.0 or 1.0.

## Expected-positive authority

Recall requires evidence-authored expected positives, such as required findings,
signals, manifests, inventory facts, recommendations, Priority Actions, or
roadmap initiatives.

Negative controls alone cannot establish recall. A pack with only forbidden
expectations may validate precision or absence behavior, but recall remains
unavailable and must not be reported as 1.0.

“No mismatch” is not a true positive.

## False negatives

A false negative means a supported, evidence-authored expected positive exists,
the product contract should detect it, and actual output missed it.

Do not count as FN: unsupported capabilities, not-claimed areas, ambiguous
signals, unavailable external context, runtime-only conditions, intentionally
excluded generated/test/vendor content, or incorrect expectations.

## Scopes

| Scope | Example metric id |
| ----- | ----------------- |
| validation set / pack | `recall:validation_set:security` |
| repository + pack | `recall:repository:local-security-hygiene:security` |
| rule | `recall:rule:security.credential-literal` |
| inventory category | `recall:inventory_category:frameworks` |
| evidence family | `recall:evidence_family:cloud.iac` |

Metric IDs are deterministic. They do not include timestamps, run IDs, or paths.

## Aggregation

Pack aggregates **sum repository TP and FN first**, then compute recall.
Repository recall percentages are never averaged.

## Negative controls and PASS

A repository may PASS with unavailable recall. PASS means authored expectations
passed; it does not imply every supported capability was exercised or that
recall is 1.0.

## Controlled versus real-world

Controlled-fixture-only recall must state fixture count, expected-positive
count, and that it does not establish arbitrary-repository recall. Mixed scope
uses `mixed_validation_set`.

## Sample size

TP, FN, denominator, repositories evaluated, repositories with authored expected
positives, and controlled/real-world counts are preserved. Small samples remain
numerically correct but may be `provisional` / `insufficient_sample`.

## What Recall is not

| Concept | Relationship |
| ------- | ------------ |
| Precision | Separate; uses TP+FP ([precision-metrics.md](./precision-metrics.md)) |
| False-Negative Tracking | Lifecycle/adjudication ledger; does not redefine raw Recall ([false-negative-tracking.md](./false-negative-tracking.md)) |
| Confidence | Separate; recall does not recalibrate confidence in this slice |
| Assessment Coverage | Unrelated runtime examined-scope metric |
| F1 / accuracy | Not computed in this slice |
| Product-wide detection | Validation-set evidence only |

## Customer boundary

Recall must not appear on customer `report.json`, HTML assessment reports,
finding cards, CCL, EIS, Priority Actions, or roadmaps.

## Disclaimer

Prefer “Recall: 1.000 within this authored validation scope.” Never “100%
detection,” “all issues found,” or “complete recall.”
