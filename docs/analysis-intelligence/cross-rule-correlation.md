# Cross-Rule Correlation

Cross-rule correlation links distinct Findings that describe related aspects of
the same repository condition. Findings remain independently valid; they are
not merged, deleted, or renumbered.

## Correlation versus duplication

| Concept | Slice | Behavior |
| ------- | ----- | -------- |
| Duplicate | 5.11 | Same rule + same condition → consolidate into one Finding |
| Correlated | 5.12 | Different rules + shared deterministic identity → relationship record |
| Theme | presentation | Synthesis/label only — never automatic correlation |

## Deterministic identity requirements

Automatic correlations require shared identity such as:

- material EvidenceRef ID with compatible subjects
- same path + configuration key
- same dependency identity and comparison scope
- same measurement symbol/scope
- same graph node/edge/cycle
- explicit reviewed rule or cross-head policy

Title similarity, category match, severity match, and LLM judgment never create
correlations.

## Correlation Confidence

Levels: `high` · `moderate` · `limited` · `unavailable`

High requires exact shared evidence/config/dependency/graph identity or an
explicit reviewed policy. Correlation Confidence is not Finding Confidence and
is not derived from severity.

## Rule relationship catalog

Policies live in
`application/findings/correlation_policies.py`. Each policy names rule IDs,
required bases, direction, minimum confidence, and limitations. The initial
catalog is intentionally small and high-value.

## Same-head and cross-head

Same-head correlations dominate the initial catalog. Cross-head correlations
require an explicit reviewed policy with `cross_head_allowed=true` and a shared
identity. Broad category-pair correlation is prohibited.

## Clusters

Connected components may form `FindingCorrelationCluster` records for
navigation. Transitive membership does not invent a direct correlation between
every pair.

## Recommendations

Correlations feed Recommendations only through explicit correlation-aware
providers. Not every correlation produces a Recommendation. Recommendation
Confidence still uses weakest supporting Finding Confidence. Severity and
Priority Action ranking are unchanged.

## Report presentation

`report.json` may include additive `assessment.finding_correlations`. Findings
may list `correlation_ids` / `correlated_finding_ids`. HTML Finding detail cards
may show Related findings with customer-safe relationship labels. Leadership
sections are unchanged.

## Validation

Optional expectation blocks may declare required/forbidden rule-pair
correlations under `finding_correlations` in repository expectations. Pair keys
are stable (`rule_a|rule_b`) and do not depend on Finding IDs. Validation
record/summary schemas remain 1.0.

Internal diagnostics:

```bash
python -m validation.finding_correlations
```

## Knowledge Graph

Community resolves correlations from local report artifacts. No commercial
Knowledge Graph requirement.

## Prohibited

- title-only or summary similarity
- AI/RAG inference
- merging Findings
- severity or priority calibration from correlation count
- fabricating transitive edges

Severity calibration is defined separately in
[Finding Severity Calibration](./finding-severity-calibration.md).
