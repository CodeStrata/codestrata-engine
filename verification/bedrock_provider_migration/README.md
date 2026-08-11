# SV.11.7 — AWS Bedrock Provider Migration Verification

Verifies that the Bedrock assess path runs on the Slice 11.2–11.5 provider
contracts via `codestrata.ai.provider_adapters.bedrock`, while preserving the
Slice 11.1 Bedrock baseline (CR-1..CR-6), without live AWS calls or credentials.

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.bedrock_provider_migration
```

Report: `reports/verification/sv11-7/bedrock-provider-migration-verification.json`

## Expected verdict

`pass_with_limitations` with limitations:

- `no_live_bedrock_calls`
- `compatibility_wrappers_remain`
- `operational_retry_remains_conservative`
- `doctor_uses_compatibility_path`
- `common_registry_consolidation_deferred`
- `wall_clock_timeout_sdk_owned`
- `openrouter_operational_explicit`
- `openrouter_doctor_local_readiness_only`

## What this verifies

Capability/config/auth/request/response/usage/error/execution/fail-soft/
registry/doctor/reporting/privacy/dependency/OpenAI-regression/determinism,
plus negative scenarios A–Z from the Slice 11.7 brief.

## What this does not do

Migrate OpenRouter, activate `max_retries=3`, rewrite doctor/CLI, bump Assessment
schema past 1.2, or make the common `AIProviderRegistry` authoritative
(Slice 11.8 Decision B retains the compatibility assess registry).

## Later slices

Slice 11.9 adds an **unwired** OpenRouter adapter (`ProviderId.OPENROUTER`) without assess registration. Operational config/auth remains Slice 11.10.
