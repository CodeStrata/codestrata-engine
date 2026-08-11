# OpenAI Provider Migration (Epic 11, Slice 11.6)

> **Status: wired.** Unlike Slices 11.2–11.5, this page describes code that
> `codestrata assess --with-ai` actually runs when the provider is `openai`.
> Bedrock is also migrated (Slice 11.7); see
> [`ai-provider-bedrock.md`](ai-provider-bedrock.md). Cross-provider guarantees
> and the registry decision are in
> [`ai-provider-platform.md`](ai-provider-platform.md) (Slice 11.8).

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.6 migrates the **OpenAI** provider onto
the Slice 11.2–11.5 provider contracts. A new adapter package,
`codestrata.ai.provider_adapters.openai`, implements the `AIProvider` protocol
and runs under `AIProviderExecutor`. The existing public class,
`OpenAIAIModelProvider`, stays exactly where it was — same module, same name,
same constructor signature, same registry key — and becomes a thin
compatibility wrapper over the adapter.

Nothing observable about an assess run changes. Same default provider
(`bedrock`), same selection precedence, same `[ai.openai]` keys, same
`gpt-4o-mini` default, the same prompt bytes on the wire, the same exceptions
raised into `AiEnrichmentService`'s fail-soft path, assessment report schema
`1.2`, the same Findings/Evidence/Recommendations surface, and the same CLI exit
codes.

This is **not**:

* A redesign of Bedrock (completed separately in Slice 11.7).
* OpenRouter or any third-party LLM routing support.
* An activation of `OpenAISettings.max_retries` — the executor still makes
  exactly one provider call per assess run (CR-1).
* Real wall-clock timeout enforcement by the executor. The 60s bound is still
  enforced by the OpenAI client's own `timeout=` argument; the executor's
  `TimeoutPolicy` only declares it.
* A change to telemetry, analytics, Community Cloud, the Data Lake, the VS Code
  extension, or infrastructure.

## Both providers migrated

After Slice 11.7, both OpenAI and Bedrock run as adapters under
`AIProviderExecutor` behind the same `AssessAIProviderRegistry` compatibility
seam. Slice 11.8 **Decision B** retains that compatibility registry;
contracts `AIProviderRegistry` consolidation remains deferred. See
[`ai-provider-platform.md`](ai-provider-platform.md).

```text
                        AssessAIProviderRegistry
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
   "openai" (migrated)                      "bedrock" (migrated, default)
              │                                       │
   OpenAIAIModelProvider                    BedrockAIModelProvider
   (AIModelProvider wrapper)                (AIModelProvider wrapper)
              │                                       │
   OpenAIProvider + executor                BedrockProvider + executor
```

Both branches still satisfy the same legacy `AIModelProvider.invoke()`
interface, so `AiEnrichmentService`, the provider factory, `codestrata ai
doctor`, and the CLI are untouched. The registry does not know that its
providers are contract-based adapters.

Compatibility wrappers remain intentional. Slice 11.8 Decision B retains the
assess compatibility registry. OpenRouter is assess-registered as an explicit non-default provider (Slice 11.10) with local doctor readiness (Slice 11.11).

## Package layout

```text
engine/src/codestrata/ai/provider_adapters/
├── __init__.py                 Namespace for provider adapters
└── openai/
    ├── __init__.py             Public surface of the adapter package
    ├── adapter.py              OpenAIProvider(AIProvider) — execute() never raises
    ├── capabilities.py         Re-exposes OPENAI_CAPABILITY_PROFILE (Slice 11.5)
    ├── client.py               The one credential boundary: lazy client, redacted repr
    ├── configuration.py        OpenAISettings → runtime configuration + client inputs
    ├── diagnostics.py          Redacted diagnostic views and published matrices
    ├── error_mapping.py        SDK exception → ErrorCategory + bounded AIProviderError
    ├── factory.py              Build adapter/executor with no client and no env read
    ├── legacy_bridge.py        PromptRequest ⇄ contracts ⇄ legacy result/exceptions
    ├── request_mapping.py      AIProviderRequest → Chat Completions kwargs
    ├── response_mapping.py     SDK response → AIProviderResult (+ bridge-only detail)
    └── usage_mapping.py        Token totals → ProviderUsageMetadata
```

### Dependency rules

The adapter may import: `codestrata.ai.provider_contracts.*`,
`codestrata.ai.prompts.models`, `codestrata.ai.providers.exceptions`,
`codestrata.ai.providers.models`, `codestrata.ai.providers.parsing`,
`codestrata.config.settings`, the `openai` SDK (in `client.py` only), and the
standard library.

It must never import `codestrata.reporting`, `codestrata.telemetry`,
`codestrata.analytics`, `codestrata.cli`, `codestrata.application`,
`codestrata.extensions`, `codestrata.platform`, `codestrata.datalake`, `boto3`,
`botocore`, or anything VS Code / Cursor. It also imports no `asyncio`,
`threading`, `signal`, `subprocess`, `socket`, `urllib`, `httpx`, or `requests`,
and never calls `time.sleep`.

Two boundaries are narrower still, and both are enforced by the SV.11.6
dependency-boundary checks:

* **`client.py` is the only module that imports the `openai` SDK.**
* **`client.py` is the only module that reads `os.environ`.**

`codestrata.ai.provider_contracts` remains SDK-free and adapter-agnostic: no
contract module imports `openai` or `provider_adapters`.

## Request mapping is byte-compatible

`legacy_bridge.fold_prompt_request` folds an ordered `PromptRequest` into the
provider-neutral `ModernizationAdvisorInput`:

* `system` messages and `developer` messages (each prefixed with
  `"Developer instructions:\n"`) join with `"\n\n"` into `instruction_text`.
* `user` messages join with `"\n\n"` into `context_payload_text`.

`request_mapping.build_chat_completion_kwargs` then produces exactly the two
messages the pre-migration provider produced — one `system`, one `user` — and,
for `ResponseExpectation.STRUCTURED_JSON`, appends the same trailer:

```text
Respond with a single JSON object only. Do not include markdown fences or prose.
```

The trailer is appended only when the folded instruction text does not already
end with it, so nothing is ever doubled. The kwargs are `model`, `messages`,
`response_format={"type": "json_object"}`, plus `temperature` and `max_tokens`
when the request carries them — the same set, with the same names and the same
omit-when-unset behavior, as before the migration. For
`ResponseExpectation.TEXT` there is no trailer and no `response_format`.

`_chat_messages()` remains a module-level helper on `openai_provider.py`,
delegating to the adapter, because the Slice 11.1 baseline characterizes that
exact function and message shape.

## Errors: bounded categories, preserved legacy exceptions

`error_mapping` classifies by SDK exception **class name**, so classification
needs no SDK import and works whether or not the optional extra is installed:

| SDK exception | `ErrorCategory` | Retryable | Legacy exception still raised |
| --- | --- | --- | --- |
| `AuthenticationError` | `authentication_failed` | no | `AIProviderInvocationError` |
| `PermissionDeniedError` | `authorization_failed` | no | `AIProviderInvocationError` |
| `NotFoundError` | `invalid_model` | no | `AIProviderInvocationError` |
| `BadRequestError` | `invalid_request` | no | `AIProviderInvocationError` |
| `UnprocessableEntityError` | `invalid_request` | no | `AIProviderInvocationError` |
| `APITimeoutError` | `timeout` | yes | `AIProviderTimeoutError` |
| `RateLimitError` | `rate_limited` | yes | `AIProviderTimeoutError` |
| `APIConnectionError` | `provider_unavailable` | yes | `AIProviderTimeoutError` |
| `InternalServerError` | `provider_unavailable` | yes | `AIProviderTimeoutError` |
| anything else | `internal_failure` | no | `AIProviderInvocationError` |

Three more categories come from outside the SDK call:
`dependency_unavailable` (the optional extra is not installed),
`missing_configuration` (the API key variable is unset, or the client
constructor failed), and `invalid_response` / `parsing_failed` (no assistant
text, an unreadable response, or undecodable JSON).

The "Retryable" column reflects the Slice 11.4 default partition. Because the
pinned retry policy allows one attempt, a retryable category is classified but
never acted on — that is the `operational_retry_remains_conservative`
limitation.

`AIProviderError.detail` is always fixed, bounded prose keyed by a diagnostic
code (`openai_rate_limited`, `openai_api_key_env_not_set`, …). It never echoes
the SDK exception's message, type, or traceback. The verbatim legacy message
travels separately on a bridge-only field consumed solely by
`legacy_bridge.legacy_error_for`, so the fail-soft messages users have always
seen are reproduced without the raw text ever reaching a contract type or a
diagnostic view.

## Execution and fail-soft

```python
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)

adapter = build_openai_provider(openai_settings=settings.ai.openai)
execution = build_openai_executor(adapter).execute(provider_request)
```

`build_openai_executor` pins `DEFAULT_RETRY_POLICY` (`maximum_attempts=1`),
`DEFAULT_TIMEOUT_POLICY` (60s, `provider_request` scope), and
`DEFAULT_BACKOFF_POLICY`, and injects a no-op sleeper so no code path can wait
even if a caller supplies a multi-attempt policy in a test.

`OpenAIProvider.execute()` never raises for an expected failure (CR-3). Every
missing key, SDK error, or malformed response comes back as a
`FAILED`/`UNAVAILABLE` `AIProviderResult` carrying a bounded `AIProviderError`.
An undeclared capability returns `SKIPPED` without constructing a client.
`KeyboardInterrupt` and `SystemExit` propagate unmodified.

The **wrapper** is what restores the raise-based contract the rest of the engine
expects. On a non-`SUCCESS` execution, `OpenAIAIModelProvider.invoke()` raises
the same legacy exception type, with the same message, that the pre-migration
provider raised — so `AiEnrichmentService` fail-soft, the resulting AI execution
status, and the CLI exit code are all unchanged. On success it rebuilds
`ModelInvocationResult`, including the enrichment payload short-circuit
(`looks_like_enrichment_payload`) and the legacy
`parse_recommendation_response` path.

## Credentials and the client

`client.resolve_client` is the only place a credential is read or a client
constructed, and it happens on the first `execute()` — never at import, never
during `supports()` or capability discovery, and not at all when AI enrichment
is disabled.

* Tests pass `injected_client=`, which short-circuits both the SDK import and
  the environment read.
* There is no process-wide client singleton; each resolution builds a fresh
  client, so no credential state outlives one invocation.
* `OpenAIClientHandle.__repr__` renders only the key *variable name*, whether a
  base URL was configured, and whether the client was injected — never the
  client object (whose own repr can echo a base URL or default headers), the
  base URL, or the key.

## Configuration

Unchanged from Slice 11.1. `[ai.openai]` still carries `answer_model`,
`api_key_env`, `base_url`, `max_retries`, `timeout_seconds`,
`embedding_model`, and `embedding_dimensions`, with `answer_model` defaulting to
`gpt-4o-mini` and `api_key_env` to `OPENAI_API_KEY`.

`configuration.build_runtime_configuration` bridges `OpenAISettings` into an
`OpenAIRuntimeConfiguration` (the Slice 11.3 `OpenAIAdapterConfiguration` for
diagnostics, plus the `OpenAIClientInputs` the client boundary needs). It
resolves *names*, never values: the API key variable name and the normalized
base URL, but never the key itself. Whether a key is present is only ever
discovered inside `client.py`.

## Privacy

Nothing derived from a prompt, a response, a credential, a base URL, or a
request ID reaches a diagnostic view or a serialized result:

* `diagnostics.py` reports provider ID, capability, status, category, counts,
  and policy shapes — never content, detail text, or configuration values.
* `AIProviderResult` diagnostic serialization omits `content`.
* Per-invocation values the legacy metadata contract needs (request ID, stop
  reason, latency, token totals, the verbatim legacy message) travel on an
  `OpenAIInvocationDetail` handed to an optional `detail_sink` callback rather
  than stored on the adapter, so two adapters never share state and nothing
  response-derived outlives one call.

## Verification

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.openai_provider_migration
```

Report: `engine/reports/verification/sv11-6/openai-provider-migration-verification.json`.
Schema: `openai-provider-migration-verification` @ `1.0.0`. Verdict:
`pass_with_limitations` is expected — the recorded limitations
(`bedrock_remains_legacy`, `mixed_mode_provider_architecture`,
`no_live_openai_calls`, `operational_retry_remains_conservative`,
`doctor_uses_compatibility_path`,
`executor_limitation_labels_predate_migration`, and the historical OpenRouter
absence limitation label from this single-provider migration slice) are
intentional properties of a single-provider migration slice, not defects.
OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion`.
See
[`engine/verification/openai_provider_migration/README.md`](../verification/openai_provider_migration/README.md).

The suite also re-checks that `bedrock.py` gained no contract, adapter,
executor, or router reference and still uses the Converse path, and that
Slices 11.1–11.5 remain green.

## Unit tests

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_adapters/openai -q
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/openai_provider_migration -q
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/test_ai_model_providers.py -q
```

No test performs a network call, reads a real credential, or waits: SDK doubles
and injected clients live in the test packages, never in `src/`.

## Related

- [ai-enrichment.md](ai-enrichment.md) — the assess enrichment path and Bedrock's legacy behavior
- [ai-provider-contracts.md](ai-provider-contracts.md) — Slice 11.2, the request/result/registry foundation
- [ai-provider-configuration.md](ai-provider-configuration.md) — Slice 11.3, the configuration foundation
- [ai-provider-execution.md](ai-provider-execution.md) — Slice 11.4, the executor/retry/timeout foundation
- [ai-provider-capabilities.md](ai-provider-capabilities.md) — Slice 11.5, capability profiles and usage metadata
- [`engine/verification/openai_provider_migration/README.md`](../verification/openai_provider_migration/README.md) — Slice 11.6 verification
- [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12 privacy / failure isolation
