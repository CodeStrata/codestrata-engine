# Repository Assessment End-to-End Verification (SV.4)

Verification-only suite for the Community assessment journey:

clean non-editable CLI install → `doctor` → `init` → canonical `assess` →
structural artifact validation → source integrity → determinism.

This package is **not** part of the installed `codestrata` wheel.

## Canonical assessment command

```bash
codestrata assess --repo . --output reports --no-ai
```

- `codestrata scan` is a **legacy** entry point (requires `[repository].url`).
- Default mode is deterministic (`--no-ai`); no provider credentials required.
- Telemetry is not transmitted by this workflow.
- Help: `codestrata --help` / `codestrata assess --help` (do not use `codestrata help`).

## Qualification (SV.4A / SV.10A)

Pinned revisions live only in the permanent catalog:

`validation/repository-catalog/catalog.json`

`qualified_revision` uses a full 40-character lowercase commit SHA (optional
`source_tag` is informational). Floating branches are rejected.

SV.10A readiness (population target, pin completeness, roles/tiers, batch plan):

```bash
python validation/repository-catalog/validate_catalog.py --write-readiness-report --write-import-template
```

Validate / qualification report:

```bash
python validation/repository-catalog/validate_catalog.py --write-report
```

Do not start the full SV.10 multi-repository assessment run until the readiness
verdict is PASS. Do not invent repositories to close a population gap.

Remote catalog-backed SV.4:

```bash
cd engine
python -m verification.repository_assessment --with-catalog-network
```


## Selection policy (when revisions exist)

1. `enabled_for.smoke == true`
2. `qualified_revision` present
3. Prefer `Small` candidate category
4. Prefer supported language groups
5. Lexicographically smallest repository `id`

## Local controlled fixture

Uses existing Engine/monorepo fixture:

`test-fixtures/sample-js-app`

This is not a substitute for a catalog-backed pinned repository.

## Run

```bash
cd engine

# Local CI / harness (no network clone)
python -m verification.repository_assessment --local-only

# When a catalog entry has qualified_revision
python -m verification.repository_assessment --with-catalog-network
```

Result:

`reports/verification/repository-assessment-verification.json`

Schema: `repository-assessment-verification` / `1.0.0`

## What SV.4 verifies

| Area | Check |
| --- | --- |
| Install | Non-editable CLI (SV.2 method) |
| Init | `codestrata init` before golden-path assess |
| Assess | Canonical command completes; required artifacts |
| Artifacts | `report.json`, `findings.json`, `recommendations.json`, `report.html` |
| Schema | `report.json` schema version **1.2** (structural) |
| Traceability | Reuses product validators (no second schema) |
| AI | Disabled / not executed |
| Telemetry | No transmission in this workflow |
| Source integrity | Only approved CodeStrata config/output mutations |
| Determinism | Normalized repeat-run comparison |
| Offline | Assessment after clone / local fixture without registries |

## What SV.4 does not do

- Report content/quality review (**SV.5**)
- 30-repository validation
- Rule/analyzer/recommendation tuning
- Product redesign
- Catalog redesign or a second repository list
- Unqualified floating-branch assessments


## Cleanup

Temporary clones and workspaces are deleted unless `--keep-output` is set.
Do not commit clones or generated assessment outputs.
