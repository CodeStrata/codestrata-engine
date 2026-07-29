# Modernization Roadmap Engine

Converts existing assessment findings and recommendations into a deterministic
phased modernization plan. It does **not** re-run assessments, invent findings,
or call AI models.

This Engine sequencing is **not** CodeStrata Platform Strategic Roadmap.

## Configuration

Disabled by default:

```toml
[report.sections.roadmap]
enabled = false
include_assumptions = true
include_limitations = true
include_evidence = true
```

When enabled, `codestrata assess` adds `assessment.roadmap` to `report.json` and
an **Implementation Sequence** section to the HTML report
(`#phased-modernization-plan`). Report schema stays additive
(compatible with schema `1.2`).

## Plan stages

| Stage | Typical categories |
| ----- | ------------------ |
| Stabilize | testing, build, documentation, governance, configuration, CI/CD, reliability |
| Secure | security |
| Modernize | architecture, dependency, maintainability, modernization, technical debt, cloud, AI readiness, unknown |
| Optimize | performance |

## Mapping rules

- **Group** recommendations by `(stage, category)`; duplicate recommendation IDs collapse.
- **Priority** is the highest priority among grouped recommendations
  (`immediate`/`critical` → critical).
- **Effort** uses explicit effort when present; otherwise action-count buckets
  (`xs`…`xl`).
- **Risk** uses explicit risk when present, otherwise priority, then escalates
  from finding severity.
- **Dependencies** are cross-stage only: Secure→Stabilize;
  Modernize→Secure+Stabilize; Optimize→prior stages.
- **Identifiers** are stable digests of stage, category, and sorted
  recommendation IDs.

## CLI

```bash
codestrata roadmap inspect --report path/to/report.json
codestrata roadmap phases --report path/to/report.json
codestrata roadmap initiatives --report path/to/report.json
codestrata roadmap generate --recommendations recommendations.json [--findings findings.json]
```

`generate` reads existing artifacts only; it does not mutate repositories.

## Related

- [report-generation.md](report-generation.md)
- [recommendation-engine.md](recommendation-engine.md)
- [community-vs-platform.md](community-vs-platform.md)
