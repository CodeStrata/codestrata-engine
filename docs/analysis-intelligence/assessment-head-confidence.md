# Assessment-Head Confidence

Assessment-Head Confidence describes how strongly the available deterministic
findings and evidence support the output of one assessment head for one
repository run.

It answers: “How confidently can CodeStrata stand behind the conclusions
produced by this assessment head within the assessed scope?”

## What it is not

- Repository health, maturity, readiness, or business risk
- Severity or recommendation priority
- Probability that the head is “correct”
- Validation-set precision / product accuracy
- Average Finding Confidence
- Recommendation Confidence (implemented separately; derives from Findings, not heads)
- Coverage itself (coverage caps confidence; it is not confidence)
- AI confidence

## Levels

| Level | Meaning |
| ----- | ------- |
| `high` | Strong material Finding Confidence with complete assessed coverage and no material limitations |
| `moderate` | Meaningful support with mixed Finding Confidence, scoped zero-finding completeness, or inventory evidence quality |
| `limited` | Partial coverage, limited findings, insufficient evidence, or deferred EvidenceRef mapping |
| `unavailable` | Head disabled/unavailable, legacy-only material dependence, or no usable support |

## Derivation components

Canonical derivation uses:

- assessment-head activation / support status
- assessment status (`assessed`, `partially_assessed`, `not_enabled`, `not_available`, …)
- material Finding Confidence for findings grouped under the head
- evidence completeness signals already present on findings
- structured coverage/status (not numeric coverage percentages)
- head limitations
- legacy finding presence
- whether the head is direct or synthesized (Modernization)

Do not derive from severity, recommendation counts, executive narrative, AI
output, or Epic 4 aggregate precision.

## Weakest-support principle

Head confidence never exceeds the weakest materially relied-upon Finding
Confidence and is further capped by coverage and support status. Levels are not
averaged.

## Zero-finding policy

Zero findings are never interpreted as “healthy” or High confidence.

| Situation | Head confidence |
| --------- | --------------- |
| Complete supported coverage + assessed + sufficient evidence + zero findings | Moderate (scoped: no findings in assessed scope) |
| Partial coverage + zero findings | Limited |
| Insufficient evidence + zero findings | Unavailable |
| Head disabled / unavailable | Unavailable |

## Relationship to Finding Confidence and coverage

| Concept | Role |
| ------- | ---- |
| Finding Confidence | Caps material support for heads that emit findings |
| Assessment Coverage | Caps head confidence; remains a separate signal ([policy](./assessment-coverage.md)) |
| Severity | Does not affect head confidence |
| Assessment-Head Confidence | Support strength for the head’s conclusions in scope |

## Per-head behavior

- **Technology Inventory** — factual inventory path from inventory status /
  evidence quality when there are no findings; not Finding Confidence reuse
- **Architecture / Technical Debt / Dependency / Security** — grouped material
  findings + coverage/status
- **Testing / Cloud / AI Readiness / Performance** — honest Limited/Unavailable
  when EvidenceRef mapping / Finding Confidence is deferred
- **Modernization Assessment** — synthesized only; cannot exceed the weakest
  contributing assessed head; no contributors → Unavailable; legacy roadmap
  fallback caps confidence; action count does not raise confidence

## Legacy / deferred packs

Phase-1 / legacy findings with Unavailable Finding Confidence cannot produce
High Assessment-Head Confidence. Deferred EvidenceRef packs do not fabricate
Finding Confidence; head confidence stays Limited or Unavailable with an
explicit limitation.

## Report and HTML

`report.json` carries an additive `assessment.assessment_head_confidence` map
keyed by assessment-head id (schema remains 1.2). HTML Assessment Results CCL
blocks display this head confidence under the heading **Confidence**. Finding /
Rule / Evidence confidence labels remain on finding detail cards only.
Engineering Intelligence Summary overall confidence is the weakest contributing
Assessment-Head Confidence among assessed heads.
