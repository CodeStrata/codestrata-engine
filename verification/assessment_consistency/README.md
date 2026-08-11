"""SV.11 — Assessment Consistency Verification

Verification-only package for System Verification slice SV.11.

## Purpose

Verify that CodeStrata assessment **contracts** behave consistently across the
complete 22-repository v0.2.0 release-validation dataset produced by SV.10.

SV.11 is **not** an accuracy, precision/recall, maturity, health, or ranking
benchmark. It compares schemas, vocabularies, activation/coverage/confidence
semantics, severity/priority policies, traceability, and Engineering
Intelligence input readiness.

## Inputs

- Permanent catalog: `validation/repository-catalog/catalog.json`
- SV.10 outputs: `engine/reports/verification/sv10/`
  - `curated-repository-validation.json`
  - `records/<repository_id>.json`
  - `artifacts/<repository_id>/<sha12>/`

Repositories are **not** cloned or reassessed by default.

## Command

```bash
cd engine
python -m verification.assessment_consistency
```

No network is required.

## Output

```
engine/reports/verification/sv11/
  assessment-consistency-verification.json
```

Contract: `schema_name=assessment-consistency-verification` / `1.0.0`

## Contract versus quality

Valid comparisons: same schema, policy vocabulary, state semantics, ownership,
scoring function behavior, reference integrity, artifact contract.

Invalid comparisons (explicitly guarded): healthier/more mature, better
engineering, Finding-count ranking, language ecosystem quality claims.

## Relationship

| Slice | Role |
| --- | --- |
| SV.10 | Produced the 22 pinned assessments |
| SV.11 | This consistency verification |
| SV.12 | Engineering Intelligence editorial review |
| SV.13 | Defect remediation (EI unsafe_metadata) |

## Engineering Intelligence input readiness

`engineering_intelligence_input_ready` means, for each repository:

- assessment schema 1.2 + identity + coverage/confidence maps
- no embedded source bodies in customer fields
- **Platform** `validate_report_document` accepts the Engine customer-safe
  report projection (same production ingestion safety authority)

SV.11 does not approximate Platform secret detectors. It invokes the real
Platform validation adapter from the monorepo.

## Dataset disclaimer

Results describe only the 22 curated pinned repositories in the v0.2.0
release-validation catalog and are not a product-wide accuracy claim.
