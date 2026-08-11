# Report Contract

<!-- documentation-visibility: public-contract -->

Hardens CodeStrata **Community** report JSON/HTML for stable, leadership-ready
output without adding assessment capabilities.

**Public contract:** `report.json` is an integration surface for CLI, MCP, and
extensions. Platform may project or extend reports for organizational views;
those projections are **not** part of the Community `report.json` 1.2 contract
documented here.

## Envelope

`report.json` remains schema **1.2** with an additive top-level `manifest`:

- report / HTML / contract versions
- CodeStrata version
- product metadata (`product_name`, `edition`, `report_type`, `brand_report_name`)
- repository ID / scan ID
- enabled sections
- generation mode
- explicit `volatile_fields` list for comparisons

Versioned schema file:
`schemas/assessment/codestrata.io/v1.2/AssessmentReport.json`
(packaged under `codestrata.resources.schemas`).

### Compatibility rules

1. Additive optional fields/sections within schema 1.2 are allowed.
2. Removing/renaming required fields or changing types is a **new schema version**.
3. Consumers must ignore unknown properties.
4. Use `manifest.volatile_fields` when comparing runs.
5. Customer-facing text must satisfy the Engine customer-safe projection
   (`codestrata.security.customer_safe_text`) so Platform EI
   `validate_report_document` accepts the same artifacts (see SV.13/SV.14).
6. Cross-schema compatibility for v0.2.0 is verified by
   `platform/verification/cross_schema_compatibility/` (SV.14). Assessment 1.2,
   validation/EIR/export/API product `1.0`, and verification report `1.0.0` are
   distinct version namespaces.

## Determinism rules

- Findings, recommendations, technologies, and evidence use shared contract sort keys.
- Report-facing finding/recommendation IDs are content-derived UUID5 values
  (`codestrata.reporting.contract.identifiers`); runtime domain UUIDs are remapped at the
  reporting boundary only.
- Duplicate IDs and identical evidence rows are removed.
- Severity / priority / effort / risk / confidence strings are normalized.
- Optional sections are omitted when disabled or empty (roadmap with zero initiatives).
- Repeated-run comparisons use `strip_volatile_fields` / `reports_structurally_equal`.

Volatile paths (ignored for structural equality):

- `assessment.generated_at`
- `assessment.timing`
- `assessment.ai.latency_ms`
- `assessment.static_analysis` (provider durations)
- `manifest.generated_at`

## Validation

```bash
codestrata report validate path/to/report.json [--json]
```

Checks schema version, manifest fields, duplicate IDs, finding references,
evidence links, and roadmap traceability.

## HTML

- Executive Summary first
- Clear section hierarchy and leadership-oriented empty states
- Related finding IDs link to in-page finding anchors
- Machine-readable JSON remains separate from HTML presentation

## Traceability interchange (Epic 2)

Schema **1.2** remains the version. Additive collections on `assessment` form
the deterministic chain:

`evidence` → `findings` → `deterministic_recommendations` → `priority_actions`
→ `roadmap` → `report.json` → HTML / MCP / Platform.

MCP and Platform must preserve these collections and supporting reference lists
when transporting or ingesting `report.json`. They must not strip unknown
additive fields, silently filter unresolved IDs, remap canonical IDs, or rebuild
relationships. Legacy / incomplete reports are accepted without fabricating
traceability and may be marked `legacy` or `incomplete`.

`assessment.roadmap` is the **Assessment Roadmap** (repository-scoped). It is
distinct from any Platform **Strategic Roadmap** (portfolio / commercial).

AI grounding, RAG, and Knowledge Graph authority are out of scope for this
contract surface (later Platform epics).

## Community vs Platform

| Concern | Community (`report.json` 1.2) | Platform |
| ------- | ----------------------------- | -------- |
| Stable fields | Schema 1.2 + additive optional sections | May store / project additional organizational views |
| Consumers | CLI, local MCP, CI, Community extensions | Platform APIs and org experiences |
| Canonical SoT | `report.json` document | Prefer retain full artifact blob; projections are not a second SoT |
| This doc | Authoritative for Community | Does not define Platform-only fields |

Public journeys: [https://docs.codestrata.ai/reports/](https://docs.codestrata.ai/reports/).
