# SV.11.10 — OpenRouter Configuration & Authentication Verification

Verifies OpenRouter operational configuration for `codestrata assess --with-ai`:
provider selection (explicit-only), `[ai.openrouter]` settings, model
resolution (no product default), env-backed credentials, base URL / optional
identification headers, lazy client construction, runtime wiring through the
Slice 11.9 adapter, fail-soft mapping, CLI/doctor boundaries, and OpenAI /
Bedrock regressions. Mocked clients only — no live OpenRouter calls.

Doctor local readiness for OpenRouter landed in Slice 11.11 (no client
construction or model invoke). Decision B keeps `AssessAIProviderRegistry`
authoritative. Bedrock remains default.

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.openrouter_configuration
```

Report: `reports/verification/sv11-10/openrouter-configuration-verification.json`

Schema: `openrouter-configuration-verification` @ `1.0.0`

## Expected verdict

`pass_with_limitations` with:

- `no_live_openrouter_calls`
- `model_catalog_not_validated`
- `compatibility_registry_retained`
- `operational_retry_conservative`
- `wall_clock_timeout_client_owned`
- `openrouter_doctor_local_readiness_only`

Optional identification headers (`site_url` / `app_name`) are implemented and
are **not** listed as deferred limitations. Doctor local readiness is covered
in Slice 11.11 (no OpenRouter client construction or model invoke).

## What this does not do

Live OpenRouter catalog validation. Changing Bedrock/OpenAI defaults.

Cross-provider privacy boundaries: Slice 11.12 (`ai_provider_privacy_boundaries`).
