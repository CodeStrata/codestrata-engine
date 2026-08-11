"""Common AI Provider Contracts (CodeStrata v0.2.0 Epic 11, Slices 11.2-11.4).

**Unwired future foundation.** This package defines provider-neutral,
SDK-free domain types for a possible future common AI provider platform:
requests, results, usage, bounded errors, a minimal synchronous provider
protocol, an explicit deterministic registry (Slice 11.2), and a
standardized, privacy-preserving representation of provider/model
configuration (Slice 11.3 — see the "Slice 11.3" section below).

Nothing here is called by any product path today. In particular:

* No production provider (``codestrata.ai.providers.bedrock``/
  ``openai_provider``) implements :class:`~codestrata.ai.provider_contracts.
  provider.AIProvider`.
* ``codestrata.ai.enrichment.service.AiEnrichmentService`` and
  ``codestrata.application.assessment.service`` do not import this package.
* ``codestrata assess`` provider selection, defaults, configuration, model
  resolution, timeouts, retries, authentication, error handling, and
  ``codestrata ai doctor`` are all completely unaffected.

## Why a sibling package instead of extending ``ai/providers/``?

``codestrata.ai.providers`` already hosts the concrete Bedrock/OpenAI
adapters, the legacy ``AIModelProvider`` ABC (``base.py``), and the
capability-specific ``ModernizationModelRequest``/``ModelInvocationResult``
shapes (``models.py``) that the production assess path depends on today.
Adding new, deliberately SDK-free domain contracts into that same package
would either collide with existing names (``AIProviderRegistry`` already
exists there with a different, Phase-5.8 meaning) or blur the line between
"the current, wired, capability-specific adapter surface" and "an unwired,
provider-neutral foundation for possible future work." Slice 11.1 also
inventories the exact file set under ``ai/providers/`` as part of its
boundary characterization; adding files there would look like scope creep
into that baseline. A sibling package keeps both trees independently
readable, testable, and dependency-checkable. See ``relationship.py`` for a
full classification of the existing vs. new abstractions, and
``engine/docs/ai-provider-contracts.md`` for the complete design writeup.

## Layout

| Module | Contents |
| --- | --- |
| ``policy.py`` | Contract/policy identifiers and bounded allowed-value sets |
| ``versions.py`` | ``ContractVersion`` and support-checking |
| ``identifiers.py`` | ``ProviderId``, ``CapabilityId``, ``ProviderModelReference`` |
| ``capabilities.py`` | ``ModernizationAdvisorInput`` and other typed capability payloads |
| ``requests.py`` | ``AIProviderRequest``, ``ExecutionOptions``, ``ResponseExpectation`` |
| ``responses.py`` | ``AIProviderResult``, ``AIProviderResultContent`` |
| ``execution.py`` | ``ProviderExecutionStatus`` and its documented (unwired) status mapping |
| ``usage.py`` | ``ProviderUsageMetadata`` |
| ``errors.py`` | ``ErrorCategory``, ``AIProviderError``, ``ProviderContractValidationError`` |
| ``diagnostics.py`` | Privacy-safe diagnostic views |
| ``provider.py`` | The ``AIProvider`` protocol |
| ``registry.py`` | ``AIProviderRegistry`` (explicit, deterministic) |
| ``validation.py`` | Shared validation helpers |
| ``serialization.py`` | Deterministic JSON serialization of diagnostic views |
| ``compatibility.py`` | Compatibility statements against Slice 11.1 CR-1..CR-6 |
| ``relationship.py`` | Classification of existing vs. new AI abstractions |

## Slice 11.3 — Standardized Provider and Model Configuration

Adds a standardized, privacy-preserving representation of "what
`codestrata assess` would use for an AI provider" as pure, injected-input
domain types. Like Slice 11.2, **this is unwired**: no product-path file
(assess factory, providers, enrichment, doctor, CLI) imports any of these
modules, and no default, precedence, or config key is changed.

| Module | Contents |
| --- | --- |
| ``configuration_policy.py`` | Policy IDs, allowed source/credential sets, defaults |
| ``configuration_sources.py`` | ``SourceCategory`` (cli/env/file/default), ``FieldSource`` |
| ``configuration_precedence.py`` | CLI>env>file>default precedence helper + field notes |
| ``model_configuration.py`` | Pure ``resolve_provider_id``/``resolve_model_reference`` |
| ``adapter_configuration.py`` | ``OpenAIAdapterConfiguration``/``BedrockAdapterConfiguration`` |
| ``configuration_models.py`` | ``AIProviderConfiguration``, ``ProviderCredentialRequirement`` |
| ``legacy_configuration.py`` | ``LegacyConfigurationInput`` — injected settings snapshot |
| ``configuration_projection.py`` | ``project_configuration()`` builder |
| ``configuration_validation.py`` | Standalone cross-field validators |
| ``configuration_diagnostics.py`` | Privacy-safe diagnostic view of a configuration |
| ``configuration_serialization.py`` | Deterministic JSON: private vs. diagnostic views |
| ``configuration_compatibility.py`` | Slice 11.1 CR-1..CR-6 statements + version helpers |

See [`engine/docs/ai-provider-configuration.md`](../../../../docs/ai-provider-configuration.md)
for the full design writeup and ground-truth citations.

## Slice 11.4 — Standardized Execution, Errors, Timeouts, and Retries

Adds a standardized, unwired execution loop (``AIProviderExecutor``) plus
its supporting policy value objects: declarative timeouts, bounded
retry/backoff policy, pure retry decision-making, and safe error
classification. Like Slices 11.2/11.3, **this is unwired**: no product-path
file (assess factory, providers, enrichment, doctor, CLI) imports any of
these modules or constructs an ``AIProviderExecutor``, and no default,
timeout, or retry behavior changes for `codestrata assess` today.

| Module | Contents |
| --- | --- |
| ``execution_policy.py`` | Policy IDs, allowed timeout/backoff sets, default retryable partition |
| ``timeout_policy.py`` | ``TimeoutPolicy``, ``TimeoutScope`` (provider_request/total_execution) |
| ``retry_policy.py`` | ``AIProviderRetryPolicy``, ``max_retries_to_maximum_attempts()`` |
| ``backoff.py`` | ``BackoffPolicy``, ``BackoffStrategy`` (none/fixed/exponential), delay helper |
| ``retry_decision.py`` | Pure ``decide_retry()`` -> ``RetryDecision`` (never sleeps) |
| ``error_classification.py`` | ``ProviderErrorClassification``, classification helpers |
| ``execution_models.py`` | ``AIProviderExecutionContext``, ``AIProviderExecutionResult`` |
| ``executor.py`` | ``AIProviderExecutor`` — the standardized, unwired execution/retry loop |
| ``execution_diagnostics.py`` | Privacy-safe diagnostic view of an execution result |
| ``execution_serialization.py`` | Deterministic JSON: private vs. diagnostic execution views |
| ``execution_compatibility.py`` | Slice 11.1 CR-1..CR-6 statements + version helpers |

``AIProviderExecutor`` never enforces a wall-clock timeout itself (no
threads/signals/``asyncio``) — see ``executor.py``'s module docstring for
why, and [`engine/docs/ai-provider-execution.md`](../../../../docs/ai-provider-execution.md)
for the full design writeup, including the ``maximum_attempts`` vs.
settings-shaped ``max_retries`` distinction.

## Slice 11.5 — Provider Usage Metadata and Capability Discovery

Adds a standardized, unwired way to *describe* what a provider currently
supports (structured JSON, streaming, timeout/retry policy honoring, usage
reporting) via a static, declared-only capability catalog, and extends
``ProviderUsageMetadata`` (Slice 11.2) with an optional
``completion_status`` field. Like Slices 11.2/11.3/11.4, **this is
unwired**: no product-path file (assess factory, providers, enrichment,
doctor, CLI) imports any of these modules, no default/selection/config/
timeout/retry/error/doctor/prompt/report/schema behavior changes for
`codestrata assess` today, and no runtime provider behavior changes.

| Module | Contents |
| --- | --- |
| ``capability_policy.py`` | Policy IDs, allowed feature-flag/limitation sets |
| ``capability_schema.py`` | ``CURRENT_CAPABILITY_SCHEMA_VERSION`` + support-checking |
| ``capability_models.py`` | ``ProviderCapabilityDescriptor``, ``ProviderCapabilityProfile`` |
| ``capability_catalogs.py`` | Static, unwired baseline profiles for bedrock/openai |
| ``capability_validation.py`` | Standalone profile/identifier validation helpers |
| ``capability_serialization.py`` | Deterministic JSON of a profile's diagnostic view |
| ``capability_diagnostics.py`` | Safe diagnostic view of a capability profile |
| ``capability_compatibility.py`` | Slice 11.1 CR-1..CR-6 + Slice 11.2/11.3/11.4 statements |
| ``usage_policy.py`` | Policy IDs, allowed completion-status set, forbidden field names |
| ``usage.py`` | ``ProviderUsageMetadata`` (extended) + ``UsageCompletionStatus`` |
| ``usage_validation.py`` | Standalone usage-record validation helpers |
| ``usage_serialization.py`` | Deterministic JSON: private vs. diagnostic usage views |
| ``usage_diagnostics.py`` | Safe availability-flags view of a usage record |

``ProviderCapabilityProfile`` and the extended ``ProviderUsageMetadata`` are
never consulted by any provider adapter, executor, or CLI command today —
see [`engine/docs/ai-provider-capabilities.md`](../../../../docs/ai-provider-capabilities.md)
for the full design writeup and ground-truth citations.
"""

from __future__ import annotations

__all__: list[str] = []
