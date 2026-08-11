# SV.11.9 — OpenRouter Provider Implementation Verification

Verifies the OpenRouter adapter against Slice 11.2–11.5 contracts with injected
mocked clients only. Slice 11.10 registered OpenRouter in
`AssessAIProviderRegistry` (explicit-only; Bedrock remains default). Decision B
keeps Assess authoritative. No live network. Doctor local readiness landed in
Slice 11.11 (no OpenRouter client construction or model invoke).

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.openrouter_provider
```

Report: `reports/verification/sv11-9/openrouter-provider-verification.json`

Schema: `openrouter-provider-verification` @ `1.0.0`

## Expected verdict

`pass_with_limitations` with:

- `no_live_openrouter_calls`
- `model_specific_feature_support_not_probed`
- `operational_retry_conservative`
- `openrouter_doctor_local_readiness_only`

## Common-contract decision

Additive `ProviderId.OPENROUTER` under provider contract **1.0** (no version bump).

## What this does not do

Configuration/auth live in Slice 11.10. Doctor local readiness is in Slice 11.11.
Bedrock remains the default provider; OpenRouter is explicit-only.

Privacy/failure-isolation across all providers: Slice 11.12 (`ai_provider_privacy_boundaries`).
