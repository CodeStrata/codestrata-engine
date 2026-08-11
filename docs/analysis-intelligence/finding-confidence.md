# Finding Confidence

Finding Confidence describes how strongly the available deterministic evidence
supports a specific Finding. It is derived after Rule Confidence, Match Evidence
Confidence, and Evidence Confidence are available. It is independent of Finding
severity ([Finding Severity Calibration](./finding-severity-calibration.md)).

## What it means

- Support strength for one Finding from its rule and evidence chain
- A property of the Finding’s deterministic backing, not of severity

## What it does not mean

- Severity or business impact
- Risk probability or remediation urgency
- Validation-set precision or product accuracy
- Recommendation Confidence or assessment-head confidence
- AI confidence or a customer health score

A high-severity Finding may have Limited Finding Confidence. A low-severity
Finding may have High Finding Confidence.

## Levels

| Level | Meaning |
| ----- | ------- |
| `high` | Strong rule, match, and evidence support with complete traceability |
| `moderate` | Support is meaningful but at least one material component is moderate |
| `limited` | Partial evidence, incomplete traceability, or limited match/rule support |
| `unavailable` | Legacy Finding, deferred EvidenceRef mapping, or missing required inputs |

## Weakest-support principle

Finding Confidence never exceeds the weakest materially required component:

- Rule Confidence
- Match Evidence Confidence (mapped onto the same scale)
- Primary / material Evidence Confidence
- Evidence completeness and traceability completeness

Do not average levels. Do not compensate for a weak component with multiple
strong ones. Moderate Rule Confidence always caps Finding Confidence at
Moderate, even when evidence is High.

## Match Evidence Confidence mapping

`RuleMatch.confidence` remains Match Evidence Confidence:

| Match value | Finding support |
| ----------- | --------------- |
| `certain` | high |
| `high` | high |
| `medium` | moderate |
| `low` | limited |

`metadata["confidence"]` continues to serialize Match Evidence Confidence for
compatibility. It is not Finding Confidence.

## Material evidence

Material EvidenceRefs are:

- the primary evidence
- synthesized/participating evidence IDs on the Finding
- resolved parent evidence IDs for synthesized material refs
- otherwise all EvidenceRefs attached to the Finding (RuleEvidence-backed)

Optional display-only evidence is not invented in this slice.

## Legacy and non-traceable packs

Phase-1 Findings and Findings without Shared Rule Confidence are Unavailable.
Packs with deferred EvidenceRef mapping (for example testing/cloud/AI/performance)
are Unavailable with an explicit deferred-mapping limitation. No fabricated
EvidenceRefs or speculative confidence.

## Relationship to other confidence concepts

| Concept | Role |
| ------- | ---- |
| Rule Confidence | Inherent rule reliability input |
| Match Evidence Confidence | Per-match evidence certainty input |
| Evidence Confidence | Per-EvidenceRef observation reliability input |
| Finding Confidence | Derived support strength for the Finding |
| Assessment-Head Confidence | Support strength for one head’s conclusions in assessed scope ([policy](./assessment-head-confidence.md)) |
| Recommendation Confidence | Support strength for one Recommendation from its Findings ([policy](./recommendation-confidence.md)) |

## Report and HTML

Findings serialize additive `finding_confidence`. HTML detail cards may show
explicit **Finding confidence**, **Rule confidence**, and **Evidence confidence**
labels. Leadership sections are unchanged.
