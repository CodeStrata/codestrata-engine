# False-Negative Tracking

False-negative tracking is internal validation/calibration infrastructure for
confirmed or suspected false negatives discovered by the Epic 4 validation
harness.

It answers which repository contains an expected positive condition; which
assessment area, rule, signal, fact, or recommendation should have detected it;
what repository evidence supports the expectation; what output was missing;
whether the condition was in supported scope; classification and status; failed
stage (root cause); resolution; regression coverage; and first/last-seen runs.

## What it is not

- Customer-facing missing-finding status
- Completeness claim for customer assessments
- Recall itself
- Assessment Coverage
- Confidence
- Suppression or waiver management
- Backlog management
- AI adjudication
- Proof that all undetected issues are known

## Expected-positive authority

False-Negative candidates originate only from structured authored expectations
classified by pack validators as `FALSE_NEGATIVE` (or tracked `AMBIGUOUS`
expected positives). Valid authorities include required technology facts,
manifests, signals, findings, rule IDs, recommendations, Priority Actions,
roadmap initiatives, and assessment statuses where the product contract supports
them.

Do not generate durable FN identities from report prose, generic “count too
low” mismatches without identifiable expected positives, unsupported desired
features, unclaimed areas, runtime-only expectations, or AI suggestions. When
structured identity is unavailable, retain the generic mismatch and do not
fabricate a durable FN ID (`false_negative_identity_unavailable`).

## Suspected versus confirmed

A pack classifier `FALSE_NEGATIVE` starts as:

- `confirmed` for reviewed controlled fixtures with explicit required expected
  positives
- `suspected` for real-world repositories until adjudicated

It becomes confirmed only when the expected condition exists in repository
evidence, the expectation is correctly authored, the capability is within
supported and claimed scope, the pack was activated where required, sufficient
evidence was available, the expected output was absent, the condition is not
ambiguous, and no intentional context filter excludes it.

## Ambiguity

Ambiguous expected conditions use `classification=ambiguous` and are excluded
from confirmed FN counts and from adjudicated recall denominators. They remain
visible for quality review and require rationale.

## Unsupported capability

If CodeStrata does not currently claim support, use
`classification=unsupported_capability`. These are not confirmed product FNs.
They remain visible as validation-scope issues and stay excluded from confirmed
counts after adjudication.

## Insufficient evidence

If the capability is supported but the repository did not provide enough usable
evidence, use `classification=insufficient_evidence`. Distinct from product
detection bugs, unsupported capability, and expectation errors. Raw
`RecallMetric` counts remain based on pack classifiers; this slice does not
silently rewrite historical recall.

## Expectation errors

Incorrectly authored expected positives use `classification=expectation_error`
and typically `resolution=expectation_fix`. They remain historically visible
and do not count as confirmed product FNs after adjudication.

## Identity

`false_negative_id = fn:{sha256[:24]}` from repository, assessment area, entity
type, expected rule/signal/category identity, normalized repository-relative
path, and expected-condition identity. No run IDs, timestamps, absolute paths,
temporary directories, mutable diagnostic prose, actual-absence wording, or raw
source snippets. Do not reuse expected Finding IDs as FN IDs.

## Lifecycle

Statuses: `open` · `investigating` · `accepted_ambiguous` · `fixed` ·
`rejected` · `superseded`

Fixed confirmed product FNs require root cause, resolution, and a regression
test reference for `product_fix`. Expectation and fixture fixes may reference
expectation/fixture files instead.

## History and comparability

Slice 4.11 run history supplies first/last-seen. Skip/error/disabled runs do
not resolve FNs. Resolution requires comparable source identity, comparable
expectation identity, successful assessment, expected positive now classified
TP, and adjudication or deterministic resolution policy. Material source-commit
or expectation-contract changes add comparability limitations and must not
falsely resolve.

## Root causes

Confirmed FNs should identify the failed stage (candidate discovery, extraction,
parser, rule predicate, activation, mapping, recommendation provider, etc.).

## Recall relationship

Pack classifier TP/FN counts continue to feed `RecallMetric` unchanged.
`FalseNegativeRecord` adds adjudication and lifecycle metadata separately.
Adjudicated recall projections, if added later, must be labeled separately and
must not overwrite raw `RecallMetric`.

## Precision / confidence / coverage

Unchanged by this slice. A missed expected positive is not automatically an
Assessment Coverage failure.

## Customer boundary

Not exposed in customer `report.json`, HTML, CCL, EIS, findings,
recommendations, Priority Actions, roadmap, or MCP customer tools.

Do not synthesize customer Findings from FN records. Correct product behavior
through analyzers, evidence, rules, mapping, or recommendation providers.

## Safety

Expected/actual values reuse `SafeValidationValue`: bounded, redacted,
repository-relative, no snippets/secrets/absolute paths. Evidence notes are
bounded descriptive text, not source bodies.

## Adjudications

Committed under `engine/validation/adjudications/false_negatives/`. Generated
records never overwrite them.

## CLI

```bash
python -m validation.false_negatives list
python -m validation.false_negatives show fn:...
python -m validation.false_negatives summarize
```

Read-only. No assessment execution.

See also [False-Positive Tracking](./false-positive-tracking.md),
[Recall Metrics](./recall-metrics.md), and
[Precision Metrics](./precision-metrics.md).
