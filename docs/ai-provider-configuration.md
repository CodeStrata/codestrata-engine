# Standardized Provider and Model Configuration (Epic 11, Slice 11.3)

> **Status: foundation, consumed by OpenAI, Bedrock, and OpenRouter adapters.**
> Since Slices 11.6/11.7/11.10 adapters build Slice 11.3 configuration types for
> diagnostics — see [`ai-provider-openai.md`](ai-provider-openai.md),
> [`ai-provider-bedrock.md`](ai-provider-bedrock.md),
> [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md),
> and [`ai-provider-platform.md`](ai-provider-platform.md). Assess still resolves
> provider/model via existing settings precedence; `timeout_seconds` /
> `max_retries` settings remain operationally conservative. See
> [`ai-enrichment.md`](ai-enrichment.md) for enrichment behavior, and
> [`ai-provider-contracts.md`](ai-provider-contracts.md) for Slice 11.2, the
> request/result/registry foundation this slice extends, and
> [`ai-provider-execution.md`](ai-provider-execution.md) /
> [`ai-provider-capabilities.md`](ai-provider-capabilities.md) for Slices
> 11.4/11.5.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.3 adds a standardized, privacy-preserving
representation of **"what `codestrata assess` would use for an AI
provider"** — provider ID, model reference, adapter-specific settings,
credential requirements, and the CLI/environment/file/default provenance of
each resolved value — as pure, injected-input domain types under
`codestrata.ai.provider_contracts` (the same Slice 11.2 sibling package, not
`codestrata.ai.providers`).

This is **not**:

* A migration of the OpenAI or Bedrock providers to these new types.
* A change to `codestrata assess` provider selection, defaults, model
  resolution precedence, configuration file keys, timeouts, retries,
  authentication, error handling, or `codestrata ai doctor`.
* A wiring of these types to the Slice 11.2 `AIProvider` protocol.
* OpenRouter support in *this* slice (added later in Slices 11.9/11.10 — see
  [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md)).
* Wired into the assessment product path in any way — every function in this
  slice takes already-extracted plain values as arguments and performs no
  filesystem access, no environment variable reads, and constructs no
  provider client.

It is a Slice 11.1/11.2-compatible foundation that a future slice (11.5+,
**not started here**) could build production configuration loading against,
without changing anything about how `codestrata assess --with-ai` behaves
today. Slice 11.4 (see
[`ai-provider-execution.md`](ai-provider-execution.md)) adds a
complementary, equally unwired standardized execution/retry/timeout shape
alongside this configuration representation.

## Ground truth this slice restates (and does not change)

Verified against `codestrata.ai.providers.factory`,
`codestrata.config.settings`, and `codestrata.ai.aws_config` — not invented:

* **Provider IDs**: `bedrock` (default), `openai` — matches
  `codestrata.config.settings.AiSettings.provider` and
  `verification.ai_provider_baseline.contract.ENGINE_PROVIDER_IDS`.
* **`codestrata assess` has no `--provider` CLI flag** and no dedicated
  provider-selection environment variable — provider selection is
  `[ai].provider` in `codestrata.toml`, or the `"bedrock"` default.
* **Model resolution** (`resolve_assess_model_id`), highest precedence first:
  1. CLI `--model-id`
  2. The provider-appropriate environment variable
     (`CODESTRATA_OPENAI_MODEL_ID` for `openai`,
     `CODESTRATA_BEDROCK_MODEL_ID` for `bedrock`)
  3. The configuration file value (`[ai.openai].answer_model` /
     `[ai.bedrock].model_id`)
  4. The hardcoded default (`gpt-4o-mini` / `amazon.nova-lite-v1:0`)
* **Asymmetry preserved, not smoothed over**: `CODESTRATA_OPENAI_MODEL_ID` is
  read only at model-resolution time and never overlaid into settings;
  `CODESTRATA_BEDROCK_MODEL_ID` is **both** overlaid into settings by
  `apply_environment_overlays` **and** read again at resolution time. This
  slice's `model_configuration.py` accepts an already-selected
  `env_model_id` from the caller precisely so it never has to (re)implement
  this asymmetry itself — the caller is responsible for picking the right
  environment variable for the active provider before calling.
* **Settings fields actually used on the assess path**: `ai.provider`;
  `openai.api_key_env`, `openai.base_url` (if set), `openai.answer_model`;
  `bedrock.model_id`; `aws.profile`, `aws.region`, `ai.bedrock.region` (via
  `resolve_aws_config`).
* **`timeout_seconds`/`max_retries`** are declared on `BedrockSettings` and
  `OpenAISettings` but are **not** read by the assess provider factory —
  there is no CLI or environment override path for either today. This slice
  represents them as optional, unwired data and never claims otherwise.
* **Not present**: `organization`, `project` (OpenAI), or an `endpoint_url`
  override (Bedrock) — this slice does not invent these fields.
* **Assess CLI**: `--with-ai`/`--no-ai`, `--model-id` (no `--provider` flag).

## Why a sibling package, not `ai/providers/`?

Same rationale as Slice 11.2 (see [`ai-provider-contracts.md`](ai-provider-contracts.md)):
`codestrata.ai.providers` hosts the concrete, wired adapter surface that
`codestrata assess` depends on today, and Slice 11.1 inventories its exact
file set as part of its compatibility baseline. Extending
`codestrata.ai.provider_contracts` — rather than creating a third package —
keeps this new configuration representation next to the request/result types
it is meant to eventually pair with, without touching either the wired
`ai/providers/` tree or Slice 11.2's already-verified module set.

## Package layout (Slice 11.3 additions)

```text
engine/src/codestrata/ai/provider_contracts/
├── configuration_policy.py         Policy IDs, allowed source/credential sets, defaults
├── configuration_sources.py        SourceCategory (cli/environment/configuration_file/default), FieldSource
├── configuration_precedence.py     Generic CLI>env>file>default helper + field-specific notes
├── model_configuration.py          Pure resolve_provider_id / resolve_model_reference
├── adapter_configuration.py        OpenAIAdapterConfiguration / BedrockAdapterConfiguration
├── configuration_models.py         AIProviderConfiguration, ProviderCredentialRequirement
├── legacy_configuration.py         LegacyConfigurationInput — injected settings snapshot
├── configuration_projection.py     project_configuration() builder
├── configuration_validation.py     Standalone cross-field validators
├── configuration_diagnostics.py    Privacy-safe diagnostic view of a configuration
├── configuration_serialization.py  Deterministic JSON: private vs. diagnostic views
└── configuration_compatibility.py  Slice 11.1 CR-1..CR-6 statements + version helpers
```

These 12 modules sit alongside, and depend only downward on, the Slice 11.2
modules (`identifiers.py`, `requests.py`, `errors.py`, `policy.py`). No
Slice 11.2 module is modified to depend on Slice 11.3.

Zero imports from the rest of `codestrata` cross into these modules from
outside the package, and none of them import `codestrata.ai.providers`,
`codestrata.extensions`, `codestrata.reporting`, `codestrata.telemetry`,
`codestrata.analytics`, `codestrata.platform`, `codestrata.datalake`,
`codestrata.cli`, `os`, `pathlib`, `subprocess`, or
`openai`/`boto3`/`botocore`/`httpx`/`requests`. This is enforced by
`engine/tests/ai/provider_contracts/test_configuration_runtime_unwired.py`
and `test_legacy_configuration.py`, and by the SV.11.3 verification suite's
`dependency_boundary.py`.

## Contract identity

| Identifier | Value |
| --- | --- |
| Policy | `community-ai-provider-configuration-policy:1.0` |
| Contract | `community-ai-provider-configuration:1.0` |
| Contract / configuration version | `1.0` |
| Source categories | `cli`, `environment`, `configuration_file`, `default` |
| Credential kinds | `api_key` (OpenAI), `aws_default_chain` (Bedrock), `aws_profile` (Bedrock, optional) |
| Credential availability statuses | `present`, `absent`, `unknown` |
| Default provider ID | `bedrock` |
| Default model IDs | `amazon.nova-lite-v1:0` (bedrock), `gpt-4o-mini` (openai) |

`configuration_version` (on `AIProviderConfiguration`) is a distinct version
namespace from Slice 11.2's `versions.CURRENT_CONTRACT_VERSION` (the
request/response envelope version), even though both currently equal
`"1.0"`. See `configuration_compatibility.py`.

## Core types

### `SourceCategory` / `FieldSource` (`configuration_sources.py`)

`SourceCategory` is the closed set of places a resolved value can come from:
`cli`, `environment`, `configuration_file`, `default`. `FieldSource` pairs a
field name with the category that supplied its value — never the value
itself.

### `resolve_provider_id` / `resolve_model_reference` (`model_configuration.py`)

Pure functions mirroring `create_assess_ai_provider`'s provider selection and
`resolve_assess_model_id`'s model resolution exactly, but taking
already-extracted candidate values as arguments:

```python
from codestrata.ai.provider_contracts.model_configuration import (
    resolve_model_reference,
    resolve_provider_id,
)

provider_id, provider_source = resolve_provider_id(file_provider=None)
# provider_id == ProviderId.BEDROCK, provider_source == SourceCategory.DEFAULT

model_reference, model_source = resolve_model_reference(
    provider_id=provider_id,
    cli_model_id=None,
    env_model_id=None,
    file_model_id=None,
)
# model_reference.value == "amazon.nova-lite-v1:0", model_source == SourceCategory.DEFAULT
```

**No function in this module reads `os.environ` or any file.** Callers
extract the relevant CLI-argument/environment-variable/settings value first.

### `OpenAIAdapterConfiguration` / `BedrockAdapterConfiguration` (`adapter_configuration.py`)

Type-safe, privacy-preserving per-provider settings. `validate_adapter_matches_provider`
rejects pairing the wrong adapter type with a `ProviderId` (an
`OpenAIAdapterConfiguration` may never be paired with `ProviderId.BEDROCK`
and vice versa).

* **OpenAI**: `api_key_env_name` (the environment variable *name*, never its
  value), `api_key_present` (bool), `base_url`/`base_url_configured`
  (`base_url` is stored opaquely for potential future adapter construction
  but is never emitted by `.redacted()` or any diagnostics/serialization
  path — only `base_url_configured: bool` is), `max_retries` (declared,
  unwired).
* **Bedrock**: `region_configured`/`profile_configured` (presence booleans
  only — never the actual region string or AWS profile name, which are
  credential-adjacent), `max_retries` (declared, unwired). No
  `endpoint_url` field — Bedrock has no configurable endpoint override
  today.

### `AIProviderConfiguration` (`configuration_models.py`)

The central immutable value object: `configuration_version`, `provider_id`,
`model_reference`, `capability_id`, `execution_options`,
`adapter_configuration`, `source_trace` (tuple of `FieldSource`, at minimum
covering `provider_id` and `model_reference`), `credential_requirements`,
`limitations`, `ai_requested`. Validated at construction time: adapter type
must match `provider_id`; `source_trace` must cover `provider_id` and
`model_reference`; `credential_requirements` must all reference the same
`provider_id`; `limitations` must be non-empty.

### `ProviderCredentialRequirement` (`configuration_models.py`)

`provider_id`, `credential_kind`, `required`, `source_category`,
`availability_status` — **never** a credential value. Bedrock always
requires `aws_default_chain` (boto3's default credential provider chain,
`availability_status="unknown"` since checking it for real would require a
network call this package never makes); an optional `aws_profile`
requirement is added when a profile is configured. OpenAI requires exactly
one `api_key` requirement, with `availability_status` reflecting whether the
named environment variable appears to be set.

### `LegacyConfigurationInput` / `legacy_configuration_input_from_mapping` (`legacy_configuration.py`)

A plain, already-extracted snapshot of the assess-relevant settings surface
— the translation boundary between "real settings/CLI/environment values"
and this package's pure domain functions. Performs no filesystem access, no
environment variable reads, and constructs no provider client;
`legacy_configuration_input_from_mapping` only shapes and validates a plain
`Mapping` the caller already built.

### `project_configuration` (`configuration_projection.py`)

Assembles a `LegacyConfigurationInput` into a complete, validated
`AIProviderConfiguration` — resolving provider/model, building the correct
adapter configuration and credential requirements, and always recording
`limitations = UNWIRED_LIMITATIONS`:

```python
from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput

configuration = project_configuration(LegacyConfigurationInput())
# configuration.provider_id == ProviderId.BEDROCK (default)
# configuration.model_reference.value == "amazon.nova-lite-v1:0" (default)
# configuration.limitations == (
#     "configuration_not_wired", "providers_not_migrated",
#     "credential_resolution_deferred", "timeout_retry_execution_deferred",
# )
```

## Compatibility with the Slice 11.1 baseline (CR-1..CR-6)

`configuration_compatibility.py` restates the six Slice 11.1 compatibility
requirement IDs (as literals, without importing the verification package)
and records why the configuration domain types do not violate each one:

| Requirement | How the configuration domain stays compatible |
| --- | --- |
| **CR-1** — exactly one invoke per assess run | `AIProviderConfiguration` is a resolved, read-only snapshot; it defines no retry/fan-out semantics and is never consulted by `AiEnrichmentService.run()` |
| **CR-2** — settings timeout/retries wiring must stay explicit | `timeout_seconds`/`max_retries` are represented as optional, unwired data; nothing reads the real settings fields and forwards them to a provider call |
| **CR-3** — fail-soft must be preserved | Building a configuration only raises `ProviderContractValidationError` for malformed input to this package's own pure functions; it is never called by `codestrata assess` |
| **CR-4** — Engine provider IDs stay stable | `resolve_provider_id()`/`ProviderId` values are exactly `bedrock`/`openai`, reused unchanged from Slice 11.2 |
| **CR-5** — no real network/credentials required | Every resolution function takes already-extracted plain values; none read `os.environ`, read a file, or construct a provider client |
| **CR-6** — defaults change only via explicit decision | `DEFAULT_PROVIDER_ID`/`DEFAULT_MODEL_BY_PROVIDER` are literal restatements of the real production defaults, unchanged by this slice |

The **enforcement** of this table — loading the real
`build_compatibility_requirements()` from
`verification.ai_provider_baseline.reporting` and cross-checking it, plus
cross-checking the default provider/model IDs against the loaded baseline —
lives in
[`engine/verification/ai_provider_configuration/baseline_compatibility.py`](../verification/ai_provider_configuration/baseline_compatibility.py),
never in the production `src` package.

## Privacy

Diagnostics (`configuration_diagnostics.py`) and the diagnostic
serialization path (`configuration_serialization.py`) never include: the raw
model reference value (only `ProviderModelReference.redacted()`), credential
values (only presence booleans / environment variable *names*), the OpenAI
`base_url` value (only `base_url_configured`), AWS profile/region values
(only presence booleans), or filesystem paths. A separate
`private_view_of_configuration`/`serialize_configuration_private` exists for
internal test/debugging use only (it may include an adapter-private raw
`base_url` if one was constructed) and must never be written to a log,
report, or CLI output. See
`engine/tests/ai/provider_contracts/test_configuration_privacy.py` and
`engine/verification/ai_provider_configuration/privacy.py`.

## Verification

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_configuration
```

Report: `engine/reports/verification/sv11-3/ai-provider-configuration-verification.json`.
Schema: `ai-provider-configuration-verification` @ `1.0.0`. Verdict:
`pass_with_limitations` is expected — recorded limitations are
`configuration_not_wired`, `providers_not_migrated`,
`credential_resolution_deferred`, and `timeout_retry_execution_deferred`,
intentional properties of this slice, not defects. See
[`engine/verification/ai_provider_configuration/README.md`](../verification/ai_provider_configuration/README.md).

## Unit tests

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/ai/provider_contracts -q
PYTHONPATH=src:. ../.venv/bin/python -m pytest tests/verification/ai_provider_configuration -q
```

## Related

- [ai-enrichment.md](ai-enrichment.md) — the actual, current provider behavior
- [ai-provider-contracts.md](ai-provider-contracts.md) — Slice 11.2, the request/result/registry foundation
- [ai-provider-execution.md](ai-provider-execution.md) — Slice 11.4, standardized execution/errors/timeouts/retries
- [ai-provider-openai.md](ai-provider-openai.md) — Slice 11.6, how the OpenAI adapter uses this configuration shape
- [`engine/verification/ai_provider_baseline/README.md`](../verification/ai_provider_baseline/README.md) — Slice 11.1
- [`engine/verification/ai_provider_contracts/README.md`](../verification/ai_provider_contracts/README.md) — Slice 11.2 verification
- [`engine/verification/ai_provider_configuration/README.md`](../verification/ai_provider_configuration/README.md) — Slice 11.3 verification
- [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12 privacy / failure isolation
