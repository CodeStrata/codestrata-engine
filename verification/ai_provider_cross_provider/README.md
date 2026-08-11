# SV.11.8 — Cross-Provider Contract Verification

Verifies that migrated OpenAI and Bedrock both satisfy the Slice 11.2–11.5
provider-platform contracts while preserving intentional provider-specific
differences. No live provider calls. OpenRouter is assess-registered
(explicit-only, Slice 11.10); doctor local readiness landed in Slice 11.11.
Decision B retains the compatibility registry.

## Run

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_cross_provider
```

Report: `reports/verification/sv11-8/ai-provider-cross-provider-verification.json`

Schema: `ai-provider-cross-provider-verification` @ `1.0.0`

## Registry decision

**B — Compatibility registry retained.**

`AssessAIProviderRegistry` remains authoritative for `codestrata assess`.
The contracts `AIProviderRegistry` stays available as an unwired platform
registry. Consolidation is deferred (see `REGISTRY_DECISION_RATIONALE` in
`contract.py`).

## Expected verdict

`pass_with_limitations` with limitations:

- `no_live_provider_calls`
- `compatibility_wrappers_remain`
- `common_registry_consolidation_deferred`
- `wall_clock_timeout_client_owned`
- `operational_retry_remains_conservative`
- `doctor_uses_compatibility_path`
- `openrouter_operational_explicit`
- `openrouter_doctor_local_readiness_only`

## Module layout

Core modules implement checks; thin alias modules match the Slice 11.8 brief
names and re-export the same runners:

| Brief name | Implementation |
| --- | --- |
| `inventory`, `baseline_compatibility`, `scenarios`, `determinism` | `matrix.py` |
| `provider_selection` | `provider_registry.py` |
| `model_resolution`, `authentication`, `capabilities` | `configuration.py` |
| `requests`, `responses`, `usage`, `errors`, `execution`, `retries` | `contracts_parity.py` |
| `fail_soft`, `doctor`, `cli`, `reporting_boundary`, `privacy`, `dependency_boundary` | `boundaries.py` |

Slice 11.12 extends this with authoritative privacy and failure-isolation verification (`ai_provider_privacy_boundaries`).
