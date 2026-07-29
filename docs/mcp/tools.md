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
| `run_assessment` | repository, `with_ai` | run ids + counts | Optional (`with_ai`) |
| `get_ai_execution` / `get_ai_enrichment` | run_id | optional AI artifacts | Artifact may be absent |
| rules / evidence / architecture / incremental / agents | vary | bounded JSON | Agents may use client model |

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
