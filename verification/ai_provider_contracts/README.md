# Epic 11, Slice 11.2 — Common AI Provider Contracts

Verifies the **new, unwired** `codestrata.ai.provider_contracts` package
introduced by Slice 11.2: a provider-neutral, SDK-free set of domain
contracts (requests, results, usage, bounded errors, a minimal synchronous
`AIProvider` protocol, and an explicit deterministic registry) for a
possible future common AI provider platform.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A dependency-boundary check that `provider_contracts` imports no SDK/product modules | A migration of OpenAI or Bedrock to the new contracts |
| A compatibility cross-check against the **real**, loaded Slice 11.1 baseline (CR-1..CR-6) | A re-implementation or restatement of Slice 11.1 |
| A privacy check that diagnostics/serialization never leak prompts/responses/credentials/paths | A production logging/telemetry pipeline |
| A confirmation that no product-path file imports the new package | A wiring of the new contracts into `codestrata assess` |
| A record of expected limitations (`contracts_not_wired_to_runtime`, `providers_not_migrated`) | A fix for those limitations |

No real provider network calls or credentials are used or required.

## Modules

| Module | Verifies |
| --- | --- |
| `contract.py` | Ground-truth constants and the `ContractVerificationContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `ContractVerificationReport`) |
| `inventory.py` | AST-based structural inventory of `provider_contracts/`; module-set completeness |
| `dependency_boundary.py` | No forbidden SDK/product imports; no product-path import of the new package; `ai/providers/` untouched |
| `baseline_compatibility.py` | Cross-checks `codestrata.ai.provider_contracts.compatibility` against the **real** `verification.ai_provider_baseline.reporting.build_compatibility_requirements()` (CR-1..CR-6) |
| `privacy.py` | Diagnostics/serialization never include prompt/response/credential/path text |
| `determinism.py` | Canonical JSON helpers used to prove report determinism |
| `scenarios.py` | Negative scenarios A–Z, including direct construction-time invariant checks (`run_value_object_negative_checks`) |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–Z)

Each scenario names a condition Slice 11.2 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: no OpenRouter references, no forbidden SDK imports, no
product-path import of the new package, `ai/providers/` unchanged, exactly
`bedrock`/`openai`/`openrouter` as `ProviderId` values (assess registration stays
bedrock+openai), every Slice 11.1 CR covered by a
compatibility statement that holds, diagnostics/serialization free of
prompts/responses/credentials/paths, rejected payload/capability mismatches,
rejected unsupported contract versions, rejected inconsistent usage totals,
rejected raw-exception-shaped error detail, `SUCCESS` results forbidding an
attached error, `FAILED`/`UNAVAILABLE` results requiring one, the registry
rejecting duplicate registration and raising for unknown provider IDs, no
absolute paths or secret-shaped tokens in the report, and this package never
shelling out to a subprocess.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_contracts
```

Report: `engine/reports/verification/sv11-2/ai-provider-contract-verification.json`
(+ `ai-provider-contract-verification.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_contracts -q
```

## Report contract

- `schema_name`: `ai-provider-contract-verification`
- `schema_version`: `1.0.0`
- `verdict`: `pass` or `pass_with_limitations` (`fail` if any check/scenario fails)
- `pass_with_limitations` is **expected**: recorded limitations are
  `contracts_not_wired_to_runtime` and `providers_not_migrated` — intentional
  properties of an unwired foundation slice, not defects.

> Since Slice 11.6, `providers_not_migrated` refers to **Bedrock** and the
> orchestration layers. OpenAI is migrated and is deliberately excluded from
> this suite's `PRODUCT_PATH_FILES`, which is the list of files that must not
> import the contracts. See
> [`../openai_provider_migration/README.md`](../openai_provider_migration/README.md).

The report is sanitized before being written: absolute home-directory paths
and secret-shaped tokens are redacted from all check/scenario text and
matrices. Two runs over an unchanged checkout produce byte-identical JSON.

## Boundaries

- Verifies the new contracts only — does not change AI execution, selection,
  models, credentials, timeouts, retries, fail-soft, prompts, reports,
  Findings, or schemas.
- Does not migrate OpenAI or Bedrock, and does not add OpenRouter.
- Does not modify telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.
- Does not start Slice 11.3.
- Not shipped in the `codestrata` wheel.

## Later slices

Slice 11.8 (`ai_provider_cross_provider`) verifies OpenAI and Bedrock against these contracts with **Decision B** (compatibility registry retained). OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
