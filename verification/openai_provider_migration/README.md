# Epic 11, Slice 11.6 — OpenAI Provider Migration

Verifies the first **wired** provider migration in Epic 11: OpenAI now runs on
the Slice 11.2–11.5 contracts through a new 12-module adapter package
(`codestrata.ai.provider_adapters.openai`), executed by `AIProviderExecutor`.
`OpenAIAIModelProvider` remains the public assess-path class and becomes a thin
compatibility wrapper over that adapter.

Historical note: when SV.11.6 first shipped, Bedrock was still legacy (mixed
mode). Slice 11.7 migrated Bedrock; Slice 11.8 verified both providers against
shared contracts (**Decision B** — compatibility registry retained). OpenRouter
completed in Slices 11.9–11.11; see `ai_provider_platform_completion`. This suite
still proves OpenAI migration invariants.

## What this is (and is not)

| It is | It is not |
| --- | --- |
| A dependency-boundary check that only `client.py` imports the `openai` SDK or reads the environment | A migration of Bedrock, or the start of Slice 11.7 |
| A byte-compatibility check that the folded prompt, message roles, structured-JSON trailer, and Chat Completions kwargs are unchanged from Slice 11.1 | A live call to OpenAI, or a test that supplies real credentials |
| A check that the executor runs the adapter under the pinned Slice 11.4 defaults (one attempt, declarative 60s) | An activation of operational retry (`max_retries`) or enforced timeouts |
| A check that the wrapper still raises the *same* legacy exception types, so `AiEnrichmentService` fail-soft is untouched | A change to CLI exit behavior, report schema 1.2, or the Findings/Recommendations surface |
| A regression check that `bedrock.py` gained no contract/adapter/executor reference and still uses the Converse path | A refactor of Bedrock, `doctor.py`, or any orchestration layer |
| A privacy check that no prompt, response, model value, base URL, request ID, credential, path, or timestamp reaches the report | A production logging or telemetry pipeline |
| A record of expected limitations (mixed mode, single attempt, unmigrated doctor) | A fix for those limitations |

Every provider execution in this suite goes through an injected in-memory
client. No network call, credential read, or wall-clock wait occurs anywhere.

## Modules

| Module | Verifies |
| --- | --- |
| `contract.py` | Ground-truth constants and the `OpenAIMigrationVerificationContract` pass/fail contract |
| `models.py` | Deterministic report dataclasses (`CheckResult`, `ScenarioResult`, `OpenAIMigrationVerificationReport`) |
| `fixtures.py` | Synthetic SDK doubles (response, usage, exception-by-class-name) and request builders; no network, no credentials, no waiting |
| `inventory.py` | AST-based structural inventory: exactly the 12 expected modules, each documented and declaring `__all__` |
| `dependency_boundary.py` | Forbidden layer/runtime imports; the `client.py` SDK and environment boundary; migrated files import the contracts while Bedrock, enrichment, assess, and the CLI do not; contracts stay SDK-free |
| `baseline_compatibility.py` | Slice 11.1 CR-1..CR-6 still hold: bedrock default, `gpt-4o-mini`, registered providers, unchanged wrapper constructor, schema 1.2 |
| `configuration.py` | `[ai.openai]` keys, the default and custom API key variable names, optional/normalized base URL, the 60s default, settings precedence, and redacted configuration views |
| `authentication.py` | Lazy client construction; `supports()` reads no credential; a missing key yields a bounded unavailable result rather than an exception; injected clients bypass the environment; no client singleton |
| `requests.py` | Prompt folding, message roles and order, the developer prefix, the structured-JSON trailer appended exactly once, and the unchanged `response_format` |
| `responses.py` | Tolerant extraction, empty/malformed content as invalid responses, bounded oversized text, structured decoding only when expected, latency propagation, and no request-ID leakage |
| `usage.py` | Wire field names, token totals, inconsistent/partial/invalid triples, missing usage objects, clamped latency, completion status, and the absence of any cost or billing field |
| `errors.py` | The SDK-exception-to-category matrix, the retryable partition against Slice 11.4, bounded safe detail prose that never echoes the exception, and classification without importing the SDK |
| `execution.py` | The adapter satisfies `AIProvider`; the executor is pinned to one attempt and a declarative 60s; a retryable failure is not retried; the executor never sleeps and never raises |
| `fail_soft.py` | Each SDK failure still raises the same legacy exception type with the same message and AI status; blank model IDs and non-positive timeouts are rejected early |
| `mixed_mode.py` | Both providers resolve from one registry; Bedrock keeps the legacy Converse path, its module surface, and its constructor signature; no OpenRouter reference exists in `ai/` |
| `doctor.py` | `doctor.py` still covers both providers, names the configured key variable, stays secret-free, and never constructs a provider or invokes a model |
| `reporting_boundary.py` | Schema 1.2, the unchanged AI execution status vocabulary and Findings/Recommendations surface, and an adapter that adds no report field and touches no filesystem |
| `privacy.py` | Diagnostics, results, serialization, configuration and client reprs, bounded errors, and the final report body are all free of secrets, URLs, prompt/response text, model values, request IDs, and paths |
| `determinism.py` | Canonical JSON helpers used to prove two runs are byte-identical |
| `scenarios.py` | Negative scenarios A–AB |
| `reporting.py` | Assembles, sanitizes, and computes the verdict for the final report |
| `runner.py` / `__main__.py` | Orchestration and CLI entry point |

## Negative scenarios (A–AB)

Each scenario names a condition Slice 11.6 must never exhibit and records
whether it was observed (`ok=True` means the forbidden condition did **not**
occur) — for example: the default provider or default answer model changed, a
config key renamed, the prompt content changed, the structured-JSON trailer
duplicated, operational retry activated, `execute()` raising for an expected
failure, a secret or base URL reaching a diagnostic, Bedrock gaining a contract
or adapter reference or losing its Converse path, an OpenRouter reference
appearing under `ai/`, the SDK or `os.environ` leaking outside `client.py`, a
forbidden layer import, the assess/enrichment/CLI path importing the SDK, the
wrapper's public surface changing, a client constructed at import time, the
assessment schema moving off 1.2, a blank model ID reaching the wire, and a
usage record carrying a cost field.

## Run

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.openai_provider_migration
```

Report: `engine/reports/verification/sv11-6/openai-provider-migration-verification.json`
(+ `openai-provider-migration-verification.md` summary). `reports/` is gitignored.

Tests:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/openai_provider_migration -q
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_adapters/openai -q
```

## Report contract

- `schema_name`: `openai-provider-migration-verification`
- `schema_version`: `1.0.0`
- `verdict`: `pass_with_limitations` (`fail` if any check or scenario fails)
- `pass_with_limitations` is **expected**. The recorded limitations are
  `bedrock_remains_legacy`, `mixed_mode_provider_architecture`,
  `no_live_openai_calls`, `operational_retry_remains_conservative`,
  `doctor_uses_compatibility_path`,
  `executor_limitation_labels_predate_migration`,
  `openrouter_operational_explicit`, and `openrouter_doctor_local_readiness_only` —
  OpenRouter is assess-registered (explicit-only); doctor local readiness landed
  in Slice 11.11 (no client construction or model invoke). Intentional properties
  of the current provider platform migration slice, not defects.

The report is sanitized before being written: home-directory paths and
secret-shaped tokens are redacted from all check text, scenario text, and
matrices, and the written JSON is re-scanned for forbidden fragments before the
run is allowed to succeed. The body carries no timestamp or duration, so two
runs over an unchanged checkout produce byte-identical JSON.

## Boundaries

- Verifies the OpenAI migration only — does not change provider selection
  precedence, credentials, prompts, reports, Findings, schemas, or CLI exit
  behavior.
- Does not migrate Bedrock and does not add OpenRouter (the forbidden
  third-party router-provider name is never spelled out as a literal inside
  `src/codestrata/ai/`; this package's `contract.py` and `scenarios.py` —
  outside `src/` — are the only places the literal appears, for scanning
  purposes).
- Does not modify telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.
- Does not start Slice 11.7.
- Not shipped in the `codestrata` wheel.
