# AWS Bedrock Provider Migration (Epic 11, Slice 11.7)

> **Status: wired.** This page describes code that `codestrata assess --with-ai`
> actually runs when the provider is `bedrock` (the default). OpenAI was
> migrated in Slice 11.6; both providers now sit on the Slice 11.2–11.5
> contracts. See [`ai-provider-openai.md`](ai-provider-openai.md) for the
> OpenAI adapter and [`ai-enrichment.md`](ai-enrichment.md) for the shared
> enrichment/fail-soft flow.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.7 migrates the **AWS Bedrock** provider onto
the Slice 11.2–11.5 provider contracts. A new adapter package,
`codestrata.ai.provider_adapters.bedrock`, implements the `AIProvider`
protocol and runs under `AIProviderExecutor`. The existing public class,
`BedrockAIModelProvider`, stays exactly where it was — same module, same name,
same constructor signature, same registry key (`bedrock`, still the default) —
and becomes a thin compatibility wrapper over the adapter.

Nothing observable about an assess run changes. Same default provider
(`bedrock`), same selection precedence, same `[ai.bedrock]` / `[aws]` keys,
same `amazon.nova-lite-v1:0` default, the same Converse request bytes, the
same exceptions raised into `AiEnrichmentService`'s fail-soft path, assessment
report schema `1.2`, and the same CLI exit codes.

This is **not**:

* A change to OpenAI's migrated path (Slice 11.6).
* OpenRouter is assess-registered as an explicit non-default provider (Slice 11.10) with local doctor readiness (Slice 11.11).
* An activation of `BedrockSettings.max_retries` — the executor still makes
  exactly one provider call per assess run (CR-1), and botocore remains pinned
  to `retries={"max_attempts": 1, "mode": "standard"}`.
* Making the common `AIProviderRegistry` authoritative — Slice 11.8 **Decision B**
  retains `AssessAIProviderRegistry` as assess authority; consolidation remains
  deferred with explicit rationale (see
  [`ai-provider-platform.md`](ai-provider-platform.md)).
* A change to telemetry, analytics, Community Cloud, Data Lake, VS Code,
  Cursor, or infrastructure.

## Architecture after Slice 11.7

```text
                        AssessAIProviderRegistry
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
   "bedrock" (migrated, default)            "openai" (migrated)
              │                                       │
   BedrockAIModelProvider                   OpenAIAIModelProvider
   (AIModelProvider wrapper)                (AIModelProvider wrapper)
              │                                       │
   legacy_bridge → AIProviderRequest         legacy_bridge → AIProviderRequest
              │                                       │
   AIProviderExecutor (1 attempt)            AIProviderExecutor (1 attempt)
              │                                       │
   BedrockProvider (AIProvider)              OpenAIProvider (AIProvider)
              │                                       │
   client → aws_config / boto3 Converse      client → openai Chat Completions
```

Both providers satisfy the same legacy `AIModelProvider.invoke()` interface, so
`AiEnrichmentService`, the factory, doctor, and CLI are unchanged. Common
`AIProviderRegistry` consolidation was reviewed in Slice 11.8 and deferred
(**Decision B** — compatibility registry retained). See
[`ai-provider-platform.md`](ai-provider-platform.md).

## Package layout

```text
engine/src/codestrata/ai/provider_adapters/bedrock/
├── adapter.py              BedrockProvider(AIProvider) — execute() never raises
├── capabilities.py         Re-exposes BEDROCK_CAPABILITY_PROFILE (Slice 11.5)
├── client.py               Sole AWS/SDK boundary (lazy; aws_config factory)
├── configuration.py        Settings → BedrockAdapterConfiguration + client inputs
├── diagnostics.py          Redacted views (no profile/region/credential values)
├── error_mapping.py        botocore/Bedrock failures → ErrorCategory
├── factory.py              build_bedrock_provider / build_bedrock_executor
├── legacy_bridge.py        PromptRequest ↔ contracts; legacy exception rebuild
├── request_mapping.py      AIProviderRequest → Converse kwargs
├── response_mapping.py     Converse response → AIProviderResult
└── usage_mapping.py        usage/metrics → ProviderUsageMetadata
```

## Boundaries

* **Adapter owns:** boto3/botocore client construction via `aws_config`, profile
  and region resolution, Converse mapping, response parsing, error translation,
  usage extraction, one wire attempt.
* **Executor owns:** `maximum_attempts=1`, retry decisions (none by default),
  safe final provider-neutral outcome.
* **Assessment owns:** fail-soft, AIExecutionStatus, reports, exit codes.
* **No OpenAI `response_format` on Bedrock.** Structured JSON remains
  prompt-instruction-only (`supports_structured_json=False`).
* **Privacy:** diagnostics and verification reports never include AWS keys,
  session tokens, profile/region/account/ARN values, prompts, responses,
  request IDs, or exception text.

## Verification

```bash
cd engine && PYTHONPATH=src:. ../.venv/bin/python -m verification.bedrock_provider_migration
```

Report: `engine/reports/verification/sv11-7/bedrock-provider-migration-verification.json`
Schema: `bedrock-provider-migration-verification` @ `1.0.0`

Expected verdict: `pass_with_limitations` (no live AWS calls; compatibility
wrappers remain; conservative retries; doctor compatibility path; common
registry deferred; wall-clock timeout SDK-owned; OpenRouter completed in Slices 11.9–11.11).
