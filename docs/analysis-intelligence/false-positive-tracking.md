# False-Positive Tracking

False-positive tracking is internal validation/calibration infrastructure for
confirmed or suspected false positives discovered by the Epic 4 validation
harness.

It answers which repository, pack, rule/entity, expected condition, and actual
output produced a false positive; whether it was confirmed, rejected, ambiguous,
or an expectation error; root cause; resolution; and first/last-seen runs.

## What it is not

- Customer finding status
- Suppression or waiver management
- Risk acceptance
- Precision itself
- Confidence
- Severity
- AI adjudication

## Suspected versus confirmed

A pack classifier `FALSE_POSITIVE` starts as:

- `confirmed` for reviewed controlled fixtures with explicit forbidden
  expectations
- `suspected` for real-world repositories until adjudicated

Ambiguous observations use `classification=ambiguous` and are excluded from
confirmed FP counts. Unsupported capabilities and expectation errors are
separate classifications.

## Identity

`false_positive_id = fp:{sha256[:24]}` from repository, area, entity type,
rule/entity, path, and expected/actual identity strings. No timestamps, run IDs,
absolute paths, or raw snippets.

## Lifecycle

Statuses: `open` · `investigating` · `accepted_ambiguous` · `fixed` ·
`rejected` · `superseded`

Fixed confirmed product FPs require root cause, resolution, and a regression
test reference for `product_fix`.

## History

Slice 4.11 run history supplies first/last-seen. Skip/error runs do not resolve
FPs. Absence from a later successful run does not auto-resolve without
adjudication.

## Adjudications

Committed under `engine/validation/adjudications/`. Generated records never
overwrite them.

## Precision relationship

Pack classifier FP counts continue to feed `PrecisionMetric` unchanged.
See also [False-Negative Tracking](./false-negative-tracking.md),
[Duplicate Finding Consolidation](./duplicate-finding-consolidation.md),
[Cross-Rule Correlation](./cross-rule-correlation.md),
[Precision Metrics](./precision-metrics.md), and
[Recall Metrics](./recall-metrics.md).

`FalsePositiveRecord` tracks adjudication separately and does not silently
redefine historical precision.

## Recall / confidence / coverage

Unchanged by this slice.

## Customer boundary

Not exposed in customer `report.json`, HTML, CCL, EIS, findings,
recommendations, Priority Actions, roadmap, or MCP customer tools.

## Safety

Expected/actual values use `SafeValidationValue`: bounded, redacted,
repository-relative, no snippets/secrets/absolute paths.

## CLI

```bash
python -m validation.false_positives list
python -m validation.false_positives show fp:...
python -m validation.false_positives summarize
```

Read-only. No assessment execution.
