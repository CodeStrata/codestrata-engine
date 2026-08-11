# Epic 11, Slice 11.1 — Existing AI Architecture and Compatibility Baseline

Characterization-only verification suite. It **freezes the current behavior**
of the existing Engine AI provider architecture (Bedrock + OpenAI assess
providers) as a compatibility baseline for Slice 11.2+ work. It does not
change any AI behavior and does not introduce a new provider interface,
provider platform, or registry redesign.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A read-only inventory + characterization of the existing `bedrock`/`openai` assess providers | A new common `AIModelProvider` platform or registry redesign |
| A frozen record of current defaults, error mapping, fail-soft, and doctor behavior | A migration of OpenAI or Bedrock to any new interface |
| A list of `compatibility_requirements` for **future** Slice 11.2+ work | An implementation of those requirements |
| A record of a known limitation (`timeout_seconds`/`max_retries` settings are declared but not wired into the assess provider factory) | A fix for that limitation |

No real credentials are used and no provider network calls are made — all
credential/client boundaries are mocked or exercised via pure, in-memory
request/response construction using the real Engine source.

## Verified product behavior (current, ground truth)

| Topic | Behavior |
| --- | --- |
| Engine assess provider IDs | `bedrock` (default), `openai`, `openrouter` (explicit-only) |
| Analytics `provider_family` mapping | `bedrock` → `aws_bedrock`; `openai` → `openai` (Engine ID is unaffected) |
| Default models | Bedrock `amazon.nova-lite-v1:0`; OpenAI `gpt-4o-mini` |
| Invocation defaults | `timeout_seconds=60.0`, `temperature=0.0`, `max_output_tokens=8192` (`ai/providers/models.py`) |
| Modernization Advisor override | `max_output_tokens=5000` for the assess path |
| Settings wiring gap | `[ai.bedrock]`/`[ai.openai]` `timeout_seconds`/`max_retries` exist in settings but are **not** read by `extensions/assess_ai.py` when constructing assess providers |
| Invoke count | Exactly one `provider.invoke()` call per assess run; `ai/providers/common.py::retry_call` exists but is unused by either provider |
| Existing abstraction | `AIModelProvider` ABC + `AssessAIProviderRegistry` (inventoried, not expanded) |
| Fail-soft | An AI provider/parsing/validation failure keeps `codestrata assess` at exit 0 whenever deterministic reports are written |
| Doctor | `codestrata ai doctor` / `build_ai_configuration_report()` — readiness only, never invokes a model |
| Optional extras | `codestrata[bedrock]` → `boto3`; `codestrata[openai]` → `openai` |
| Product path | `AiEnrichmentService` (Modernization Advisor), not a legacy agent |
| Assessment schema | Unchanged, `1.2` |

## Modules

| Module | Characterizes |
| --- | --- |
| `contract.py` | Ground-truth constants and the `BaselineContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `BaselineReport`, ...) |
| `inventory.py` | AST-based structural coupling inventory of existing AI provider modules |
| `provider_selection.py` | Default provider, supported providers, unsupported-provider errors, model ID resolution precedence |
| `configuration.py` | AI-relevant Pydantic settings defaults |
| `authentication.py` | Credential/auth boundary characterization (mocked; no real network) |
| `requests.py` | Bedrock Converse / OpenAI Chat Completions request-shape characterization |
| `responses.py` | Provider response extraction from synthetic payloads |
| `timeouts.py` | Timeout defaults and the settings-to-factory wiring gap |
| `retries.py` | Retry behavior and the `retry_call` non-usage finding |
| `errors.py` | Exception hierarchy and per-provider error-mapping matrices |
| `diagnostics.py` | `codestrata ai doctor` readiness-only behavior |
| `doctor.py` | Thin re-export of doctor characterization from `diagnostics.py` |
| `usage.py` | Token usage extraction/normalization |
| `capabilities.py` | Model capability defaults and `ModelInvocationOptions` bounds |
| `fail_soft.py` | Fail-soft contract (customer messages, exit-0 preservation) |
| `assessment_integration.py` | `AiEnrichmentService` / assess integration invariants |
| `reporting_integration.py` | `AIExecutionStatus` / execution-document reporting integration |
| `boundaries.py` | Slice 11.1 hard-constraint boundaries (no OpenRouter, no new provider platform, ...) |
| `determinism.py` | Canonical JSON / stable-hash helpers used to prove report determinism |
| `scenarios.py` | Negative scenarios A–Z: forbidden conditions that must **not** hold |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–Z)

Each scenario names a condition Slice 11.1 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: no real network calls, no OpenRouter references, no new
common provider interface, no unexpected files under `ai/providers/`, settings
`timeout_seconds`/`max_retries` not silently wired in, exactly one
`invoke()` call per assess run, no secret-shaped tokens or absolute paths in
the report, and this package itself never shells out to `git commit`.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_baseline
```

Report: `engine/reports/verification/sv11-1/ai-provider-compatibility-baseline.json`
(+ `ai-provider-compatibility-baseline.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_baseline -q
```

## Report contract

- `schema_name`: `ai-provider-compatibility-baseline`
- `schema_version`: `1.0.0`
- `verdict`: `pass` or `pass_with_limitations` (`fail` if any check/scenario fails)
- `pass_with_limitations` is **expected** without live credentials/network; recorded
  limitations are `no_live_provider_calls`, `no_real_credentials`, and
  `settings_timeout_max_retries_not_wired_to_assess_factory`.

The report is sanitized before being written: absolute home-directory paths
(`/Users/...`, `/home/...`) and secret-shaped tokens (`sk-...`, `AKIA...`,
`Bearer ...`) are redacted from all check/scenario text, matrices, and the
coupling inventory. Two runs over an unchanged checkout produce byte-identical
JSON.

## Boundaries

- Characterization only — does not change AI execution, selection, models,
  credentials, timeouts, retries, fail-soft, prompts, reports, Findings, or
  schemas.
- Does not introduce a common provider interface, provider platform, or
  registry redesign, and does not migrate OpenAI or Bedrock.
- Does not add OpenRouter.
- Does not modify Community Cloud, Data Lake, Anonymous Analytics, VS Code,
  Cursor, or infrastructure.
- Does not start Slice 11.2.
- Not shipped in the `codestrata` wheel.

## Successor

Epic 11, Slice 11.2 (started; see
[`engine/verification/ai_provider_contracts/README.md`](../ai_provider_contracts/README.md))
introduces a new, unwired `codestrata.ai.provider_contracts` domain package
that stays compatible with every `CompatibilityRequirement` (CR-1..CR-6)
recorded above — loaded directly from `build_compatibility_requirements()`
by the Slice 11.2 verification suite, not restated by hand. Slice 11.2 does
not change anything characterized by this package.

Epic 11, Slice 11.3 (started; see
[`engine/verification/ai_provider_configuration/README.md`](../ai_provider_configuration/README.md))
extends the same package with a standardized, privacy-preserving
configuration representation, likewise cross-checked against every CR-1..CR-6
recorded above and against this package's default provider/model IDs. Slice
11.3 does not change anything characterized by this package either.

Epic 11, Slice 11.4 (started; see
[`engine/verification/ai_provider_execution/README.md`](../ai_provider_execution/README.md))
extends the same package with a standardized, unwired execution/retry/
timeout/backoff shape and an `AIProviderExecutor`, likewise cross-checked
against every CR-1..CR-6 recorded above and against this package's default
timeout/`max_retries` values. Slice 11.4 does not change anything
characterized by this package either.

## Later slices

Slice 11.8 (`ai_provider_cross_provider`) verifies OpenAI and Bedrock against these contracts with **Decision B** (compatibility registry retained). OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
