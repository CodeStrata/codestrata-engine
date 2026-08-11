# Standardized Execution, Errors, Timeouts, and Retries (Epic 11, Slice 11.4)

> **Status: foundation, consumed by OpenAI and Bedrock.** Since Slices 11.6 and
> 11.7 both adapters run under `AIProviderExecutor` with `DEFAULT_RETRY_POLICY`
> (`maximum_attempts=1`) and `DEFAULT_TIMEOUT_POLICY` (60s, still declarative
> at the executor; wall-clock enforcement remains client-owned) — see
> [`ai-provider-openai.md`](ai-provider-openai.md),
> [`ai-provider-bedrock.md`](ai-provider-bedrock.md), and
> [`ai-provider-platform.md`](ai-provider-platform.md). No CodeStrata-stacked
> retry is performed by default. See [`ai-enrichment.md`](ai-enrichment.md) for
> fail-soft ownership, and
> [`ai-provider-contracts.md`](ai-provider-contracts.md) /
> [`ai-provider-configuration.md`](ai-provider-configuration.md) for Slices
> 11.2/11.3, and [`ai-provider-capabilities.md`](ai-provider-capabilities.md)
> for Slice 11.5.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.4 adds a standardized, provider-neutral
**execution shape** for running one `AIProviderRequest` against one
`AIProvider`: bounded timeout/retry/backoff policies, a pure retry-decision
function, safe error classification, and an `AIProviderExecutor` that ties
them together — all as pure, injected-input domain types under
`codestrata.ai.provider_contracts` (the same Slice 11.2/11.3 sibling
package, not `codestrata.ai.providers`).

This slice is **not** (Slice 11.6 later wired the first two of these for
OpenAI only):

* A migration of the OpenAI or Bedrock providers to use `AIProviderExecutor`.
* A wiring of the executor into `codestrata assess`, `AiEnrichmentService`,
  the provider factory, or `codestrata ai doctor`.
* A change to any default, provider selection, credential, wire format,
  fail-soft behavior, prompt, report, or schema.
* Real wall-clock timeout enforcement — `AIProviderExecutor` never starts a
  thread, installs a signal handler, or uses `asyncio`.
* OpenRouter or any third-party LLM routing/aggregation support *in this
  slice* (OpenRouter arrives in Slices 11.9/11.10 — see
  [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md)).

It is a Slice 11.1/11.2/11.3-compatible foundation that a future slice
(11.5+, **not started here**) could build a real, enforced execution path
against, without changing anything about how `codestrata assess --with-ai`
behaves today.

## Ground truth this slice restates (and does not change)

Verified against `codestrata.ai.providers.models`,
`codestrata.ai.providers.factory`, `codestrata.ai.enrichment`, and Slice
11.1's baseline compatibility requirements — not invented:

* **`AIProvider.execute(request) -> AIProviderResult`** never changes — the
  protocol still returns a `FAILED`/`UNAVAILABLE` result with an
  `AIProviderError` for expected failures rather than raising. The executor
  only *wraps* a provider that already honors this contract.
* **`ErrorCategory`** (from `errors.py`) is reused unchanged and is the only
  source of failure-category values; this slice partitions it into
  retryable/non-retryable but never redefines it.
* **CR-1 — exactly one `AIProvider.execute()` call per assess run today** —
  `DEFAULT_RETRY_POLICY` has `maximum_attempts=1`, so the executor's default
  configuration never retries, matching current production behavior exactly.
* **`DEFAULT_TIMEOUT_SECONDS = 60.0`** — restated from
  `codestrata.ai.providers.models` as a literal (this package has zero
  `codestrata` dependencies outside itself); `TimeoutPolicy`'s default
  matches it.
* **`max_retries` on `BedrockSettings`/`OpenAISettings` defaults to `3`,
  unwired** — restated as `SETTINGS_DEFAULT_MAX_RETRIES = 3`, used only to
  build `SETTINGS_REPRESENTABLE_RETRY_POLICY` (`maximum_attempts=4`), a pure
  representation that activates nothing.
* **Slice 11.3's `maximum_attempts = max_retries + 1` conversion** is now a
  standalone, reusable helper: `max_retries_to_maximum_attempts()`.

## Why a sibling package, not `ai/providers/`?

Same rationale as Slices 11.2/11.3 (see
[`ai-provider-contracts.md`](ai-provider-contracts.md)):
`codestrata.ai.providers` hosts the concrete, wired adapter surface that
`codestrata assess` depends on today, and Slice 11.1 inventories its exact
file set as part of its compatibility baseline. Extending
`codestrata.ai.provider_contracts` keeps this new execution shape next to
the request/result/configuration types it is meant to eventually pair with,
without touching either the wired `ai/providers/` tree or the already
verified Slice 11.2/11.3 module sets.

## Package layout (Slice 11.4 additions)

```text
engine/src/codestrata/ai/provider_contracts/
├── execution_policy.py         Policy IDs, allowed timeout/backoff sets, default retryable partition
├── timeout_policy.py           TimeoutPolicy, TimeoutScope (provider_request/total_execution)
├── retry_policy.py             AIProviderRetryPolicy, max_retries_to_maximum_attempts()
├── backoff.py                  BackoffPolicy, BackoffStrategy (none/fixed/exponential), delay helper
├── retry_decision.py           Pure decide_retry() -> RetryDecision (never sleeps)
├── error_classification.py     ProviderErrorClassification, classification helpers
├── execution_models.py         AIProviderExecutionContext, AIProviderExecutionResult
├── executor.py                 AIProviderExecutor — the standardized, unwired execution/retry loop
├── execution_diagnostics.py    Privacy-safe diagnostic view of an execution result
├── execution_serialization.py  Deterministic JSON: private vs. diagnostic execution views
└── execution_compatibility.py  Slice 11.1 CR-1..CR-6 statements + version helpers
```

These 11 modules sit alongside, and depend only downward on, the Slice
11.2/11.3 modules (`identifiers.py`, `requests.py`, `responses.py`,
`errors.py`, `provider.py`, `execution.py`, `usage.py`,
`configuration_sources.py`). No Slice 11.2/11.3 module is modified to depend
on Slice 11.4, and `execution.py`'s existing `ProviderExecutionStatus` enum
is reused unchanged (not duplicated).

Zero imports from the rest of `codestrata` cross into these modules from
outside the package, and none of them import `codestrata.ai.providers`,
`codestrata.extensions`, `codestrata.reporting`, `codestrata.telemetry`,
`codestrata.analytics`, `codestrata.platform`, `codestrata.datalake`,
`codestrata.cli`, `os`, `pathlib`, `subprocess`, `threading`, `asyncio`,
`signal`, or `openai`/`boto3`/`botocore`/`httpx`/`requests`. This is
enforced by `engine/tests/ai/provider_contracts/test_execution_runtime_unwired.py`
and by the SV.11.4 verification suite's `dependency_boundary.py`.

## Contract identity

| Identifier | Value |
| --- | --- |
| Policy | `community-ai-provider-execution-policy:1.0` |
| Contract | `community-ai-provider-execution:1.0` |
| Contract / execution version | `1.0` |
| Timeout scopes | `provider_request`, `total_execution` |
| Backoff strategies | `none`, `fixed`, `exponential` |
| Default timeout | `60.0` seconds, scope `provider_request`, `enabled=True` |
| Default retry policy | `maximum_attempts=1` (CR-1: no CodeStrata-level retries) |
| Settings-representable retry policy | `maximum_attempts=4` (pure representation of `max_retries=3`) |
| Default retryable categories | `timeout`, `rate_limited`, `provider_unavailable` |
| Default non-retryable categories | `missing_configuration`, `dependency_unavailable`, `authentication_failed`, `authorization_failed`, `invalid_model`, `invalid_request`, `invalid_response`, `parsing_failed`, `internal_failure` |

`execution` contract version is a distinct version namespace from Slice
11.2's `versions.CURRENT_CONTRACT_VERSION` and Slice 11.3's
`configuration_version`, even though all three currently equal `"1.0"`. See
`execution_compatibility.py`.

## Core design: `maximum_attempts` vs. `max_retries`

`maximum_attempts` (on `AIProviderRetryPolicy`) is the **canonical** field
name throughout this slice, and always **includes the first, non-retry
attempt** — a policy with `maximum_attempts=1` makes exactly one call and
never retries. This is deliberately different from the *settings*-shaped
`max_retries` field (Slice 11.3's `BedrockAdapterConfiguration.max_retries`
/ `OpenAIAdapterConfiguration.max_retries`), which counts retries only,
excluding the first attempt.

```python
from codestrata.ai.provider_contracts.retry_policy import max_retries_to_maximum_attempts

max_retries_to_maximum_attempts(0)  # -> 1 (no retries)
max_retries_to_maximum_attempts(3)  # -> 4 (first attempt + 3 retries)
```

Two ready-made policies:

* **`DEFAULT_RETRY_POLICY`** (`maximum_attempts=1`) — matches CR-1's
  existing "exactly one `AIProvider.execute()` call per assess run"
  behavior. This is what `AIProviderExecutor` uses by default.
* **`SETTINGS_REPRESENTABLE_RETRY_POLICY`** — a *pure representation* of
  what `BedrockSettings.max_retries`/`OpenAISettings.max_retries`'s default
  value (`3`) would mean if it were ever wired up (`maximum_attempts=4`).
  Building this value object activates nothing: no executor uses it by
  default, and nothing reads the real settings value to construct it.

## Core design: timeouts are declared, never enforced here

`TimeoutPolicy(timeout_seconds=60.0, scope=TimeoutScope.PROVIDER_REQUEST,
enabled=True)` is the default, representable timeout. `AIProviderExecutor`
does **not** enforce a wall-clock timeout itself — no threads, no signals,
no `asyncio`. Instead, `AIProviderExecutionResult.timeout_applied` only
records whether a provider-reported `ErrorCategory.TIMEOUT` was observed on
any attempt. Real wall-clock enforcement (e.g. an `httpx`/`boto3` client
constructed with this value) is deferred to a future provider-adapter, out
of scope for this slice.

## Core types

### `BackoffPolicy` / `compute_backoff_delay` (`backoff.py`)

Three strategies: `none` (always zero), `fixed` (constant delay),
`exponential` (`base_delay_seconds * multiplier ** (attempt - 1)`, capped at
`max_delay_seconds`). `jitter` is disabled by default so delay computation
stays fully deterministic; when enabled, the jitter factor is derived only
from `attempt` via a seeded `random.Random`, never from wall-clock time, so
results stay reproducible. `compute_backoff_delay` never sleeps.

### `RetryDecision` / `decide_retry` (`retry_decision.py`)

A pure function of its arguments — given the attempt number that just
failed, its `ErrorCategory`, a retry policy, and a backoff policy, it
returns whether to retry, the next attempt number, and how long to wait
first:

```python
from codestrata.ai.provider_contracts.backoff import DEFAULT_BACKOFF_POLICY
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.retry_decision import decide_retry
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy

decision = decide_retry(
    attempt=1,
    category=ErrorCategory.TIMEOUT,
    retry_policy=AIProviderRetryPolicy(maximum_attempts=3),
    backoff_policy=DEFAULT_BACKOFF_POLICY,
)
# decision.should_retry is True, decision.next_attempt == 2
```

Never sleeps, never reads a clock, never mutates its arguments.

### `ProviderErrorClassification` (`error_classification.py`)

Never carries raw exception text or SDK exception class names — only the
already-bounded `ErrorCategory`, whether the configured retry policy
considers it retryable, and a short, fixed "safe code". For an unexpected
exception (a contract violation — `AIProvider.execute()` is documented to
never raise for expected failures), `classify_unexpected_exception` always
returns `ErrorCategory.INTERNAL_FAILURE` with the fixed
`UNEXPECTED_EXCEPTION_SAFE_CODE` literal, never the exception's message or
type name.

### `AIProviderExecutor` (`executor.py`)

```python
from codestrata.ai.provider_contracts.executor import AIProviderExecutor

executor = AIProviderExecutor(provider)  # DEFAULT_RETRY_POLICY: no retries
result = executor.execute(request)
# result.status, result.attempts, result.retry_count, result.timeout_applied, ...
```

Behavior:

* Confirms `provider.supports(capability)` before ever calling `execute()`;
  when unsupported, returns a `SKIPPED` result without invoking the
  provider (zero attempts).
* On a `FAILED`/`UNAVAILABLE` result whose error category is retryable
  under the configured `AIProviderRetryPolicy` (and while attempts remain
  under `maximum_attempts`), uses `decide_retry` to decide whether to
  retry, calling the injected `sleeper` with the computed backoff delay
  before the next attempt.
* Validates that the `AIProviderResult` returned by `execute()` reports the
  same `provider_id` as the provider itself — a contract violation
  otherwise (`ProviderContractValidationError`).
* Catches any unexpected `Exception` raised by `execute()` and converts it
  into a synthetic `FAILED` result classified as `internal_failure`,
  never inspecting the exception's message, type, or traceback.
  `KeyboardInterrupt`/`SystemExit` do not subclass `Exception` and always
  propagate unmodified.
* Never reads `os.environ` or a configuration file, never constructs a
  provider client, and never mutates a report.
* `clock`, `sleeper`, `timeout_policy`, `retry_policy`, and `backoff_policy`
  are all injectable constructor arguments — production code paths never
  call the real `time.sleep` because nothing in the product path
  constructs an `AIProviderExecutor` at all.

### `AIProviderExecutionResult` (`execution_models.py`)

`provider_id`, `capability`, `status` (`ProviderExecutionStatus`),
`provider_result` (optional `AIProviderResult`), `attempts`, `retry_count`
(always `attempts - 1`), `terminal_error_category`, `timeout_applied`
(bool), `usage` (optional), `diagnostics` (`ExecutionDiagnostics`),
`limitations` (always `executor.EXECUTOR_LIMITATIONS`, non-empty).
Extensively self-validated at construction: a `SUCCESS` result must carry a
matching `SUCCESS` `provider_result` and no `terminal_error_category`; a
`FAILED`/`UNAVAILABLE` result must carry a matching `provider_result` and a
`terminal_error_category`; a pre-flight `SKIPPED` result (no
`provider_result`) must record zero attempts/retries.

Diagnostic/public serialization always omits `provider_result.content`.

## Compatibility with the Slice 11.1 baseline (CR-1..CR-6)

`execution_compatibility.py` restates the six Slice 11.1 compatibility
requirement IDs (as literals, without importing the verification package)
and records why the execution domain types do not violate each one:

| Requirement | How the execution domain stays compatible |
| --- | --- |
| **CR-1** — exactly one invoke per assess run | `DEFAULT_RETRY_POLICY` has `maximum_attempts=1`; `AIProviderExecutor` is never constructed by `AiEnrichmentService.run()` |
| **CR-2** — settings timeout/retries wiring must stay explicit | `SETTINGS_REPRESENTABLE_RETRY_POLICY` is a pure, inert representation; nothing reads the real settings fields and forwards them to a live executor |
| **CR-3** — fail-soft must be preserved | The executor never raises for an expected provider failure — those surface as a terminal `FAILED`/`UNAVAILABLE` result; only contract violations (bad protocol return) raise |
| **CR-4** — Engine provider IDs stay stable | `ProviderId` is reused unchanged from Slice 11.2; the executor validates result `provider_id` matches the wrapped provider's |
| **CR-5** — no real network/credentials required | The executor calls only the already-constructed `provider`/`request` arguments; it never reads `os.environ`, reads a file, or constructs a provider client |
| **CR-6** — defaults change only via explicit decision | `DEFAULT_TIMEOUT_SECONDS`/`DEFAULT_MAXIMUM_ATTEMPTS`/the retryable partition are literal restatements of real production behavior, unchanged by this slice |

The **enforcement** of this table — loading the real
`build_compatibility_requirements()` from
`verification.ai_provider_baseline.reporting` and cross-checking it, plus
cross-checking `DEFAULT_TIMEOUT_SECONDS`/`SETTINGS_DEFAULT_MAX_RETRIES`
against the real settings defaults — lives in
[`engine/verification/ai_provider_execution/baseline_compatibility.py`](../verification/ai_provider_execution/baseline_compatibility.py),
never in the production `src` package.

## Privacy

Diagnostics (`execution_diagnostics.py`) and the diagnostic serialization
path (`execution_serialization.py`) never include: `provider_result`'s
`content`, the underlying `AIProviderError.detail` text, an unexpected
exception's message/type/traceback, or filesystem paths — only bounded
category/status/count/policy-shape data. A separate
`private_view_of_execution_result`/private serialization exists for
internal test/debugging use only and must never be written to a log,
report, or CLI output. See
`engine/tests/ai/provider_contracts/test_execution_privacy.py` and
`engine/verification/ai_provider_execution/privacy.py`.

## Verification

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_execution
```

Report: `engine/reports/verification/sv11-4/ai-provider-execution-verification.json`.
Schema: `ai-provider-execution-verification` @ `1.0.0`. Verdict:
`pass_with_limitations` is expected — recorded limitations are
`executor_not_wired`, `providers_not_migrated`,
`timeout_enforcement_deferred_to_adapters`, and
`runtime_settings_still_unwired`, intentional properties of this slice, not
defects. See
[`engine/verification/ai_provider_execution/README.md`](../verification/ai_provider_execution/README.md).

## Unit tests

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_contracts -q
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_execution -q
```

Fake providers for executor testing live in
`engine/tests/ai/provider_contracts/execution_fakes.py` — never in `src/`.

## Related

- [ai-enrichment.md](ai-enrichment.md) — the actual, current provider behavior
- [ai-provider-contracts.md](ai-provider-contracts.md) — Slice 11.2, the request/result/registry foundation
- [ai-provider-configuration.md](ai-provider-configuration.md) — Slice 11.3, the configuration foundation
- [ai-provider-openai.md](ai-provider-openai.md) — Slice 11.6, the first adapter run by this executor
- [`engine/verification/ai_provider_baseline/README.md`](../verification/ai_provider_baseline/README.md) — Slice 11.1
- [`engine/verification/ai_provider_contracts/README.md`](../verification/ai_provider_contracts/README.md) — Slice 11.2 verification
- [`engine/verification/ai_provider_configuration/README.md`](../verification/ai_provider_configuration/README.md) — Slice 11.3 verification
- [`engine/verification/ai_provider_execution/README.md`](../verification/ai_provider_execution/README.md) — Slice 11.4 verification
- [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12 privacy / failure isolation
