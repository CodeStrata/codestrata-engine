# Provider Usage Metadata and Capability Discovery (Epic 11, Slice 11.5)

> **Status: foundation, consumed by OpenAI and Bedrock.** Since Slices 11.6 and
> 11.7 both adapters read their static capability profiles
> (`OPENAI_CAPABILITY_PROFILE` / `BEDROCK_CAPABILITY_PROFILE`) — see
> [`ai-provider-openai.md`](ai-provider-openai.md),
> [`ai-provider-bedrock.md`](ai-provider-bedrock.md), and
> [`ai-provider-platform.md`](ai-provider-platform.md). Profiles remain
> intentionally different (`supports_structured_json` is true for OpenAI and
> false for Bedrock). See [`ai-enrichment.md`](ai-enrichment.md) for enrichment
> behavior, and
> [`ai-provider-contracts.md`](ai-provider-contracts.md) /
> [`ai-provider-configuration.md`](ai-provider-configuration.md) /
> [`ai-provider-execution.md`](ai-provider-execution.md) for Slices
> 11.2/11.3/11.4.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.5 adds two small, unwired additions to
`codestrata.ai.provider_contracts`:

1. **Capability discovery** — a static, declared-only
   `ProviderCapabilityProfile` for each known Engine provider (bedrock,
   openai), describing what that provider *would* support if a real adapter
   were built against this contract package: structured JSON, streaming,
   timeout/retry policy honoring, and usage/token reporting.
2. **Usage metadata extension** — `ProviderUsageMetadata` (Slice 11.2) gains
   an optional `completion_status` field (`UsageCompletionStatus`) recording
   what happened during the call the usage was measured for, using the same
   four-value vocabulary as `ProviderExecutionStatus` (Slice 11.4).

This is **not**:

* A migration of the OpenAI or Bedrock providers onto
  `ProviderCapabilityProfile`/the extended `ProviderUsageMetadata`.
* A wiring of capability discovery or usage metadata into `codestrata
  assess`, `AiEnrichmentService`, the provider factory, or `codestrata ai
  doctor`.
* A change to any default, provider selection, credential, wire format,
  fail-soft behavior, prompt, report, or schema.
* A live measurement — the two catalog profiles are hand-authored constants,
  never produced by calling a real provider.
* A cost/pricing/billing feature — `ProviderUsageMetadata` never carries a
  cost, price, or billing field, and never will under this contract (see
  `usage_policy.FORBIDDEN_USAGE_FIELD_NAMES`).
* OpenRouter or any third-party LLM routing/aggregation support *in this
  slice* (OpenRouter arrives in Slices 11.9/11.10 — see
  [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md)).

It is a Slice 11.1/11.2/11.3/11.4-compatible foundation that a later slice
could build a real capability-aware provider selection or usage-reporting path
against, without changing anything about how `codestrata assess --with-ai`
behaves. Slice 11.6 took the first step: the migrated OpenAI adapter declares
its support from `OPENAI_CAPABILITY_PROFILE`. Capability-aware *selection* and
usage *reporting* are still not wired anywhere.

## Ground truth this slice restates (and does not change)

Verified against `codestrata.ai.providers.bedrock`/`openai_provider` and
Slice 11.1's baseline compatibility requirements — not invented:

* **OpenAI's Chat Completions API has a native JSON mode**
  (`response_format={"type": "json_object"}`); Bedrock's Converse API has no
  equivalent, so any structured output today is achieved only by
  prompt-instructing the model. `OPENAI_CAPABILITY_PROFILE.
  supports_structured_json = True`; `BEDROCK_CAPABILITY_PROFILE.
  supports_structured_json = False` with the `"prompt_instruction_only"`
  limitation — this is the same intentional Slice 11.1 OpenAI/Bedrock
  difference, restated as a capability declaration rather than newly
  invented.
* **Neither provider adapter has a streaming code path today** —
  `supports_streaming = False` for both, enforced as a construction-time
  invariant on `ProviderCapabilityProfile` for this slice (no profile may
  declare streaming support until a real streaming implementation exists).
* **Both adapters already extract token usage when the SDK response
  provides it** (`ModelInvocationResult.tokens_used`) — `reports_usage_
  metadata = True`/`reports_token_accounting = True` for both.
* **Neither adapter honors `TimeoutPolicy`/`AIProviderRetryPolicy` today** —
  `supports_timeout_policy = True`/`supports_retry_policy = True` are
  declared as **contract-readiness** flags only (documenting what an
  adapter *could* honor if migrated), always paired with the
  `"not_wired_to_runtime"` limitation.
* **`ProviderExecutionStatus`'s four-value vocabulary** (`success`/
  `unavailable`/`failed`/`skipped`, Slice 11.4) is restated as
  `UsageCompletionStatus` with the identical values — `usage_policy.
  ALLOWED_USAGE_COMPLETION_STATUSES` is asserted equal to `policy.
  ALLOWED_EXECUTION_STATUSES` at import time.

## Why a sibling package, not `ai/providers/`?

Same rationale as Slices 11.2/11.3/11.4 (see
[`ai-provider-contracts.md`](ai-provider-contracts.md)):
`codestrata.ai.providers` hosts the concrete, wired adapter surface that
`codestrata assess` depends on today, and Slice 11.1 inventories its exact
file set as part of its compatibility baseline. Extending
`codestrata.ai.provider_contracts` keeps these new capability/usage types
next to the request/result/configuration/execution types they are meant to
eventually pair with, without touching either the wired `ai/providers/` tree
or the already-verified Slice 11.2/11.3/11.4 module sets.

## Package layout (Slice 11.5 additions)

```text
engine/src/codestrata/ai/provider_contracts/
├── capability_policy.py          Policy IDs, allowed feature-flag/limitation sets
├── capability_schema.py          CURRENT_CAPABILITY_SCHEMA_VERSION + support-checking
├── capability_models.py          ProviderCapabilityDescriptor, ProviderCapabilityProfile
├── capability_catalogs.py        Static, unwired baseline profiles for bedrock/openai
├── capability_validation.py      Standalone profile/identifier validation helpers
├── capability_serialization.py   Deterministic JSON of a profile's diagnostic view
├── capability_diagnostics.py     Safe diagnostic view of a capability profile
├── capability_compatibility.py   Slice 11.1 CR-1..CR-6 + Slice 11.2/11.3/11.4 statements
├── usage_policy.py               Policy IDs, allowed completion-status set, forbidden fields
├── usage.py                      ProviderUsageMetadata (extended) + UsageCompletionStatus
├── usage_validation.py           Standalone usage-record validation helpers
├── usage_serialization.py        Deterministic JSON: private vs. diagnostic usage views
└── usage_diagnostics.py          Safe availability-flags view of a usage record
```

`usage.py` is **extended in place** (one new optional field,
`completion_status`); it is not a new file. The other 12 modules are new.
They sit alongside, and depend only downward on, the Slice 11.2 modules
(`identifiers.py`, `errors.py`, `policy.py`). No Slice 11.2/11.3/11.4 module
is modified to depend on Slice 11.5.

Zero imports from the rest of `codestrata` cross into these modules from
outside the package, and none of them import `codestrata.ai.providers`,
`codestrata.extensions`, `codestrata.reporting`, `codestrata.telemetry`,
`codestrata.analytics`, `codestrata.platform`, `codestrata.datalake`,
`codestrata.cli`, `os`, `pathlib`, `subprocess`, `threading`, `asyncio`,
`signal`, or `openai`/`boto3`/`botocore`/`httpx`/`requests`. This is
enforced by
`engine/tests/ai/provider_contracts/test_capability_runtime_unwired.py`
and by the SV.11.5 verification suite's `dependency_boundary.py`.

## Contract identity

| Identifier | Value |
| --- | --- |
| Capability policy | `community-ai-provider-capability-policy:1.0` |
| Capability contract | `community-ai-provider-capability:1.0` |
| Usage policy | `community-ai-provider-usage-policy:1.0` |
| Usage contract | `community-ai-provider-usage:1.0` |
| Capability schema version | `1.0` |
| Allowed capability feature flags | `supports_structured_json`, `supports_streaming`, `supports_timeout_policy`, `supports_retry_policy`, `reports_usage_metadata`, `reports_token_accounting` |
| Allowed capability limitations | `prompt_instruction_only`, `not_wired_to_runtime`, `streaming_not_implemented` |
| Allowed usage completion statuses | `success`, `unavailable`, `failed`, `skipped` (identical to `ProviderExecutionStatus`) |

The capability schema version is a distinct version namespace from Slice
11.2's `versions.CURRENT_CONTRACT_VERSION`, Slice 11.3's
`configuration_version`, and Slice 11.4's `execution_version`, even though
all four currently equal `"1.0"`. See `capability_schema.py`.

## Core types

### `ProviderCapabilityProfile` (`capability_models.py`)

An immutable, declared-only summary of what a provider supports:

```python
from codestrata.ai.provider_contracts.capability_catalogs import (
    capability_profile_for,
)
from codestrata.ai.provider_contracts.identifiers import ProviderId

profile = capability_profile_for(ProviderId.OPENAI)
profile.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)  # True
profile.supports_structured_json                                 # True
```

Every boolean field is a **capability declaration**, not a runtime
measurement — nothing in this package invokes a real provider to confirm
it. Construction-time invariants: `supported_capability_ids` must be a
non-empty, duplicate-free tuple of `CapabilityId`; every boolean feature
field must actually be a `bool`; `supports_streaming` must be `False` for
this slice's baseline (no streaming implementation exists yet — this is
enforced, not just documented); `limitations` must be a duplicate-free tuple
drawn only from `capability_policy.ALLOWED_CAPABILITY_LIMITATIONS`;
`schema_version` must be a currently-supported value.

### `ProviderCapabilityDescriptor` (`capability_models.py`)

A single-field wrapper around a `CapabilityId`, returned by
`ProviderCapabilityProfile.descriptors()`. Exists so a future slice adding
per-capability feature flags (rather than per-provider ones) has a natural
extension point without breaking `supported_capability_ids`, which stays a
flat tuple of `CapabilityId` for this slice.

### Static catalogs (`capability_catalogs.py`)

```python
from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
    all_known_capability_profiles,
    capability_profile_for,
)
```

| Provider | `supports_structured_json` | `supports_streaming` | `supports_timeout_policy` | `supports_retry_policy` | `reports_usage_metadata` | `reports_token_accounting` | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bedrock` | `False` | `False` | `True` | `True` | `True` | `True` | `prompt_instruction_only`, `not_wired_to_runtime` |
| `openai` | `True` | `False` | `True` | `True` | `True` | `True` | `not_wired_to_runtime` |

Both declare `supported_capability_ids = (CapabilityId.MODERNIZATION_ADVISOR,)`
— the only capability Slice 11.2's `CAPABILITY_PAYLOAD_TYPES` declares.
`KNOWN_PROVIDER_CAPABILITY_PROFILES` is an explicit, literal dict (never
built by scanning a directory or introspecting a registry), so iteration
order and membership are always stable.

### `UsageCompletionStatus` / extended `ProviderUsageMetadata` (`usage.py`)

```python
from codestrata.ai.provider_contracts.usage import (
    ProviderUsageMetadata,
    UsageCompletionStatus,
)

usage = ProviderUsageMetadata(
    input_tokens=128,
    output_tokens=64,
    total_tokens=192,
    latency_ms=250.5,
    completion_status=UsageCompletionStatus.SUCCESS,
)
```

All Slice 11.2 invariants are preserved unchanged (every integer field
non-negative, `latency_ms` non-negative, `total_tokens == input_tokens +
output_tokens` when all three are present). `completion_status` is
optional, defaults to `None`, and — when present — must be a
`UsageCompletionStatus` member. No cost, pricing, billing, prompt, response,
request-ID, or exception-text field exists on this type or ever will (see
`usage_policy.FORBIDDEN_USAGE_FIELD_NAMES`, a documentation constant checked
by the verification suite's `serialization.py`).

### Validation (`capability_validation.py` / `usage_validation.py`)

Standalone functions duplicating each dataclass's `__post_init__`
invariants, for callers/tests that want to validate already-extracted
values (or catalog data obtained from elsewhere) without constructing (or
discarding) an instance: `validate_capability_id_is_known`,
`validate_provider_id_is_known`, `validate_capability_profile`,
`validate_provider_declares_capability`, `validate_usage_metadata`,
`validate_completion_status_is_known`.

### Diagnostics and serialization

* `capability_diagnostics.diagnostic_view_of_capability_profile` — a
  complete, safe projection (a capability profile never carries prompts,
  credentials, or model references in the first place).
* `usage_diagnostics.usage_availability_view` — an **availability-flags**
  view (`has_input_tokens`, `has_completion_status`, ...) reporting which
  fields a provider populated, without the values themselves.
* `capability_serialization.py` / `usage_serialization.py` — deterministic,
  sorted-key canonical JSON. `usage_serialization.py`'s private and
  diagnostic views are **identical** (there is nothing to redact from a
  type that never carries sensitive data), documented explicitly rather
  than assumed.

## Compatibility with the Slice 11.1 baseline (CR-1..CR-6) and Slices 11.2-11.4

`capability_compatibility.py` restates the six Slice 11.1 compatibility
requirement IDs (as literals, without importing the verification package)
and records why the capability/usage domain types do not violate each one:

| Requirement | How the capability/usage domain stays compatible |
| --- | --- |
| **CR-1** — exactly one invoke per assess run | `ProviderCapabilityProfile`/`ProviderUsageMetadata` are read-only value objects never consulted by `AIProvider.execute()`/`AIProviderExecutor` |
| **CR-2** — settings timeout/retries wiring must stay explicit | `supports_timeout_policy`/`supports_retry_policy` always carry `"not_wired_to_runtime"`; nothing reads real settings and forwards them |
| **CR-3** — fail-soft must be preserved | Neither type is on any path `codestrata assess` executes, so neither can introduce a new non-zero exit |
| **CR-4** — Engine provider IDs stay stable | `capability_catalogs.py` covers exactly `ProviderId.BEDROCK`/`ProviderId.OPENAI`, reused unchanged from Slice 11.2 |
| **CR-5** — no real network/credentials required | Every function takes already-constructed value objects; none reads `os.environ`, a file, or makes a network call |
| **CR-6** — defaults change only via explicit decision | This slice defines no default provider and no default model ID; catalogs declare capabilities only, never a preferred provider |

`build_prior_slice_compatibility_notes()` additionally records — as a
separate, explicit statement set — that this slice does not modify anything
Slices 11.2/11.3/11.4 shipped (no shared module imports the other
direction, no existing type is redefined).

The **enforcement** of both statement sets — loading the real
`build_compatibility_requirements()` from
`verification.ai_provider_baseline.reporting` and cross-checking it — lives
in
[`engine/verification/ai_provider_capabilities/compatibility.py`](../verification/ai_provider_capabilities/compatibility.py),
never in the production `src` package.

## Privacy

Capability profiles never carry prompts, credentials, model references, or
SDK objects in the first place. Usage records never carry cost, pricing,
billing, prompt, response, request-ID, or exception-text data — see
`usage_policy.FORBIDDEN_USAGE_FIELD_NAMES`. Diagnostics and serialization
for both types are checked against credential-shaped tokens and absolute
paths by `engine/tests/ai/provider_contracts/` and
`engine/verification/ai_provider_capabilities/privacy.py`.

## Verification

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_capabilities
```

Report: `engine/reports/verification/sv11-5/ai-provider-capability-verification.json`.
Schema: `ai-provider-capability-verification` @ `1.0.0`. Verdict:
`pass_with_limitations` is expected — recorded limitations are
`provider_capabilities_not_consumed`, `usage_metadata_not_wired`,
`providers_not_migrated`, and the historical OpenRouter absence limitation
(later recorded as `openrouter_operational_explicit` / doctor-local readiness),
intentional properties of this slice, not defects. OpenRouter completed in
Slices 11.9–11.11; see `ai_provider_platform_completion`. See
[`engine/verification/ai_provider_capabilities/README.md`](../verification/ai_provider_capabilities/README.md).

## Unit tests

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_contracts/test_capability_*.py tests/ai/provider_contracts/test_usage_*.py -q
```

## Boundaries (explicit, re-stated)

These are the boundaries **of Slice 11.5**. Slice 11.6 later crossed the first
and third of them for OpenAI alone; see
[`ai-provider-openai.md`](ai-provider-openai.md).

* No product-path file (`application/assessment/service.py`,
  `ai/enrichment/service.py`, `ai/providers/bedrock.py`,
  `ai/providers/openai_provider.py`, `ai/providers/factory.py`,
  `ai/providers/doctor.py`, `ai/aws_config.py`, `extensions/assess_ai.py`,
  `config/settings.py`, `config/profiles.py`, `cli/assess.py`) imports any
  Slice 11.5 module. (Slice 11.6 makes `ai/providers/openai_provider.py` the
  one exception, via the OpenAI adapter.)
* `codestrata assess`'s provider selection, defaults, configuration, model
  resolution, timeouts, retries, authentication, error handling, fail-soft
  behavior, and `codestrata ai doctor` are completely unaffected.
* OpenAI and Bedrock are not migrated; no third-party LLM routing provider
  is added — the forbidden name is never spelled out as a literal inside
  `src/codestrata/ai/` (see `capability_policy.py`'s module docstring for
  why). (Slice 11.6 migrates OpenAI; Bedrock and the router-provider
  boundaries still hold.)
* Telemetry, analytics, Community Cloud, Data Lake, VS Code, Cursor, and
  infrastructure are untouched.
