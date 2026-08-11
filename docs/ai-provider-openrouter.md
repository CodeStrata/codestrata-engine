# OpenRouter Provider Adapter (Epic 11, Slice 11.9)

> **Status: adapter implemented; config/auth in 11.10; doctor in 11.11.**
> The OpenRouter package satisfies the Slice 11.2–11.5 provider-platform
> contracts. Assess registration and `[ai.openrouter]` configuration live in
> Slice 11.10
> ([ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md)).
> Doctor local readiness and mocked integration live in Slice 11.11
> ([ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md)).
> See [`ai-provider-platform.md`](ai-provider-platform.md) for Decision B.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.9 adds:

* `ProviderId.OPENROUTER` (`openrouter`) — additive under contract **1.0**
* `codestrata.ai.provider_adapters.openrouter` — OpenAI-compatible Chat
  Completions mapper owned by this adapter (not by reusing the OpenAI adapter
  implementation)
* Static `OPENROUTER_CAPABILITY_PROFILE`
* `OpenRouterAdapterConfiguration` (no API-key values)
* Verification: `engine/verification/openrouter_provider/`
  (`openrouter-provider-verification` @ `1.0.0`)

## What this is not

* A change to Bedrock (still default) or OpenAI behavior
* A consolidation away from Decision B (compatibility assess registry)
* Live OpenRouter calls in Slice 11.9 verification
* Remote API-key or model validation (doctor remains local — Slice 11.11)

## Architecture (this slice)

```text
AIProviderRequest
        ↓
AIProviderExecutor (maximum_attempts=1)
        ↓
OpenRouterProvider
        ↓
OpenAI-compatible request mapping (adapter-owned)
        ↓
Injected mocked client (Slice 11.9) / operational client (Slice 11.10)
        ↓
AIProviderResult
```

## Intentional limitations (Slice 11.9 verification)

* No live OpenRouter calls
* Structured JSON via `response_format` is an adapter capability; model support
  may vary (`model_support_for_structured_json_varies`)

Operational configuration/authentication: Slice 11.10.
Doctor local readiness / mocked integration: Slice 11.11.

## Related

* [ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md)
* [ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md)
* [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12
* [ai-provider-platform.md](ai-provider-platform.md)
* [ai-provider-openai.md](ai-provider-openai.md)
* [ai-provider-bedrock.md](ai-provider-bedrock.md)
* [ai-provider-contracts.md](ai-provider-contracts.md)
