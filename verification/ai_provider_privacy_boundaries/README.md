# SV.11.12 — AI Provider Privacy Boundary Verification

Verifies privacy, failure-isolation, and architecture boundaries across
`bedrock`, `openai`, and `openrouter`: credential/prompt/response/model/error
privacy, diagnostic allowlists, configuration and execution boundaries, retry
and interrupt safety, doctor/CLI surfaces, telemetry/analytics isolation,
Platform/Data Lake isolation, VS Code/Cursor isolation, packaging/public
export, and Registry Decision B. Mocked clients only — no live provider calls.

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_privacy_boundaries
```

Report: `reports/verification/sv11-12/ai-provider-privacy-boundary-verification.json`

Schema: `ai-provider-privacy-boundary-verification` @ `1.0.0`

## Expected verdict

`pass_with_limitations` with:

- `no_live_provider_calls`
- `no_real_credentials`
- `no_remote_model_validation`
- `no_remote_credential_validation`
- `compatibility_registry_retained`
- `operational_retry_conservative`
- `wall_clock_timeout_client_owned`
- `no_full_external_extension_host_or_cloud_validation`

## What this does not do

Slice 11.13 completion. Live provider validation. Changing Bedrock/OpenAI/
OpenRouter defaults or selection. Consolidating registries.
