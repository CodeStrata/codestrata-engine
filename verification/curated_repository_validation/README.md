"""SV.10 — Validate 22 Curated OSS Repositories

Verification-only package for System Verification slice SV.10.

## Scope

- Permanent catalog: `validation/repository-catalog/catalog.json`
- v0.2.0 target: exactly **22** release_validation repositories
- Requires catalog readiness verdict **PASS** (SV.10A/SV.10B)
- Does **not** start SV.11

Results describe only this curated dataset and are **not** a product-wide
accuracy claim.

## Canonical workflow (per repository)

```bash
codestrata doctor
codestrata init
codestrata assess --repo . --output reports --no-ai
```

No dependency installation, builds, repository tests, submodule init, or Git LFS.

## Commands

```bash
cd engine

# One tier at a time (recommended)
python -m verification.curated_repository_validation --tier tier1
python -m verification.curated_repository_validation --tier tier2
python -m verification.curated_repository_validation --tier tier3
python -m verification.curated_repository_validation --tier tier4

# Full dataset + determinism samples
python -m verification.curated_repository_validation --all
```

Outputs (gitignored under `reports/`):

```
engine/reports/verification/sv10/
  tier1-summary.json
  tier2-summary.json
  tier3-summary.json
  tier4-summary.json
  curated-repository-validation.json
  records/<repository_id>.json
  artifacts/<repository_id>/<sha12>/
```

## Batches

Batch membership is resolved from catalog `expected_runtime_tier` metadata.
Do not hardcode repository lists in runtime code.

Timeouts:

| Tier | Assess timeout |
| --- | --- |
| tier1 | 5 minutes |
| tier2 | 15 minutes |
| tier3 | 20 minutes |
| tier4 | 30 minutes |

## Relationship

| Slice | Role |
| --- | --- |
| SV.10A/B | Catalog readiness gate |
| SV.10 | This multi-repository assessment run |
| SV.11 | Broader consistency analysis |
| SV.12 | Engineering Intelligence editorial review |
| SV.13 | Defect remediation |
