# Epic 11, Slice 11.5 — Provider Usage Metadata and Capability Discovery

Verifies the 12 **new, unwired** `codestrata.ai.provider_contracts.
capability_*`/`usage_*` modules introduced by Slice 11.5 (plus the in-place
extension of `usage.py` with an optional `completion_status` field): a
static, declared-only capability catalog for the two known Engine providers
(bedrock, openai), and extended usage metadata.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A dependency-boundary check that the new modules import no SDK/product modules | A migration of OpenAI or Bedrock to the new capability contract |
| A check that the two static catalog profiles reflect the intentional Slice 11.1 OpenAI/Bedrock structured-JSON difference | A live measurement taken by calling a real provider |
| A compatibility cross-check against the **real**, loaded Slice 11.1 baseline (CR-1..CR-6) plus Slices 11.2/11.3/11.4 non-interference notes | A re-implementation or restatement of any prior slice |
| A privacy check that diagnostics/serialization never leak forbidden usage fields (cost/prompt/response/etc.) | A production logging/telemetry pipeline |
| A confirmation that no product-path file imports the new modules, and that importing them never changes the assess registry/settings | A wiring of capability discovery or usage metadata into `codestrata assess` |
| A record of expected limitations (`provider_capabilities_not_consumed`, `usage_metadata_not_wired`, `providers_not_migrated`, `openrouter_operational_explicit`, `openrouter_doctor_local_readiness_only`) | A fix for those limitations |

No real provider network calls or credentials are used or required.

## Modules

| Module | Verifies |
| --- | --- |
| `contract.py` | Ground-truth constants and the `CapabilityVerificationContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `CapabilityVerificationReport`) |
| `inventory.py` | AST-based structural inventory of `provider_contracts/`; module-set completeness after Slice 11.5 |
| `dependency_boundary.py` | No forbidden SDK/product/environment imports; no product-path import of the new modules; `ai/providers/` untouched |
| `catalogs.py` | The two static baseline capability profiles (bedrock, openai): correct provider coverage, the intentional structured-JSON difference, no streaming, `not_wired_to_runtime` timeout/retry limitation, usage/token reporting |
| `validation.py` | `capability_validation.py`/`usage_validation.py` reject unknown capability IDs, unknown limitations, `supports_streaming=True`, and unknown completion statuses |
| `serialization.py` | Deterministic, sorted-key JSON for both capability and usage views; private/diagnostic usage views are identical; no forbidden field names |
| `privacy.py` | Diagnostics/serialization never include credential-shaped tokens or absolute paths |
| `compatibility.py` | Cross-checks `codestrata.ai.provider_contracts.capability_compatibility` against the **real** `verification.ai_provider_baseline.reporting.build_compatibility_requirements()` (CR-1..CR-6) and against Slice 11.2/11.3/11.4 non-interference notes |
| `runtime_unwired.py` | Importing the new modules never changes the assess provider registry, `AiSettings` defaults, or settings fields |
| `determinism.py` | Canonical JSON helpers used to prove report determinism |
| `scenarios.py` | Negative scenarios A–AC |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–AC)

Each scenario names a condition Slice 11.5 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: no OpenRouter references, no forbidden SDK/environment
imports, no product-path import of the new modules, `ai/providers/`
unchanged, exactly the expected module set present, every Slice 11.1 CR and
every Slice 11.2/11.3/11.4 compatibility note covered and holding, both
catalog profiles declaring `modernization_advisor`, the intentional
OpenAI/Bedrock structured-JSON difference preserved, neither profile
declaring streaming support, timeout/retry policy flags always carrying the
`not_wired_to_runtime` limitation, rejected invalid capability
profiles/completion statuses, no credential-shaped tokens or forbidden usage
field names in serialized output, importing the new modules never changing
the assess registry or settings, no absolute paths or secret-shaped tokens
in the report, and this package never shelling out to a subprocess.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_capabilities
```

Report: `engine/reports/verification/sv11-5/ai-provider-capability-verification.json`
(+ `ai-provider-capability-verification.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_capabilities -q
```

## Report contract

- `schema_name`: `ai-provider-capability-verification`
- `schema_version`: `1.0.0`
- `verdict`: `pass` or `pass_with_limitations` (`fail` if any check/scenario fails)
- `pass_with_limitations` is **expected**: recorded limitations are
  `provider_capabilities_not_consumed`, `usage_metadata_not_wired`,
  `providers_not_migrated`, `openrouter_operational_explicit`, and
  `openrouter_doctor_local_readiness_only` —
  intentional properties of an unwired foundation slice, not defects.

> Since Slice 11.6, `providers_not_migrated` refers to **Bedrock** and the
> orchestration layers, and `provider_capabilities_not_consumed` to everything
> other than the OpenAI adapter, which does consume
> `OPENAI_CAPABILITY_PROFILE`. `ai/providers/openai_provider.py` is therefore
> excluded from this suite's `PRODUCT_PATH_FILES`. See
> [`../openai_provider_migration/README.md`](../openai_provider_migration/README.md).

The report is sanitized before being written: absolute home-directory paths
and secret-shaped tokens are redacted from all check/scenario text and
matrices. Two runs over an unchanged checkout produce byte-identical JSON.

## Boundaries

- Verifies the new capability/usage modules only — does not change AI
  execution, selection, models, credentials, timeouts, retries, fail-soft,
  prompts, reports, Findings, or schemas.
- Does not migrate OpenAI or Bedrock, and does not add OpenRouter (the
  forbidden third-party router-provider name is never spelled out as a
  literal inside `src/codestrata/ai/`; this verification package's own
  `contract.py` — outside `src/` — is the one place the literal appears, for
  scanning purposes).
- Does not modify telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.
- Did not start Slice 11.6 (that migration is verified separately by
  [`../openai_provider_migration/`](../openai_provider_migration/)).
- Not shipped in the `codestrata` wheel.

## Later slices

Slice 11.8 (`ai_provider_cross_provider`) verifies OpenAI and Bedrock against these contracts with **Decision B** (compatibility registry retained). OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
