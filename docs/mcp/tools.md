# MCP Tools

<!-- documentation-visibility: public-contract -->

Community Engine tools register with the local MCP server when
`[mcp].enabled=true`. Discover the live catalog with `codestrata mcp tools`.

**CodeStrata Platform** may register additional organizational tools when the
Platform package is installed. Those tools and wire contracts are Platform
documentation — they are not part of the Community catalog below.

## Community Engine tools (local)

| Tool (examples) | Inputs | Outputs | AI |
| --------------- | ------ | ------- | -- |
| `list_repositories` / `get_repository` | id / limit | repository summaries | No |
| `list_assessments` / `get_assessment` / `get_latest_assessment` | repository / run_id | assessment metadata | No |
| `list_findings` / `get_finding` / `explain_finding` | run_id / filters | findings | No |
| `list_recommendations` / … | run_id / filters | recommendations | No |
| `inspect_assessment_report` / `get_assessment_report_entity` / `inspect_assessment_report_traceability` | `report_path` (+ entity id) | canonical `report.json` collections / exact-ID lookup / chain status | No |
| `run_assessment` | repository, `with_ai` | run ids + counts | Optional (`with_ai`) |
| `get_ai_execution` / `get_ai_enrichment` | run_id | optional AI artifacts | Artifact may be absent |
| rules / evidence / architecture / incremental / agents | vary | bounded JSON | Agents may use client model |

### Assessment report traceability (Epic 2)

`report.json` is the canonical interchange artifact (schema **1.2**). The
`inspect_assessment_report*` tools read that document without regenerating
relationships or inventing IDs. They preserve `assessment.evidence`,
`assessment.priority_actions`, roadmap Priority Action references, and Finding /
Recommendation supporting lists when present.

Knowledge-store finding/recommendation views also carry additive EvidenceRef /
supporting-finding fields when stored on domain models. They remain projections
of assessment results — not a second universe.

`assessment.roadmap` is repository-scoped and Priority Action backed. It is
**not** the Platform Strategic Roadmap. AI / RAG / Knowledge Graph grounding is
owned by later Platform epics, not these tools.

Optional AI uses **Engine AI provider credentials** in `codestrata.toml` /
environment — never `CODESTRATA_PLATFORM_API_KEY`.

## Result bounding

When `max_result_characters` is exceeded, complete lower-priority collections are
omitted (never mid-JSON truncation), status becomes `partial`, and diagnostics
record exclusions.

## Related

- [overview.md](overview.md) — principles and boundary
- [setup.md](setup.md) — enable and serve
- [client-examples.md](client-examples.md)
