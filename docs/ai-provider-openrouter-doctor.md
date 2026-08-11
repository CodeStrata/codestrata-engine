# OpenRouter Doctor and Mocked Integration (Epic 11, Slice 11.11)

> **Status: doctor local readiness + mocked integration verified.**
> `codestrata ai doctor` reports OpenRouter readiness without contacting
> OpenRouter. End-to-end assess enrichment is verified with an injected mocked
> client only. Slice 11.12 privacy boundaries and Slice 11.13 Epic 11 completion
> are verified; see [`ai-provider-security-boundaries.md`](ai-provider-security-boundaries.md)
> and `ai_provider_platform_completion`.
> See [`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md)
> for configuration/auth and [`ai-provider-openrouter.md`](ai-provider-openrouter.md)
> for the adapter.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.11 adds:

* OpenRouter local readiness in `codestrata.ai.providers.doctor`
* Bounded readiness categories (ready / model_missing / credential_missing /
  dependency_missing / invalid_configuration / …)
* Setup guide: `codestrata ai --provider openrouter`
* Mocked end-to-end integration verification
  (`engine/verification/openrouter_doctor_integration/`,
  schema `openrouter-doctor-integration-verification` @ `1.0.0`)

## What doctor does

Preferred flow:

```text
Read validated configuration
        ↓
Determine selected provider
        ↓
Evaluate OpenRouter local readiness
        ↓
Return bounded readiness result
        ↓
No network · no model invocation · no client send
```

Checks (when relevant):

| Check | Reports |
| --- | --- |
| Dependency | OpenAI-compatible extra importable (`codestrata[openai]`) |
| API key | presence only via configured env var name |
| Model | configured vs missing (value never printed) |
| Base URL | `default` / `custom_valid` / `invalid` (URL never printed) |
| Optional site_url / app_name | configured booleans; HTTPS/bounds only |

Doctor does **not**:

* execute the Modernization Advisor
* construct a prompt
* call OpenRouter
* validate the API key remotely
* validate model availability remotely
* print API-key values, prefixes, lengths, models, URLs, or headers
* construct an OpenRouter/OpenAI network client

## Readiness vs runtime

| Surface | Meaning |
| --- | --- |
| Doctor | Local readiness only |
| Runtime (mocked in SV.11.11) | Injected client execution outcome |

A doctor “ready” result does **not** prove provider connectivity.

## Exit behavior

Unchanged conventions:

* Active provider unsupported or not `Configured` → exit **1**
* Active provider `Configured` (inactive providers may show ✗) → exit **0**

OpenRouter follows the same rule: not ready only fails the run when it is the
**active** `[ai].provider`.

## Human-readable labels

Examples:

* `✓ OpenRouter configured`
* `✗ OpenRouter model configuration missing`
* `✗ OpenRouter API key not available`
* `✗ OpenRouter client dependency unavailable`
* `✗ OpenRouter invalid configuration`

## Mocked integration

Verification covers configuration → selection → credential resolution →
provider construction → `AIProviderExecutor` → injected client → legacy bridge,
including success and a failure matrix (auth, timeout, rate limit, invalid
model, malformed response, …). Exactly one invocation. No OpenAI/Bedrock
fallback. Assessment schema remains **1.2**. Doctor diagnostics never enter
customer reports.

## Verification

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.openrouter_doctor_integration
```

Report: `reports/verification/sv11-11/openrouter-doctor-integration-verification.json`

## Related

* [ai-provider-openrouter.md](ai-provider-openrouter.md)
* [ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md)
* [ai-provider-platform.md](ai-provider-platform.md)
* [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12
* [ai-enrichment.md](ai-enrichment.md)
* [cli-reference.md](cli-reference.md)
