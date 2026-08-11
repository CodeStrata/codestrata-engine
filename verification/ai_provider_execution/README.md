# Epic 11, Slice 11.4 — Standardized Execution, Errors, Timeouts, and Retries

Verifies the **new, unwired** `codestrata.ai.provider_contracts.execution_*`
(plus `timeout_policy.py`/`retry_policy.py`/`retry_decision.py`/`backoff.py`/
`error_classification.py`/`executor.py`) modules introduced by Slice 11.4: a
standardized, provider-neutral execution loop (timeout/retry/backoff policy,
error classification, and `AIProviderExecutor`) as pure, injected-input
domain types plus one orchestration class.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A dependency-boundary check that execution modules import no SDK/product modules, and never `os`/`pathlib`/`subprocess`/`threading`/`asyncio`/`signal` | A migration of OpenAI or Bedrock to the new execution types |
| A compatibility cross-check against the **real**, loaded Slice 11.1 baseline (CR-1..CR-6), including `DEFAULT_RETRY_POLICY.maximum_attempts=1` matching CR-1's exact-one-invoke behavior | A change to default provider, default models, or resolution precedence |
| A functional exercise of `AIProviderExecutor` against small, in-process fake providers (never real network calls) | A wiring of `AIProviderExecutor` into `codestrata assess` |
| A fail-soft characterization: the executor never raises for a `FAILED`/`UNAVAILABLE` result, and never swallows `KeyboardInterrupt`/`SystemExit` | A new `AIProvider` protocol implementation used by assess |
| A privacy check that diagnostics/serialization never leak provider response content or exception text | A production logging/telemetry pipeline |
| A confirmation that no product-path file (assess factory, providers, enrichment, doctor, CLI, config layer) imports the new modules | A wall-clock timeout enforcement mechanism |
| A record of expected limitations (`executor_not_wired`, `providers_not_migrated`, `timeout_enforcement_deferred_to_adapters`, `runtime_settings_still_unwired`) | A fix for those limitations |

No real provider network calls or credentials are used or required.

## Modules

| Module | Verifies |
| --- | --- |
| `contract.py` | Ground-truth constants and the `ExecutionVerificationContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `ExecutionVerificationReport`) |
| `inventory.py` | AST-based structural inventory; confirms all 11 Slice 11.4 modules exist alongside the Slice 11.2/11.3 set |
| `dependency_boundary.py` | No forbidden SDK/product imports; execution modules never import `os`/`pathlib`/`subprocess`/`threading`/`asyncio`/`signal`; no product-path import; `ai/providers/` untouched |
| `baseline_compatibility.py` | Cross-checks `execution_compatibility` against the **real** `verification.ai_provider_baseline.reporting.build_compatibility_requirements()` (CR-1..CR-6); default retry policy vs. CR-1; settings-representable retry policy vs. the real `BedrockSettings`/`OpenAISettings.max_retries` default; `DEFAULT_TIMEOUT_SECONDS` vs. the real providers default |
| `policy.py` | `execution_policy` constants: retryable/non-retryable partition covers every `ErrorCategory` exactly once, bounded defaults, hard constraints recorded |
| `timeout.py` | `TimeoutPolicy` bounds (positive, finite, ≤ 3600s), default (60s/provider_request/enabled), `TimeoutScope` matches policy |
| `retries.py` | `max_retries_to_maximum_attempts`, `AIProviderRetryPolicy` bounds, `decide_retry` (stop at max attempts / non-retryable / schedule retry, never sleeps), `backoff` (none/fixed/exponential, capped, deterministic even with jitter, never sleeps) |
| `errors.py` | `error_classification`: category/safe_code preserved, `classify_unexpected_exception` takes no exception argument and never leaks exception text |
| `executor.py` | `AIProviderExecutor` functional behavior against small in-process fakes: skip, success, retry-then-success, non-retryable stop, max-attempts stop, timeout_applied, unexpected-exception-to-internal-failure, `KeyboardInterrupt` propagation, provider_id mismatch rejection |
| `fail_soft.py` | Structural: `executor.py` catches exactly `Exception` (never bare `except:`/`BaseException`), never calls `sys.exit`/`os.kill` |
| `privacy.py` | Diagnostics/serialization never include provider response content or exception text/type |
| `runtime_unwired.py` | Importing execution modules never touches the assess registry, changes settings defaults, or exposes a process-wide registry/executor singleton |
| `determinism.py` | Canonical JSON helpers; repeated-execution/backoff-delay-sequence/hash stability checks |
| `scenarios.py` | Negative scenarios A–Z, including direct construction-time invariant checks (`run_value_object_negative_checks`) |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–Z)

Each scenario names a condition Slice 11.4 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: no OpenRouter references, no
`os`/`pathlib`/`subprocess`/`threading`/`asyncio`/`signal` imports in
execution modules, no product-path import of the new modules, `ai/providers/`
unchanged, every Slice 11.1 CR covered by an execution compatibility
statement that holds, the default retry policy matching CR-1, the
settings-representable retry policy matching the real settings default, the
default timeout matching the real providers default, the retryable/
non-retryable partition covering every `ErrorCategory` exactly once,
authentication/authorization never retryable by default, all 11 new modules
present, the executor never raising for a failed result, never retrying a
non-retryable category, stopping at `maximum_attempts`, never propagating an
unexpected exception unmodified, never swallowing `KeyboardInterrupt`,
rejecting a `provider_id` mismatch, diagnostics excluding provider content,
no absolute paths or secret-shaped tokens in the report, and this package
never shelling out to a subprocess.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_execution
```

Report: `engine/reports/verification/sv11-4/ai-provider-execution-verification.json`
(+ `ai-provider-execution-verification.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_execution -q
```

## Report contract

- `schema_name`: `ai-provider-execution-verification`
- `schema_version`: `1.0.0`
- `verdict`: `pass` or `pass_with_limitations` (`fail` if any check/scenario fails)
- `pass_with_limitations` is **expected**: recorded limitations are
  `executor_not_wired`, `providers_not_migrated`,
  `timeout_enforcement_deferred_to_adapters`, and
  `runtime_settings_still_unwired` — intentional properties of an unwired
  execution slice, not defects.

> Since Slice 11.6, `executor_not_wired` and `providers_not_migrated` describe
> **Bedrock** and the orchestration layers. OpenAI is migrated and runs under
> `AIProviderExecutor`, so `ai/providers/openai_provider.py` is deliberately
> excluded from this suite's `PRODUCT_PATH_FILES`. The pinned policy is still
> `DEFAULT_RETRY_POLICY` (`maximum_attempts=1`), so `max_retries` remains
> unwired and no retry is ever performed. See
> [`../openai_provider_migration/README.md`](../openai_provider_migration/README.md).

The report is sanitized before being written: absolute home-directory paths
and secret-shaped tokens are redacted from all check/scenario text and
matrices. Two runs over an unchanged checkout produce byte-identical JSON.

## Boundaries

- Verifies the new execution modules only — does not change provider
  selection, defaults, model resolution precedence, config keys, doctor,
  CLI, or real AI execution.
- Does not migrate OpenAI or Bedrock, does not add OpenRouter, and does not
  wire `AIProviderExecutor` into `codestrata assess`, `codestrata.ai.enrichment`,
  the providers factory, or doctor.
- Does not modify telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.
- Does not start Slice 11.5.
- Not shipped in the `codestrata` wheel.

## Later slices

Slice 11.8 (`ai_provider_cross_provider`) verifies OpenAI and Bedrock against these contracts with **Decision B** (compatibility registry retained). OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
