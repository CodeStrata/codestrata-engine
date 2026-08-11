# SV.11.11 — OpenRouter Doctor & Integration Verification

Verifies privacy-safe OpenRouter readiness in `codestrata ai doctor` and mocked
end-to-end integration for the explicit OpenRouter assess path: local readiness
categories, credential/model/dependency presence, HTTPS configuration shape,
exit semantics, injected-client success and failure matrix, provider-selection
isolation, fail-soft ownership, Assessment schema 1.2 boundary, and OpenAI /
Bedrock regressions. Mocked clients only — no live OpenRouter calls.

Decision B keeps `AssessAIProviderRegistry` authoritative. Bedrock remains
default. Credentials and models are not remotely validated.

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.openrouter_doctor_integration
```

Report: `reports/verification/sv11-11/openrouter-doctor-integration-verification.json`

Schema: `openrouter-doctor-integration-verification` @ `1.0.0`

## Expected verdict

`pass_with_limitations` with:

- `no_live_openrouter_calls`
- `credential_not_remotely_validated`
- `model_not_remotely_validated`
- `compatibility_registry_retained`
- `operational_retry_conservative`
- `wall_clock_timeout_client_owned`
- `no_full_external_extension_host_or_cloud_validation`

## What this does not do

Slice 11.12 privacy-verification expansion. Live OpenRouter catalog or
connectivity validation. Changing Bedrock/OpenAI defaults.
