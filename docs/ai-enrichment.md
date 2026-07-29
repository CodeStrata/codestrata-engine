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

## Related

- [report-generation.md](report-generation.md)
- [runtime.md](runtime.md)
- [cli-reference.md](cli-reference.md)
