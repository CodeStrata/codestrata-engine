# Common AI Provider Contracts (Epic 11, Slice 11.2)

> **Status: foundation, consumed by OpenAI and Bedrock.** Since Slices 11.6 and
> 11.7 both providers implement `AIProvider` under these contracts — see
> [`ai-provider-openai.md`](ai-provider-openai.md),
> [`ai-provider-bedrock.md`](ai-provider-bedrock.md), and
> [`ai-provider-platform.md`](ai-provider-platform.md). See
> [`ai-enrichment.md`](ai-enrichment.md) for enrichment/fail-soft behavior, and
> [`ai-provider-configuration.md`](ai-provider-configuration.md) /
> [`ai-provider-execution.md`](ai-provider-execution.md) /
> [`ai-provider-capabilities.md`](ai-provider-capabilities.md) for Slices
> 11.3/11.4/11.5, which extend this same sibling package.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.2 introduces a small, provider-neutral,
SDK-free set of domain types under `codestrata.ai.provider_contracts`:
requests, results, usage metadata, bounded errors, a minimal synchronous
`AIProvider` protocol, and an explicit, deterministic registry.

This is **not**:

* A migration of the OpenAI or Bedrock providers.
* A new default provider selection mechanism.
* A change to `codestrata assess` provider selection, defaults,
  configuration, model resolution, timeouts, retries, authentication, error
  handling, or `codestrata ai doctor`.
* OpenRouter support *in this slice* (added later under contract 1.0 in Slices
  11.9/11.10 — see
  [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md)).
* Wired into the assessment product path in any way.

It is a Slice 11.1-compatible foundation that a future slice (11.3+, not
started here) could build production adapters against, without changing
anything about how `codestrata assess --with-ai` behaves today.

## Why a sibling package (`ai/provider_contracts/`), not `ai/providers/`?

`codestrata.ai.providers` already hosts:

* The concrete `BedrockAIModelProvider`/`OpenAIAIModelProvider` adapters.
* `base.py`'s `AIModelProvider` — the current, capability-specific,
  synchronous `invoke(request, options) -> result` ABC used by
  `AiEnrichmentService`.
* `models.py`'s `ModernizationModelRequest`/`ModelInvocationResult` — the
  current prompt-package request/response shapes.
* `registry.py`'s `AIProviderRegistry` — a **different**, Phase 5.8,
  embedding/answer-provider knowledge registry (Platform extension surface).

Slice 11.1 also inventories the exact file set under `ai/providers/` as part
of its compatibility-baseline boundary characterization
(`ALLOWED_AI_PROVIDERS_DIRECTORY_FILES`). Adding new files there would both:

1. Collide with an existing `AIProviderRegistry` name that means something
   different, and
2. Look like scope creep into the Slice 11.1 baseline's inventoried file set.

A sibling package — `codestrata.ai.provider_contracts` — keeps the two trees
independently readable and dependency-checkable: the existing tree stays
100% focused on "what `codestrata assess` actually calls today," and the new
tree stays 100% focused on "provider-neutral domain types with zero SDK
imports, not called by anything yet." See
[`relationship.py`](../src/codestrata/ai/provider_contracts/relationship.py)
for the full classification and
[`engine/verification/ai_provider_baseline/README.md`](../verification/ai_provider_baseline/README.md)
for the Slice 11.1 inventory this package deliberately does not touch.

## Package layout

```text
engine/src/codestrata/ai/provider_contracts/
├── __init__.py           Package overview + design rationale (this doc, condensed)
├── policy.py             Contract/policy identifiers and bounded allowed-value sets
├── versions.py           ContractVersion value object and support-checking
├── identifiers.py        ProviderId, CapabilityId, ProviderModelReference
├── capabilities.py       ModernizationAdvisorInput (typed capability payload)
├── requests.py           AIProviderRequest, ExecutionOptions, ResponseExpectation
├── responses.py          AIProviderResult, AIProviderResultContent
├── execution.py          ProviderExecutionStatus + documented AIExecutionStatus mapping
├── usage.py              ProviderUsageMetadata
├── errors.py             ErrorCategory, AIProviderError, ProviderContractValidationError
├── diagnostics.py        Privacy-safe diagnostic views (never prompts/responses/credentials)
├── provider.py           The AIProvider protocol
├── registry.py           AIProviderRegistry (explicit, deterministic)
├── validation.py         Shared validation helpers
├── serialization.py      Deterministic JSON serialization of diagnostic views
├── compatibility.py      Compatibility statements against Slice 11.1 CR-1..CR-6
└── relationship.py       Classification of existing vs. new AI abstractions
```

Zero imports from the rest of `codestrata` cross into this package from
outside it, and this package imports nothing from `codestrata.ai.providers`,
`codestrata.extensions`, `codestrata.reporting`, `codestrata.telemetry`,
`codestrata.analytics`, `codestrata.platform`, `codestrata.datalake`,
`codestrata.cli`, or any of `openai`/`boto3`/`botocore`/`httpx`/`requests`.
This is enforced by an architecture test
(`engine/tests/ai/provider_contracts/test_dependency_boundary.py`) and by
the SV.11.2 verification suite.

## Contract identity

| Identifier | Value |
| --- | --- |
| Policy | `community-ai-provider-contract-policy:1.0` |
| Contract | `community-ai-provider-contract:1.0` |
| Contract version | `1.0` |
| Provider IDs | `openai`, `bedrock` (Engine IDs — matches `verification.ai_provider_baseline.contract.ENGINE_PROVIDER_IDS`; **not** `aws_bedrock`, which is an analytics-only `provider_family` label) |
| Capability | `modernization_advisor` (matches the analytics capability catalog; "Modernization Advisor" is the product-facing display name only) |
| Response expectations | `text`, `structured_json` (a caller's expectation — whether an adapter uses a provider's native JSON-mode is an adapter implementation detail, not part of this contract) |
| Execution statuses | `success`, `unavailable`, `failed`, `skipped` |
| Error categories | `missing_configuration`, `dependency_unavailable`, `authentication_failed`, `authorization_failed`, `invalid_model`, `timeout`, `rate_limited`, `provider_unavailable`, `invalid_request`, `invalid_response`, `parsing_failed`, `internal_failure` |

## Core types

### `AIProviderRequest` (`requests.py`)

An immutable envelope: `capability`, a **typed** capability `payload` (never
an arbitrary `dict`), `response_expectation`, an opaque `model_reference`,
optional `execution_options`, and `contract_version` (defaults to `"1.0"`).

```python
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation

request = AIProviderRequest(
    capability=CapabilityId.MODERNIZATION_ADVISOR,
    payload=ModernizationAdvisorInput(
        instruction_text="Summarize modernization risk for this repository.",
        context_payload_text="{...finalized, already-serialized context...}",
    ),
    response_expectation=ResponseExpectation.STRUCTURED_JSON,
    model_reference=ProviderModelReference("gpt-4o-mini"),
)
```

`execution_options` (`timeout_seconds`/`temperature`/`max_tokens`) are
**optional, opaque placeholders for possible future use**. Per Slice 11.1's
CR-2, this slice does **not** claim they are wired to anything — no adapter
reads them, and no settings/timeout/retry behavior has changed.

### `ModernizationAdvisorInput` (`capabilities.py`)

Finalized, provider-neutral text — not an OpenAI `messages: list[dict]`
array, and not a Bedrock Converse `messages`/`system` dict shape. An adapter
(not implemented by this slice) would be responsible for wrapping
`instruction_text`/`context_payload_text` into whichever wire format its SDK
requires. **No actual prompt construction in
`codestrata.ai.enrichment`/`codestrata.ai.prompts` is changed by this type.**

### `AIProviderResult` (`responses.py`)

Immutable: `provider_id`, `capability`, `status`, optional typed `content`
(`AIProviderResultContent`: free text and/or a provider-neutral JSON `dict`),
optional `usage`, optional bounded `error`, and `limitations`. Invariants are
enforced at construction time:

* `SUCCESS` requires `content` and forbids `error`.
* `FAILED`/`UNAVAILABLE` require `error` and forbid `content`.
* `SKIPPED` forbids both `content` and `error`.

### `ProviderModelReference` (`identifiers.py`)

An opaque, validated model identifier string. `.value` holds the raw string
for adapter use; `.redacted()` (and `__repr__`/`__str__`) always return
`"[model_ref]"`. Diagnostics, logs, the registry, and verification reports
must always use `.redacted()`, never `.value`.

### `ProviderUsageMetadata` (`usage.py`)

All fields optional (`input_tokens`, `output_tokens`, `total_tokens`,
`latency_ms`, `request_count`, `retry_count`); non-negative when present.
When `input_tokens`, `output_tokens`, and `total_tokens` are **all** present,
`total_tokens` must equal their sum. Partial usage (e.g. only
`input_tokens`) is not cross-validated.

### `AIProvider` protocol (`provider.py`)

Exactly three synchronous members: `provider_id`, `supports(capability)`,
`execute(request) -> result`. No `async`, no streaming, no tool-calling, no
`configure()`/`set_api_key()`/raw-client accessor. Implementations must
never raise for expected provider/parsing/validation failures — those are
represented as a `FAILED`/`UNAVAILABLE` result instead.

### `AIProviderRegistry` (`registry.py`)

Explicit construction (`AIProviderRegistry()` — no process-wide default, no
`importlib.metadata` entry-point discovery). `register()` stores a static
capability declaration and a zero-argument factory; it never instantiates
the provider. Only `resolve()` calls the factory, and only for a caller who
asks for that specific provider. Duplicate `provider_id` registration and
resolution of an unknown `provider_id` both raise
`ProviderContractValidationError`. `list_provider_ids()` always returns IDs
sorted.

This is a **new, separate registry** — not
`codestrata.extensions.assess_ai.AssessAIProviderRegistry` (today's runtime
selection registry) and not `codestrata.ai.providers.registry.AIProviderRegistry`
(the Phase 5.8 embedding/answer knowledge registry). See `relationship.py`.

### `AIProviderError` (`errors.py`)

A bounded **data** object (never a raised exception) carried inside a
result: `category` (one of the twelve error categories above), a short
machine-safe `code`, and an optional short safe-prose `detail` (≤240
characters). Construction rejects raw exception text/stack traces,
`-----BEGIN` PEM fences, absolute home-directory paths, and
`Authorization: Bearer` headers in `detail`.

## `ProviderExecutionStatus` vs. `AIExecutionStatus`

`ProviderExecutionStatus` (`success`/`unavailable`/`failed`/`skipped`) is
deliberately coarser than the existing, unchanged
`codestrata.reporting.modernization_models.AIExecutionStatus`
(`not_requested`/`succeeded`/`authentication_failed`/`provider_failed`/
`parsing_failed`/`validation_failed`). `execution.py` documents — but does
**not** implement or import — a mapping:

| `ProviderExecutionStatus` | `AIExecutionStatus` (unchanged) | Notes |
| --- | --- | --- |
| `success` | `succeeded` | 1:1 |
| `unavailable` | `not_requested` | Capability/dependency unavailable; nothing attempted |
| `failed` | `provider_failed` | Coarse — a real migration would use `AIProviderError.category` to choose a finer status; explicitly deferred past Slice 11.2 |
| `skipped` | `not_requested` | Contract-level skip (e.g. capability unsupported) |

`execution.py` cannot import `codestrata.reporting` (forbidden by the
dependency boundary), so this table's right-hand values are duplicated
literals for documentation/testing only — the real `AIExecutionStatus` enum
and the reporting pipeline that produces it are completely untouched.

## Compatibility with the Slice 11.1 baseline (CR-1..CR-6)

`compatibility.py` restates the six Slice 11.1 compatibility requirement IDs
(as literals, without importing the verification package) and records why
this contract's type system does not violate each one:

| Requirement | How the contract stays compatible |
| --- | --- |
| **CR-1** — exactly one invoke per assess run | `AIProvider.execute()` is a single synchronous call; no retry/fan-out semantics are defined |
| **CR-2** — settings timeout/retries wiring must stay explicit | `ExecutionOptions` fields are optional and read by nothing; no adapter exists to silently wire them |
| **CR-3** — fail-soft must be preserved | `execute()` always returns a result with a status; failures are `FAILED`/`UNAVAILABLE` results, never raised exceptions |
| **CR-4** — Engine provider IDs stay stable | `ProviderId` values are exactly `bedrock`/`openai`; analytics `provider_family` naming is untouched |
| **CR-5** — no real network/credentials required | Constructing requests/results/usage/registry entries requires neither |
| **CR-6** — defaults change only via explicit decision | This package defines no default provider and no default model ID |

The **enforcement** of this table — i.e. loading the real
`build_compatibility_requirements()` from
`verification.ai_provider_baseline.reporting` and cross-checking it against
`compatibility.build_contract_compatibility_statements()` — lives in
[`engine/verification/ai_provider_contracts/baseline_compatibility.py`](../verification/ai_provider_contracts/baseline_compatibility.py),
never in the production `src` package.

## Privacy

Diagnostics (`diagnostics.py`) and serialization (`serialization.py`) never
include: prompt/response text, credentials, filesystem paths, raw model
reference values (only `[model_ref]`), or SDK objects/raw exception text.
`AIProviderError.detail` is bounded and pattern-checked at construction
time. See `engine/tests/ai/provider_contracts/test_privacy.py` and
`engine/verification/ai_provider_contracts/privacy.py`.

## Verification

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_contracts
```

Report: `engine/reports/verification/sv11-2/ai-provider-contract-verification.json`.
Schema: `ai-provider-contract-verification` @ `1.0.0`. Verdict:
`pass_with_limitations` is expected — recorded limitations are
`contracts_not_wired_to_runtime` and `providers_not_migrated`, intentional
properties of this slice, not defects. See
[`engine/verification/ai_provider_contracts/README.md`](../verification/ai_provider_contracts/README.md).

## Unit tests

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_contracts -q
```

## Existing abstraction classification

| Abstraction | Classification | Status |
| --- | --- | --- |
| `codestrata.ai.providers.base.AIModelProvider` | Legacy, capability-specific invoke ABC | Retained unchanged |
| `codestrata.extensions.assess_ai.AssessAIProviderRegistry` | Legacy runtime selection registry | Retained unchanged |
| `codestrata.ai.providers.registry.AIProviderRegistry` | Legacy Phase 5.8 knowledge registry | Retained unchanged |
| `codestrata.ai.providers.models.ModernizationModelRequest`/`ModelInvocationResult` | Adapter-facing, capability-specific current path | Retained unchanged |
| `codestrata.ai.provider_contracts.provider.AIProvider` | Future foundation | New, unwired |
| `codestrata.ai.provider_contracts.registry.AIProviderRegistry` | Future foundation | New, unwired |

See `relationship.build_abstraction_classifications()` for the
machine-readable version of this table. Its `new_unwired` statuses are the
Slice 11.2 classifications and are left as introduced; Slice 11.6 wires
`AIProvider` for OpenAI without redefining the Slice 11.2 record, and no
provider uses `provider_contracts.registry.AIProviderRegistry` yet.

## Related

- [ai-enrichment.md](ai-enrichment.md) — the actual, current provider behavior
- [ai-provider-configuration.md](ai-provider-configuration.md) — Slice 11.3, standardized provider/model configuration
- [ai-provider-execution.md](ai-provider-execution.md) — Slice 11.4, standardized execution/errors/timeouts/retries
- [ai-provider-openai.md](ai-provider-openai.md) — Slice 11.6, the first provider wired onto these contracts
- [`engine/verification/ai_provider_baseline/README.md`](../verification/ai_provider_baseline/README.md) — Slice 11.1
- [`engine/verification/ai_provider_contracts/README.md`](../verification/ai_provider_contracts/README.md) — Slice 11.2 verification
- [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12 privacy / failure isolation
