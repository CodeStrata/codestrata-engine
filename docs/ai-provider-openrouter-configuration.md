# OpenRouter Configuration and Authentication (Epic 11, Slice 11.10)

> **Status: operational configuration wired; doctor local readiness in 11.11.**
> OpenRouter is an explicit, non-default assess provider. Configuration and
> API-key resolution work through existing selection/factory paths. Doctor
> readiness is local-only
> ([ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md)). See
> [`ai-provider-openrouter.md`](ai-provider-openrouter.md) for the Slice 11.9
> adapter and [`ai-provider-platform.md`](ai-provider-platform.md) for Decision B.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.10 adds:

* Explicit assess selection of `provider = "openrouter"`
* Isolated `[ai.openrouter]` settings (model, `api_key_env`, optional
  `base_url` / `site_url` / `app_name`, timeout/retry representation)
* Environment model overlay: `CODESTRATA_OPENROUTER_MODEL_ID`
* Lazy API-key lookup from the configured environment-variable **name**
  (default `OPENROUTER_API_KEY`) at the OpenRouter client boundary only
* Compatibility wrapper `OpenRouterAIModelProvider` registered in
  `AssessAIProviderRegistry`
* Verification: `engine/verification/openrouter_configuration/`
  (`openrouter-configuration-verification` @ `1.0.0`)

## What this is not

* A change to the default provider (Bedrock remains default)
* Automatic selection based on API-key presence
* Fallback to OpenAI or Bedrock
* Plaintext API-key fields in TOML or canonical configuration
* New CLI secret/base-url/model/header flags
* Live OpenRouter network calls in verification
* Common-registry consolidation (Decision B retained)
* Retry activation beyond `maximum_attempts=1`
* Remote API-key / model validation (doctor is local — see Slice 11.11)

## Runtime posture

| Request | Provider |
| --- | --- |
| No AI (`--no-ai`) | No provider/client/credential resolution |
| Default AI | Bedrock |
| Explicit `openai` | Migrated OpenAI adapter |
| Explicit `bedrock` | Migrated Bedrock adapter |
| Explicit `openrouter` | OpenRouter configuration → credential resolution → Slice 11.9 adapter |
| Unknown | Configuration error |

No silent fallback. Exactly one provider invocation when AI runs.

## Configuration

```toml
[ai]
provider = "openrouter"

[ai.openrouter]
model = "openai/gpt-4o-mini"   # required — no product default
api_key_env = "OPENROUTER_API_KEY"
base_url = ""                  # optional override; default is adapter-owned HTTPS URL
site_url = ""                  # optional HTTP-Referer (HTTPS URL)
app_name = ""                  # optional X-Title (bounded)
timeout_seconds = 60
max_retries = 3                # represented only; operational attempts remain 1
```

### Model resolution

1. CLI `--model-id` (existing generic flag)
2. `CODESTRATA_OPENROUTER_MODEL_ID`
3. `[ai.openrouter].model`
4. **Error** — OpenRouter has no product default model

The Slice 11.9 test-only model is never a product default.

### API key

* Configuration stores only the environment-variable **name**
* Value is read only inside the OpenRouter client boundary
* Missing / empty / whitespace-only → bounded missing-configuration failure
* Never falls back to `OPENAI_API_KEY` or other variables unless
  `api_key_env` is explicitly set to that name
* Never enters diagnostics, reports, logs, or exception text

### Base URL and optional headers

* Default base URL is adapter-owned (`https://openrouter.ai/api/v1`)
* Overrides must be HTTPS, without credentials, query, or fragment
* Raw URL is excluded from public diagnostics and verification reports
* Optional `site_url` / `app_name` map to `HTTP-Referer` / `X-Title` only
  inside the client boundary — never derived from repository/customer/machine
  identity; never reported in diagnostics

## Registry

**Decision B remains in force.** `AssessAIProviderRegistry` is authoritative.
OpenRouter is registered as `openrouter` alongside `bedrock` and `openai`.
Common `AIProviderRegistry` consolidation remains deferred.

## Client construction

* Lazy — only when OpenRouter is selected and invocation begins
* Injected client wins in tests (no real network)
* Compatible OpenAI SDK supplies the HTTP client (reuse `codestrata[openai]`)
* `ProviderId` remains `OPENROUTER`; OpenAI adapter is not instantiated
* No client when AI is disabled or another provider is selected

## Doctor / CLI

* Doctor local readiness: Slice 11.11
  ([ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md))
* Existing CLI provider/model options accept OpenRouter; no new secret flags
* `codestrata ai --provider openrouter` shows the setup guide

## Verification

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.openrouter_configuration
```

Report: `reports/verification/sv11-10/openrouter-configuration-verification.json`

Mocked only. No live credentials. Deterministic double-run required.

## Related

* [ai-provider-openrouter.md](ai-provider-openrouter.md) — Slice 11.9 adapter
* [ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md) — Slice 11.11
* [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12
* [ai-provider-platform.md](ai-provider-platform.md) — Decision B / shared guarantees
* [ai-provider-configuration.md](ai-provider-configuration.md) — Slice 11.3 contracts
* [ai-enrichment.md](ai-enrichment.md) — fail-soft ownership
