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

## Community vs Platform

| Concern | Community (`report.json` 1.2) | Platform |
| ------- | ----------------------------- | -------- |
| Stable fields | Schema 1.2 + additive optional sections | May store / project additional organizational views |
| Consumers | CLI, local MCP, CI, Community extensions | Platform APIs and org experiences |
| This doc | Authoritative for Community | Does not define Platform-only fields |

Public journeys: [https://docs.codestrata.ai/reports/](https://docs.codestrata.ai/reports/).
