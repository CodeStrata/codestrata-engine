# Report generation

Customer-facing CodeStrata Engineering Assessment (HTML) and companion JSON for
the Community Edition.

```text
Assessment inputs
        │  (+ findings / recommendations / optional Advisor)
        ▼
Customer report document
        ▼
HTML renderer
        ▼
report.html (self-contained, branded)
```

## Artifacts

| File | Role |
| ---- | ---- |
| `report.html` | CodeStrata Engineering Assessment (customer deliverable) |
| `report.json` | Machine-readable assessment contract (schema 1.2) |
| `findings.json` | Deterministic findings (unchanged by HTML) |
| `recommendations.json` | Deterministic recommendations |
| `advisor.json` | Optional Modernization Advisor narrative |
| `advisor-execution.json` | Internal Advisor provider/model/status/errors |

## Sections (HTML v3 — Design System aligned)

Brand and layout follow the CodeStrata Design System (tokens mirrored in the
public docs portal).

1. Cover (brand, edition, repository, KPIs)
2. Contents (TOC)
3. Executive Summary
4. Repository Overview
5. Assessment Summary (verdict, takeaways, risks)
6. Domain Intelligence (optional capability packs)
7. Findings (cross-domain insights)
8. Recommendations (Priority Actions + opportunities)
9. Engineering Assessment Conclusion
10. Implementation Sequence (Engine assess roadmap section — not Platform Strategic Roadmap)
11. Optional AI Enhancements (when AI enrichment present)
12. Technical Appendix (evidence, graphs, artifacts, rule IDs)

## Current Engineering Assessment vs future executive report

Today’s production deliverable is the **Engineering Assessment** above
(hero KPIs, findings, recommendations, optional domain sections). A richer
CTO-oriented executive report (broader dimension scoring, investment narrative,
and methodology appendix) remains future presentation work on the same
deterministic findings and recommendations — it is not a second analysis
pipeline.

Optional domain assessment sections (for example architecture) may appear in
`report.json` / HTML when their report gates are enabled. They consume
in-memory assessment sections and do not implement a full executive redesign.

## Executive dashboard cards

Factual, evidence-backed values only (no composite “health” or “readiness” scores):

| Card | Source | Display |
| ---- | ------ | ------- |
| Files | Repository file count | integer |
| Technologies | Detected technologies | integer |
| Findings | Findings count | integer |
| Recommendations | Recommendation count | integer |
| Test Files Detected | `StructureFacts.test_file_count` / `has_tests` | count, Detected, Not detected, or Unknown |
| CI/CD | `CicdFacts.has_ci` / `pipeline_count` | Detected, Not detected, or Unknown |
| Cloud Enablement Signals | Seven cloud flags | `N of 7` + Established / Partial / Not detected, or Unknown |
| Repository Size | File count | `N files` |
| Highest Finding Severity | Max finding severity | Critical…Informational, None Detected, or Unknown |

Cloud signals counted: Docker, Kubernetes, Helm, Terraform, CloudFormation, Serverless, Docker Compose.

## Boundaries

* Renderer performs HTML/CSS only — no analysis re-run
* Must not invent or rewrite findings/recommendations
* Absolute host paths are not leaked into customer HTML
* JSON artifact contracts are unchanged by presentation redesign
* `CustomerReportDocument` is renderer-neutral (HTML today; PDF/Markdown later)

## Related

- [report-interpretation.md](report-interpretation.md)
- [report-contract.md](report-contract.md)
- [recommendation-engine.md](recommendation-engine.md)
- [ai-enrichment.md](ai-enrichment.md)
- [community-vs-platform.md](community-vs-platform.md) — Platform Strategic
  Roadmap is separate from the Engine Implementation Sequence
