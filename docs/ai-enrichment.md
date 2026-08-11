# AI Providers / enrichment

> **Canonical public overview:** [AI Providers](https://docs.codestrata.ai/ai-providers/)

Optional AI is a Community Engine capability. Public setup lives in the docs
portal; Engine provider wiring follows.

Optional one-call leadership narrative over deterministic findings and
recommendations. Customer-facing name: **Modernization Advisor**. Internal
modules may still use `AiEnrichment*` identifiers.

```text
findings.json + recommendations.json + compact repo summary
        ↓
Modernization Advisor (exactly one provider call: Bedrock or OpenAI)
        ↓
advisor.json  (+ report HTML/JSON from AiEnrichmentResult)
```

## Boundary

| Allowed | Forbidden |
| ------- | --------- |
| Interpretive narrative | Creating or deleting findings |
| Referencing known finding/recommendation IDs | Mutating `findings.json` / `recommendations.json` |
| Compact budgeted context | Full graph dumps, source files, secrets |

## Providers

Configure `[ai].provider` as `bedrock` (default) or `openai`.

Discover and validate without assessing:

```bash
codestrata ai
codestrata ai doctor
```

* Bedrock: Converse API; model via `--model-id`, `CODESTRATA_BEDROCK_MODEL_ID`,
  or `ai.bedrock.model_id`
* OpenAI: Chat Completions with `response_format=json_object`; model via
  `--model-id`, `CODESTRATA_OPENAI_MODEL_ID`, or `ai.openai.answer_model`

Portal setup: [AI Providers](https://docs.codestrata.ai/ai-providers/).

## Advisor metadata

Successful enrichment stamps:

* Provider and model
* Advisor version / prompt version
* Generated timestamp (UTC)

HTML and JSON reports both render from the same `AiEnrichmentResult` domain
model (`assessment.ai_enrichment` in report.json).

## Call budget

* Deterministic mode: **0** provider calls
* `--with-ai`: **exactly 1** provider call
* No silent retries that create additional calls

## Failure behavior

Advisor failures become staged warnings. Deterministic graphs, findings,
recommendations, and reports remain valid. No fabricated enrichment is written.
CLI exit code remains 0 for enrichment-only failure.

## Artifact

`advisor.json` (written only on successful enrichment).

## Compatibility baseline

Epic 11, Slice 11.1 characterizes and freezes the *existing* provider
architecture described above (Bedrock/OpenAI, defaults, error mapping,
fail-soft, `codestrata ai doctor`) as a compatibility baseline for future
work — it does not change any behavior on this page. See
[`engine/verification/ai_provider_baseline/README.md`](../verification/ai_provider_baseline/README.md).

Epic 11, Slice 11.2 adds a new, **unwired** set of provider-neutral domain
contracts (`codestrata.ai.provider_contracts`) as a possible future
foundation. Nothing on this page changes: Bedrock/OpenAI, defaults, prompts,
and the Modernization Advisor call path above are untouched, and no provider
implements the new contracts yet. See
[`ai-provider-contracts.md`](ai-provider-contracts.md).

Epic 11, Slice 11.3 adds a standardized, privacy-preserving representation
of provider/model configuration to the same unwired package. It is a pure
data-modeling layer only: the actual provider selection, model resolution
precedence, settings fields, and CLI flags described above are all restated
as ground truth, not changed. See
[`ai-provider-configuration.md`](ai-provider-configuration.md).

Epic 11, Slice 11.4 adds a standardized, unwired execution shape (bounded
timeout/retry/backoff policies, a pure retry-decision function, safe error
classification, and an `AIProviderExecutor`) to the same package. Nothing on
this page changes: the actual provider call in
`AiEnrichmentService.run()` (a single, non-retried `AIModelProvider.generate()`
call) is untouched, and the executor is wired into nothing. See
[`ai-provider-execution.md`](ai-provider-execution.md).

Epic 11, Slice 11.5 adds a static, unwired capability profile per known
provider (structured JSON, streaming, timeout/retry policy support,
usage/token reporting) plus an optional `completion_status` field on usage
metadata, to the same package. Nothing on this page changes: provider
selection, token extraction, and fail-soft behavior are all restated as
ground truth, not changed. See
[`ai-provider-capabilities.md`](ai-provider-capabilities.md).

Epic 11, Slice 11.6 **wires** those contracts for OpenAI. Slice 11.7 wires
Bedrock the same way. Both providers run under `AIProviderExecutor` behind
compatibility wrappers; enrichment fail-soft ownership on this page is
unchanged. See [`ai-provider-openai.md`](ai-provider-openai.md),
[`ai-provider-bedrock.md`](ai-provider-bedrock.md), and
[`ai-provider-platform.md`](ai-provider-platform.md) (Slice 11.8 cross-provider
verification; Decision B — compatibility registry retained). Slice 11.10 adds
explicit OpenRouter configuration
([`ai-provider-openrouter-configuration.md`](ai-provider-openrouter-configuration.md));
doctor local readiness is Slice 11.11
([`ai-provider-openrouter-doctor.md`](ai-provider-openrouter-doctor.md)).

## Related

- [report-generation.md](report-generation.md)
- [runtime.md](runtime.md)
- [cli-reference.md](cli-reference.md)
- [ai-provider-openai.md](ai-provider-openai.md) — OpenAI after Slice 11.6
- [ai-provider-bedrock.md](ai-provider-bedrock.md) — Bedrock after Slice 11.7
- [ai-provider-platform.md](ai-provider-platform.md) — cross-provider posture (11.8)
- [ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md) — OpenRouter config/auth (11.10)
- [ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md) — OpenRouter doctor / mocked integration (11.11)
- [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) — privacy / failure isolation (11.12)
