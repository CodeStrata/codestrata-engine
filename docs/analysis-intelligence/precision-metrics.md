# Precision Metrics

Precision is an internal validation/calibration metric. It answers:

> Of the assessment outputs classified as positive within a defined validation
> scope, what proportion were confirmed true positives?

## Formula

```text
precision = true_positives / (true_positives + false_positives)
```

Counts are authoritative. The metric value is always derived from TP and FP —
callers cannot supply a contradictory precomputed value.

- Ambiguous observations are excluded from TP, FP, and the denominator.
- Not-applicable observations are excluded.
- False negatives are excluded from the precision denominator (they belong to recall).
- When TP+FP = 0, `value` is null and availability is `unavailable` or
  `not_applicable` — never an artificial 0.0 or 1.0.

## Scopes

Every `PrecisionMetric` identifies a scope, for example:

| Scope | Example metric id |
| ----- | ----------------- |
| validation set / pack | `precision:validation_set:security` |
| repository + pack | `precision:repository:local-security-hygiene:security` |
| rule | `precision:rule:security.credential-literal` |
| inventory category | `precision:inventory_category:languages` |
| evidence family | `precision:evidence_family:cloud.container` |

Metric IDs are deterministic. They do not include timestamps, run IDs, or paths.

## Aggregation

Pack aggregates **sum repository TP and FP first**, then compute precision.
Repository precision percentages are never averaged.

## Controlled versus real-world

Source is recorded as controlled-fixture, real-world, expected/actual validation,
or mixed. Controlled-only metrics must state they are not representative of
arbitrary repositories. High numeric precision does not upgrade calibration.

## Sample size

TP, FP, denominator, repositories evaluated, and repositories with positive
classifications are preserved. Small positive samples remain numerically correct
but may be marked `provisional` / `insufficient_sample`.

## What Precision is not

| Concept | Relationship |
| ------- | ------------ |
| Recall | Separate metric ([recall-metrics.md](./recall-metrics.md)); uses FN in its denominator |
| Confidence | Separate; precision does not recalibrate confidence in this slice |
| Assessment Coverage | Unrelated runtime examined-scope metric |
| PASS verdict | A repository can PASS as a negative control with unavailable precision |
| Product-wide accuracy | Validation-set evidence only |

## Customer boundary

Precision must not appear on customer `report.json`, HTML assessment reports,
finding cards, CCL, EIS, Priority Actions, or roadmaps. Assessment runtime has
no ground truth.

## Disclaimer

Validation summaries retain:

> These results describe only the repositories and controlled fixtures included
> in this validation set. They are not a product-wide accuracy claim.

Prefer “Precision: 1.000 within this validation scope.” Never “100% accurate.”
