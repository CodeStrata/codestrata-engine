# Epic 11, Slice 11.3 — Standardized Provider and Model Configuration

Verifies the **new, unwired** `codestrata.ai.provider_contracts.configuration_*`
modules introduced by Slice 11.3: a standardized, privacy-preserving
representation of "what `codestrata assess` would use for an AI provider"
(provider ID, model reference, adapter configuration, credential
requirements, source trace) as pure, injected-input domain types.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A dependency-boundary check that configuration modules import no SDK/product modules, and never `os`/`pathlib`/`subprocess` | A migration of OpenAI or Bedrock to the new configuration types |
| A compatibility cross-check against the **real**, loaded Slice 11.1 baseline (CR-1..CR-6), including default provider/model IDs | A change to default provider, default models, or resolution precedence |
| A correctness cross-check of `resolve_provider_id`/`resolve_model_reference` against the **real** `resolve_assess_model_id` | A wiring of the new configuration types into `codestrata assess` |
| A privacy check that diagnostics/serialization never leak model values, credentials, `base_url`, or paths | A production logging/telemetry pipeline |
| A confirmation that no product-path file (assess factory, providers, enrichment, doctor, CLI, config layer) imports the new modules | A new `AIProvider` protocol implementation |
| A record of expected limitations (`configuration_not_wired`, `providers_not_migrated`, `credential_resolution_deferred`, `timeout_retry_execution_deferred`) | A fix for those limitations |

No real provider network calls or credentials are used or required.

## Modules

| Module | Verifies |
| --- | --- |
| `contract.py` | Ground-truth constants and the `ConfigurationVerificationContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `ConfigurationVerificationReport`) |
| `inventory.py` | AST-based structural inventory; confirms all 12 Slice 11.3 modules exist alongside the Slice 11.2 set |
| `dependency_boundary.py` | No forbidden SDK/product imports; configuration modules never import `os`/`pathlib`/`subprocess`; no product-path import; `ai/providers/` untouched |
| `baseline_compatibility.py` | Cross-checks `configuration_compatibility` against the **real** `verification.ai_provider_baseline.reporting.build_compatibility_requirements()` (CR-1..CR-6), and default provider/model IDs against the loaded baseline |
| `provider_selection.py` | `resolve_provider_id` matches `AiSettings` default and the real factory's normalization behavior |
| `model_resolution.py` | `resolve_model_reference` matches the real `resolve_assess_model_id` for both providers, including the `CODESTRATA_BEDROCK_MODEL_ID` re-read-at-resolution-time asymmetry |
| `credentials.py` | Credential-requirement shape: bounded kind/status, never a value, correct per-provider requirements |
| `adapter_configuration.py` | Adapter type safety (mismatch rejection) and no invented fields (no `organization`/`project`/`endpoint_url`) |
| `privacy.py` | Diagnostics/serialization never include model values, `base_url` values, or credential values |
| `runtime_unwired.py` | Importing configuration modules never touches the assess registry or changes settings defaults |
| `determinism.py` | Canonical JSON helpers and repeated-resolution stability checks |
| `scenarios.py` | Negative scenarios A–Z, including direct construction-time invariant checks (`run_value_object_negative_checks`) |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–Z)

Each scenario names a condition Slice 11.3 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: no OpenRouter references, no `os`/`pathlib`/`subprocess`
imports in configuration modules, no product-path import of the new modules,
`ai/providers/` unchanged, `ProviderId` includes `bedrock`/`openai`/`openrouter`
(assess registry remains bedrock+openai),
every Slice 11.1 CR covered by a configuration compatibility statement that
holds, default provider/model IDs matching the loaded baseline, diagnostics
free of raw model/`base_url`/credential values, all 12 new modules present,
rejected adapter/provider type mismatches, rejected unsupported
`configuration_version`, rejected empty `limitations`, rejected
credential-requirement provider mismatches, rejected unsupported provider
names, no absolute paths or secret-shaped tokens in the report, and this
package never shelling out to a subprocess.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_configuration
```

Report: `engine/reports/verification/sv11-3/ai-provider-configuration-verification.json`
(+ `ai-provider-configuration-verification.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_configuration -q
```

## Report contract

- `schema_name`: `ai-provider-configuration-verification`
- `schema_version`: `1.0.0`
- `verdict`: `pass` or `pass_with_limitations` (`fail` if any check/scenario fails)
- `pass_with_limitations` is **expected**: recorded limitations are
  `configuration_not_wired`, `providers_not_migrated`,
  `credential_resolution_deferred`, and `timeout_retry_execution_deferred` —
  intentional properties of an unwired configuration slice, not defects.

> Since Slice 11.6, `providers_not_migrated` refers to **Bedrock** and the
> orchestration layers. OpenAI is migrated and is deliberately excluded from
> this suite's `PRODUCT_PATH_FILES`, which is the list of files that must not
> import the contracts. See
> [`../openai_provider_migration/README.md`](../openai_provider_migration/README.md).

The report is sanitized before being written: absolute home-directory paths
and secret-shaped tokens are redacted from all check/scenario text and
matrices. Two runs over an unchanged checkout produce byte-identical JSON.

## Boundaries

- Verifies the new configuration modules only — does not change provider
  selection, defaults, model resolution precedence, config keys, timeouts,
  retries, doctor, CLI, or AI execution.
- Does not migrate OpenAI or Bedrock, does not add OpenRouter, and does not
  wire the configuration types to the `AIProvider` protocol.
- Does not modify telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.
- Not shipped in the `codestrata` wheel.

## Successor

Epic 11, Slice 11.4 (started; see
[`engine/verification/ai_provider_execution/README.md`](../ai_provider_execution/README.md))
extends the same `codestrata.ai.provider_contracts` package with a
standardized, unwired execution/retry/timeout/backoff shape, likewise
cross-checked against every CR-1..CR-6 and against this package's default
provider/model IDs. Slice 11.4 does not change anything characterized by
this package.

## Later slices

Slice 11.8 (`ai_provider_cross_provider`) verifies OpenAI and Bedrock against these contracts with **Decision B** (compatibility registry retained). OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
