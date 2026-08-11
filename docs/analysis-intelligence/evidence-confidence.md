# Evidence Confidence

Evidence Confidence describes how reliable and complete a specific evidence
observation is. It is attached to each `EvidenceRef` and serialized under
`assessment.evidence[].evidence_confidence`.

## What it means

- Reliability of one evidence observation and its extraction process
- Completeness of the observation given available provenance

## What it does not mean

- Rule Confidence (inherent reliability of a Shared Rule)
- Match Evidence Confidence (`MatchEvidenceConfidence` on `RuleMatch.confidence`)
- Finding Confidence ([finding-confidence.md](finding-confidence.md); derived in Slice 5.3)
- Severity, validation precision, AI confidence, or customer risk

## Levels

| Level | Typical use |
| ----- | ----------- |
| `high` | Exact parse, explicit declaration/configuration, exact signature, supported AST metric, direct artifact with strong provenance |
| `moderate` | Bounded static pattern, inferred classification, contextual exact evidence, redacted high-value previews |
| `limited` | Partial parse, fallback extraction, approximate location, missing parents for synthesis |
| `unavailable` | Legacy evidence or insufficient provenance |

High requires an approved strong basis. `partial_parse`, `fallback_extraction`,
`approximate_location`, and `legacy_evidence` cannot be High.

## Derivation inputs

Derivation uses structured evidence properties only:

- production mode and evidence kind
- provider identity / version when present
- parse or inspection status
- extraction method / provenance
- location precision
- measurement / graph presence
- redaction level
- parent evidence IDs and parent confidence
- envelope limitations

It does not use finding severity, recommendation priority, titles, rule
confidence, AI output, or Epic 4 pack precision.

## Direct versus synthesized

- Direct evidence is scored by family policy (dependency, sensitive, complexity,
  architecture, language, repository signals).
- Synthesized evidence cannot exceed the weakest resolved parent and cannot
  become High solely through synthesis. Missing parents lower confidence.

## Completeness versus confidence

`EvidenceCompleteness` describes how completely supporting evidence is
represented on a Finding. `EvidenceConfidence` describes the reliability of one
observation. A complete envelope may still be Limited; a direct observation may
still be Limited after a partial parse.

## Legacy behavior

Legacy production mode and old payloads without `evidence_confidence` map to
`unavailable` with an explicit limitation. No fabricated High confidence.

## Report and HTML

Canonical evidence index entries include the nested confidence block. Findings
may carry additive `primary_evidence_confidence` and
`evidence_confidence_summary` metadata for later Finding Confidence work. HTML
may show **Evidence confidence** in the Technical Appendix evidence panel only.
