# Rule Confidence

Rule Confidence describes the inherent reliability of a Shared Rule’s
deterministic logic when its required evidence is present. It is stable rule
metadata on `RuleMetadata`, copied onto each `RuleMatch`, and projected into
finding metadata. Finding Confidence is derived separately; see
[finding-confidence.md](finding-confidence.md).

## What it means

- How strongly the rule’s predicate can support the conclusion it produces
- A property of the rule contract, not of one repository or one match

## What it does not mean

- [Finding Confidence](finding-confidence.md) (per-finding support strength; implemented in Slice 5.3)
- Evidence confidence or match evidence certainty
- Severity or business impact
- Precision measured from a validation set as a universal probability
- Probability that a repository is defective
- AI confidence or a customer risk score

Match-specific evidence certainty remains `MatchEvidenceConfidence`
(`low`, `medium`, `high`, or `certain`) on `RuleMatch.confidence`. Reports keep
that value at metadata key `confidence`. Structured inherent confidence is
additive at `rule_confidence` and must be labeled **Rule confidence**, never
plain “Confidence”.

## Levels

| Level | Use when |
| ----- | -------- |
| `high` | Exact signature, explicit configuration, direct manifest declaration, exact threshold over supported parsed evidence, or exact graph cycle over complete graph evidence |
| `moderate` | Deterministic result that still depends on classification, contextual thresholds, architecture inference, or static signals that do not prove runtime behavior |
| `limited` | Partial extraction, weak structural approximation, incomplete coverage, ambiguous context, or similar constraints |
| `unavailable` | Confidence cannot be supported honestly (for example Phase-1 legacy rules) |

Do not assign High solely because a validation set had no false positives.

## Bases

One or more unique bases, sorted deterministically:

- `exact_signature`
- `explicit_configuration`
- `deterministic_threshold`
- `structural_graph_relationship`
- `manifest_declaration`
- `static_pattern`
- `inferred_classification`
- `partial_extraction`
- `legacy_rule`

High requires at least one of the first five strong bases. `partial_extraction`
and `legacy_rule` cannot be High.

## Calibration and validation support

Calibration is `defined`, `validation_supported`, `provisional`, or
`unavailable`.

`validation_supported` requires a `RuleValidationSupport` record with:

- a validation set id
- reconciled counts and optional precision/recall
- at least one true positive
- explicit limitations (including controlled-fixture scope when applicable)

Zero denominators leave precision or recall unavailable (`null`). Validation-set
precision does not become a universal accuracy claim. Rules not exercised
positively must remain `defined` or `provisional`, not `validation_supported`.

Epic 4 controlled fixtures may exercise architecture, complexity, and dependency
rules. Until rule-level true-positive counts are attached, those assignments stay
`defined` with fixture-scope limitations.

## Severity vs Rule Confidence vs Finding Confidence

| Concept | Meaning |
| ------- | ------- |
| Severity | Importance of the reported condition |
| Rule Confidence | Inherent reliability of the rule’s logic |
| Match evidence certainty | Certainty of evidence for one match (`MatchEvidenceConfidence`) |
| Finding Confidence | Derived Finding support strength ([finding-confidence.md](finding-confidence.md)) |
| Assessment-Head Confidence | Support strength for one head ([assessment-head-confidence.md](assessment-head-confidence.md)) |
| Recommendation Confidence | Support strength for one Recommendation ([recommendation-confidence.md](recommendation-confidence.md)) |

## Legacy rules

Phase-1 legacy adapters use level `unavailable`, basis `legacy_rule`, and
calibration `unavailable`. Legacy rule IDs are unchanged. Match evidence
certainty may still be `certain` without asserting inherent Rule Confidence.

## Report projection

Findings may carry additive `rule_confidence` (nested object) plus flattened
`rule_confidence_level`, `rule_confidence_basis`,
`rule_confidence_limitations`, and `rule_confidence_calibration_status`.
Assessment schema remains 1.2 when these fields are additive.
