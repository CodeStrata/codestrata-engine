# Assessment Report Verification (SV.5)

Verification-only suite for assessment **artifact quality and integrity** after
SV.4 has proven the end-to-end workflow.

This package is **not** part of the installed `codestrata` wheel.

## Relationship to SV.4

| Slice | Focus |
| --- | --- |
| SV.4 | Workflow: install → init → assess → artifacts exist, structurally valid |
| SV.5 | Report quality: schema, parity, HTML, traceability, credibility, privacy |
| SV.6 | CLI UX (not this suite) |
| SV.12 | Deeper quality review (not this suite) |

SV.5 prepares inputs by invoking the **existing SV.4 assessment helpers**
(catalog, clone, assess). It does not invent a second assessment workflow or
hardcode repository URLs.

## Inputs

1. Controlled local fixture (`test-fixtures/sample-js-app`)
2. Catalog-backed smoke repository (policy-selected; currently `cleanarchitecture`)

Permanent catalog: `validation/repository-catalog/catalog.json`

## Required artifacts

- `report.json` (schema **1.2**)
- `findings.json`
- `recommendations.json`
- `report.html`

## Checks

- Structural `report.json` via product `validate_report_json`
- Traceability via product canonical validators
- Companion JSON parity with `report.json`
- HTML DOCTYPE/CSP/`script-src 'none'`/print CSS/unique anchors/section order
- Coverage / Confidence / Limitations separation; no validation Precision/Recall
- Disclaimer-aware unsupported-claim scan
- Privacy scan (secrets, absolute paths, source bodies)
- Deterministic render compare on local fixture repeat
- Model-level negative/empty-state honesty checks

## Run

```bash
cd engine

# Local fixture report only
python -m verification.assessment_report --local-only

# Include catalog-backed remote assessment report
python -m verification.assessment_report --with-catalog-network

# Reuse existing run directories
python -m verification.assessment_report --artifact-dir path/to/run
```

Result: `reports/verification/assessment-report-verification.json`

Schema: `assessment-report-verification` / `1.0.0`

## Limitations

- Does not judge whether every Finding/Recommendation is analytically correct
- Does not tune rules, thresholds, or redesign reports
- Does not start Engineering Intelligence verification or 30-repository runs
