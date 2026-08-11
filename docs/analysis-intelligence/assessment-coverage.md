# Assessment Coverage

Assessment Coverage describes what portion of an assessment head’s supported
analysis scope was examined during one repository assessment.

It answers: “What supported assessment scope was examined, successfully
processed, skipped, partially processed, unsupported, or unavailable?”

## What it is not

- Confidence (Rule / Finding / Recommendation / Assessment-Head)
- Precision or recall
- Assessment quality, repository health, maturity, or readiness
- Severity or risk
- Code coverage or test coverage
- Probability or AI confidence
- Validation-set repository coverage

Coverage must not be inferred from finding count. Zero findings with complete
coverage is different from zero findings with insufficient evidence.

## Denominator policy

Declared methodology areas use claim states:

| Claim | Denominator role |
| ----- | ---------------- |
| `claimed` | Included as supported / applicable |
| `partial` | Included as partially supported; limitation required |
| `not_claimed` | Excluded from supported coverage ratio; may appear as unsupported detail |

Unsupported areas are not failures. Disabled heads are not unavailable failures.

## Levels / status

`complete` · `partial` · `insufficient_evidence` · `unavailable` · `disabled` ·
`not_applicable`

## Metrics

Where denominators are valid:

- `assessment.area_coverage`
- `assessment.candidate_processing`
- `assessment.rule_execution`

Numerator and denominator are always preserved. Zero denominator → metric
unavailable (no artificial 0% or 100%). Unrelated denominators are never averaged
into a repository-wide coverage score.

## Relationship to Assessment-Head Confidence

Coverage and confidence remain separate. Canonical coverage may cap confidence.
Confidence never determines coverage.

## Modernization

Modernization coverage is synthesized from contributing heads and chain
completeness. It does not invent a numeric ratio from Priority Action counts and
cannot exceed contributing head coverage.

## Epic 4 distinction

Validation-set repository coverage and precision/recall are separate from
assessment-run Assessment Coverage. See [Precision Metrics](./precision-metrics.md)
and [Recall Metrics](./recall-metrics.md) for the internal validation contracts.

## Report and HTML

`report.json` carries additive `assessment.assessment_coverage` keyed by head id
(schema remains 1.2). HTML CCL Coverage renders canonical numerator/denominator
summaries. EIS shows complete/partial/unavailable/disabled head counts without
averaging percentages.
