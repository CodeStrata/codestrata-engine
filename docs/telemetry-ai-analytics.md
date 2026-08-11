# AI analytics (Epic 10 Slice 10.6)

**Policy:** `community-ai-analytics-policy:1.0`  
**Schema:** `community-ai-analytics-schema:1.0`  
**Status:** Construction API only — **not wired into assess or AI execution**; no
transmission; no analytics persistence

## Purpose

Construct privacy-safe, bounded **AI usage** analytics:

- capability (closed catalog)
- provider family (not raw provider configuration)
- model family (not exact model IDs)
- provider ownership category
- coarse outcome / optional failure category
- optional coarse duration bucket
- optional `ai_used` boolean

```text
Bounded AI aggregate input
        │
        ▼
Privacy validation
        │
        ▼
AI analytics projection
        │
        ▼
Identity-bearing local envelope
        │
        ▼
Identity-free AnalyticsEvent(category=ai_usage)
        │
        ▼
(Not persisted / not transmitted)
```

## Product-path decision

**Construction API and typed aggregate input only.**

Normal assess / AI execution does **not** invoke AI analytics and does **not**
auto-create installation identity. Reasons:

- AI provider architecture will be redesigned in a later epic
- OpenRouter is operational but absent from approved AI analytics provider families
- Slice 10.8 owns full privacy verification
- no analytics transmission or persistence exists yet
- product paths should not auto-create installation identity

## Independent policy / schema

Distinct from:

- telemetry AI usage endpoint policy
- Community Cloud AI usage schema
- runtime / assessment / repository-aggregate analytics policies
- future AI Provider Platform contracts
- future OpenRouter provider contract

## Capability catalog 1.0

| Value | Notes |
| ----- | ----- |
| `modernization_advisor` | Canonical Engine assess AI capability |

Aliases accepted only at input mapping (`ai_enrichment`, `assess_with_ai`) and
always stored as `modernization_advisor`.

## Provider-family catalog 1.0

| Value | Maps from (Engine registry) |
| ----- | --------------------------- |
| `openai` | `openai` |
| `aws_bedrock` | `bedrock`, `aws_bedrock` |
| `unavailable` | unavailable / no provider |

Unknown providers are **rejected**. Hostnames, endpoints, and account-shaped
strings are rejected as raw provider identifiers. **OpenRouter is not a family.**

## Model-family catalog 1.0

| Value | Explicit mapping |
| ----- | ---------------- |
| `gpt_family` | `gpt-*` public OpenAI naming shapes used by Engine defaults |
| `amazon_nova_family` | `amazon.nova-*` Bedrock shapes used by Engine defaults |
| `unavailable` | unavailable |

Unrecognized exact IDs (Claude ARNs, fine-tunes, deployment aliases) are
**rejected**. Errors never echo the rejected identifier.

## Provider ownership

| Value | Meaning |
| ----- | ------- |
| `customer_managed` | Customer-supplied credentials / account (Engine default) |
| `codestrata_managed` | Reserved catalog value; Engine assess path does not emit yet |
| `unavailable` | Ownership not applicable |

Does not collect account, subscription, tenant, or credential ownership details.

## Outcome semantics

| Outcome | Meaning |
| ------- | ------- |
| `success` | AI execution completed successfully |
| `failure` | AI execution attempted and failed |
| `unavailable` | Provider/model unavailable at execution time |
| `skipped` | AI not requested / intentionally not executed (not a provider failure) |

**AI disabled or not requested is `skipped`, not `failure`.**  
Provider readiness checks are not AI execution. Low-confidence content is not
failure unless product execution status says so.

### Failure category

Required for `failure` / `unavailable`. Forbidden for `success` / `skipped`.

Bounded values only (no exception text, HTTP bodies, or high-cardinality codes):
`authentication_failed`, `timeout`, `rate_limited`, `provider_unavailable`,
`invalid_configuration`, `request_rejected`, `response_invalid`,
`internal_failure`, `unavailable`.

## Duration / token decision

- **Duration:** optional coarse bucket reused from Epic 10 analytics vocabulary
  (`lt_1s`, `s_1_10`, `s_10_60`, `m_1_5`, `gt_5m`, `unknown`). Exact latency is
  prohibited. Callers may omit duration entirely.
- **Token usage bucket:** **excluded in Slice 10.6** (backlog asks for provider/
  model families; exact tokens/cost remain forbidden). Documented policy
  limitation `token_usage_bucket_excluded_in_slice_10_6`.

## Tool / RAG / graph decision

**Omitted in Slice 10.6.** Assess Advisor is a single chat capability without
reliable bounded tool/RAG/graph attribution today. Policy forbids emitting these
fields (`tool_rag_graph_omitted_in_slice_10_6`).

## Aggregate input

`AIAnalyticsInput` accepts only already-bounded catalog categories. Projection
never accepts provider clients, prompts, responses, credentials, HTTP bodies, or
exact model IDs. Optional mapping helpers (`map_provider_to_family`,
`map_model_id_to_family`) exist for tests / future safe adapters — they are not
wired into product execution.

## Identity

Local envelope may include `installation_id`. Base `AnalyticsEvent` remains
identity-free. Diagnostics omit identity values. Identity is never combined with
raw provider/model strings (those are rejected before projection).

## Privacy guarantees

Rejected (typed allowlists + structural checks):

- prompts / responses / source / context / retrieved documents
- credentials / API keys / authorization
- endpoints / regions / accounts / ARNs / deployment names
- raw `provider` / `model_id`
- exact tokens / latency / cost
- Finding / Evidence / Recommendation
- exception / traceback / HTTP body text

## Determinism

Equivalent bounded inputs produce identical stable dicts, JSON, base events, and
diagnostics categories. No timestamps. Environment credentials / cwd do not
affect payloads.

## Boundaries

| Boundary | Slice 10.6 posture |
| -------- | ------------------ |
| Assess / AI execution | Unwired |
| Provider clients / network | Not invoked |
| Persistence / transmission | Disabled |
| OpenRouter | Not supported |
| AI Provider Platform redesign | Deferred |
| Community Cloud / Data Lake | Unchanged |
| VS Code analytics | Deferred to Slice 10.7 |
| Cursor | Unchanged |
| Report schema | Remains Assessment 1.2 |

## Related docs

- [Anonymous analytics](telemetry-anonymous-analytics.md)
- [Installation identity](telemetry-installation-identity.md)
- [Runtime analytics](telemetry-runtime-analytics.md)
- [Assessment analytics](telemetry-assessment-analytics.md)
- [Repository aggregate analytics](telemetry-repository-aggregate-analytics.md)
- [Telemetry overview](telemetry.md)
