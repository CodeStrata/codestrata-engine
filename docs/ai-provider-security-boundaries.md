# AI Provider Security and Privacy Boundaries

Epic 11 Slice 11.12 documents the privacy, failure-isolation, and architecture
boundaries that apply to the three Engine AI providers: **bedrock**, **openai**,
and **openrouter**.

This is a security-boundary overview. It does **not** claim absolute anonymity,
perfect security, or live-provider validation.

## Private vs public

Provider credentials, prompts, responses, exact model IDs, request IDs, endpoints,
headers, profile/region values, and raw exception text may exist transiently on
the **private** execution path (typed request objects, adapter wire mapping,
injected/SDK client call).

They must not enter **public** surfaces:

- adapter / result / execution diagnostics
- doctor redacted readiness output
- verification reports
- customer assessment reports (except the approved Modernization Advisor artifact)
- telemetry and anonymous AI analytics projections
- CLI help and non-verbose error messaging
- registry metadata and capability profiles

Diagnostic views are presence-only (booleans, env **names**, limitation codes,
error categories). See the verification allowlist in
`verification/ai_provider_privacy_boundaries/contract.py`.

## Failure isolation

Provider failures must not:

- fall back to another provider
- duplicate invocation under the default retry policy (`maximum_attempts=1`)
- corrupt non-AI Findings / Evidence / Recommendations
- change Assessment schema identity (`1.2`)
- swallow `KeyboardInterrupt` / `SystemExit`

Assess remains fail-soft for optional AI: provider failure does not replace the
primary assessment outcome.

## Doctor and CLI

Doctor is readiness-only: no client construction, no invoke, no prompt
construction. CLI has no secret flags (`--api-key`, `--openrouter-api-key`,
`--aws-access-key`, `--send-test`).

## Isolation from other products

Provider adapters and common contracts must not import Platform, Data Lake,
telemetry, or analytics runtimes. The VS Code extension does not carry
OpenRouter extension configuration. Anonymous AI analytics keeps coarse
`provider_family` / `model_family` catalogs; OpenRouter is intentionally absent
from approved AI provider families.

## Registry

Decision **B** remains in force: `AssessAIProviderRegistry` is authoritative for
assess. Bedrock remains the default provider. The contracts `AIProviderRegistry`
stays unwired.

## Verification

Authoritative suite:

```bash
cd engine
PYTHONPATH=src:. ../.venv/bin/python -m verification.ai_provider_privacy_boundaries
```

Report: `reports/verification/sv11-12/ai-provider-privacy-boundary-verification.json`

Limitations: no live provider calls, no real credentials, no remote model or
credential validation, conservative operational retry, client-owned wall-clock
timeouts, no full external extension-host or cloud validation.

Epic 11 completion is verified in Slice 11.13
(`engine/verification/ai_provider_platform_completion/`).
