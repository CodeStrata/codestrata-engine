# Duplicate Finding Consolidation

Duplicate Finding consolidation is a deterministic merge of Findings that
represent the **same underlying repository condition**. It prevents one logical
issue from appearing multiple times because of overlapping evidence, mapper
paths, Phase-1/Shared Rule projections, or repeated report projection.

## What it is not

- Cross-rule correlation (Slice 5.12)
- Suppressing valid distinct findings
- Grouping Findings that merely share a title
- Reducing finding count for presentation
- Customer waiver/suppression
- Deduplicating Recommendations
- Severity calibration

## Exact versus equivalent versus related

| Kind | Meaning |
| ---- | ------- |
| Exact duplicate | Same Finding ID (or same canonical condition with identical IDs) |
| Equivalent duplicate | Same rule and same condition, different evidence/mapper paths |
| Related finding | Different rule or materially different condition — **not** consolidated here |
| Presentation duplicate | Same canonical Finding rendered more than once |

## Canonical condition identity

`canonical_finding_condition_key(finding)` is derived from:

- `rule_id`
- canonical subject keys (evidence-id tokens stripped)
- normalized repository-relative locations
- symbolic / measurement / graph identity when present

It excludes title, summary, severity, confidence, rule version, timestamps, run
IDs, recommendation IDs, and report ordering.

Prefer the existing Finding ID when it already represents the condition.
`build_finding_id` is not replaced globally.

## Eligibility

Automatically consolidate only when:

1. Same Finding ID
2. Same `rule_id` and same canonical subject identity
3. Same `rule_id`, same path/symbol/measurement identity, compatible evidence
4. Explicit reviewed legacy→Shared Rule equivalence **and** agreeing location

Never consolidate only because titles, summaries, severities, categories, or
assessment heads match. Different rules remain separate except explicit legacy
mappings.

## Same-rule merge behavior

- Union EvidenceRefs and synthesized evidence IDs
- Union limitations and compatible locations/measurements/graph refs
- Select primary evidence deterministically
- Recompute Finding Confidence (no first-wins)
- Preserve one canonical Finding ID; record member IDs in the consolidation ledger
- Do not discard stronger evidence
- Do not change severity merely because duplicates exist

## Severity and confidence

Severity is outside confidence derivation and is not summed or calibrated.
Same-rule severity conflicts preserve the highest deterministic severity and add
a consolidation limitation. Rule Confidence and Evidence Confidence are not
changed; Finding Confidence is recomputed from merged support.

## Legacy overlap

Phase-1 versus Shared Rule Findings consolidate only through an explicit,
reviewed mapping with agreeing evidence/path identity. Shared Rule Findings are
canonical; legacy IDs become members/aliases. Uncertain overlaps remain separate
for Slice 5.12 or legacy cleanup. Title similarity is never sufficient.

## Downstream references

Consolidation runs before Recommendation creation in the assessment pipeline so
Recommendation IDs use canonical Finding IDs. Customer-universe recommendation
alignment remaps member IDs via aliases. Priority Actions and Roadmap consume
canonical IDs through Recommendation links. Recommendations themselves are not
merged in this slice.

## Customer presentation

`report.json` contains consolidated Findings only. HTML uses one detail anchor
per canonical Finding ID. Architecture supporting tables dedupe by Finding ID,
never by title alone.

## Internal diagnostics

`FindingConsolidationDiagnostics` tracks original/canonical counts and duplicate
group kinds. Optional CLI:

```bash
python -m validation.finding_duplicates
```

Read-only. No customer suppression controls.

## Relationship to Slice 5.12

Cross-rule correlation of related Findings is defined in
[Cross-Rule Correlation](./cross-rule-correlation.md). Correlated Findings
remain separate; only true duplicates consolidate here.
