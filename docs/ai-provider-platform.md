# AI Provider Platform (Epic 11 complete)

> **Status: Epic 11 complete (Slices 11.1–11.13).** OpenAI, Bedrock, and
> OpenRouter run on the Slice 11.2–11.5 contracts. This page records shared
> platform guarantees, intentional differences, and registry Decision B.
> OpenRouter is assess-registered as an **explicit, non-default** provider with
> local doctor readiness
> ([ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md)).
> Privacy and failure-isolation boundaries are verified in
> [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md).
> Completion gate:
> [`ai_provider_platform_completion`](../verification/ai_provider_platform_completion/README.md).
> Doctor never proves provider connectivity. Epic 12 is not started.

## What this is

CodeStrata v0.2.0 Epic 11, Slice 11.8 produces an authoritative offline
verification that both migrated providers satisfy the common provider-platform
contracts without forcing identical wire or authentication behavior.

Enforced by
[`engine/verification/ai_provider_cross_provider/`](../verification/ai_provider_cross_provider/README.md)
(`ai-provider-cross-provider-verification` @ `1.0.0`).

## Registry / factory decision

**Decision B — Compatibility registry retained.**

| Registry | Role |
| --- | --- |
| `AssessAIProviderRegistry` | Authoritative for `codestrata assess`, doctor entry points, and `AIModelProvider` wrappers |
| Contracts `AIProviderRegistry` | Explicit, empty-by-default platform registry; not wired to assess |

Rationale: Assess factories take `CodestrataSettings` and return
`AIModelProvider` wrappers; the contracts registry uses zero-arg `AIProvider`
factories. Consolidation without behavior change needs a settings-aware bridge
and is deferred. Slice 11.9 implements the OpenRouter adapter; Slice 11.10
registers it for explicit assess selection and operational configuration.

Compatibility wrappers (`OpenAIAIModelProvider`, `BedrockAIModelProvider`,
`OpenRouterAIModelProvider`) remain. They are not deleted in this slice.

## Shared guarantees

* Provider IDs in contracts / assess: `bedrock` (default), `openai` (explicit),
  and `openrouter` (explicit; never default).
* Requests/results: `AIProviderRequest` / `AIProviderResult` with typed
  Modernization Advisor payloads.
* Execution: `AIProviderExecutor` with `DEFAULT_RETRY_POLICY.maximum_attempts=1`.
* Configuration: Slice 11.3 models; credentials never enter redacted views.
* Capabilities: static profiles; discovery is network-free and client-free.
* Usage: `ProviderUsageMetadata` without cost/pricing.
* Errors: closed `ErrorCategory` set; raw exception text excluded from
  contracts.
* Fail-soft: owned by assessment orchestration; Assessment schema remains `1.2`.
* No silent cross-provider fallback; no duplicate invocation.
* Common contracts remain SDK-free; SDKs stay adapter-local.

## Intentional differences

| Topic | OpenAI | Bedrock | OpenRouter |
| --- | --- | --- | --- |
| Default | No (explicit) | Yes | No (explicit) |
| Model default | `gpt-4o-mini` | `amazon.nova-lite-v1:0` | **None — model required** |
| Credentials | API-key environment variable | AWS default chain / optional profile+region | API-key environment variable (`OPENROUTER_API_KEY` by default) |
| Wire protocol | Chat Completions | Converse | OpenAI-compatible Chat Completions (adapter-owned) |
| Structured JSON | `response_format` JSON mode | Prompt instruction only (`supports_structured_json=false`) | `response_format` JSON mode (model support may vary) |
| Timeout ownership | OpenAI client | botocore client config | OpenAI-compatible client |

Do not treat these as defects. Cross-provider verification records intentional
differences; OpenRouter operational details are verified by SV.11.10.

## Boundaries

* OpenRouter is assess-registered and configurable (Slice 11.10) with **local**
  doctor readiness (Slice 11.11). Doctor does not prove connectivity.
* No telemetry / Anonymous Analytics / Community Cloud / Data Lake / VS Code /
  Cursor / infrastructure changes in the provider-platform slices.
* Verification reports omit credentials, prompts, responses, endpoints,
  regions, profiles, request IDs, exception text, and filesystem paths.

## Related docs

* [ai-provider-contracts.md](ai-provider-contracts.md) — Slice 11.2
* [ai-provider-configuration.md](ai-provider-configuration.md) — Slice 11.3
* [ai-provider-execution.md](ai-provider-execution.md) — Slice 11.4
* [ai-provider-capabilities.md](ai-provider-capabilities.md) — Slice 11.5
* [ai-provider-openai.md](ai-provider-openai.md) — Slice 11.6
* [ai-provider-bedrock.md](ai-provider-bedrock.md) — Slice 11.7
* [ai-provider-openrouter.md](ai-provider-openrouter.md) — Slice 11.9 adapter
* [ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md) — Slice 11.10
* [ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md) — Slice 11.11
* [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — Slice 11.12
* [ai-enrichment.md](ai-enrichment.md) — enrichment / fail-soft ownership
