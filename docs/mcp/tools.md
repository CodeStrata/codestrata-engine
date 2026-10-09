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

### Bounded local artifact evidence queries (E12.1)

CodeStrata provides a pure, zero-database local evidence MCP server (`create_artifact_mcp_server` / `build_artifact_mcp_server`) serving deterministic inspection directly from file artifacts (such as `report.json`, `assessment.json`, `metrics.json`, `manifest.json`, and run directory trees).

| Category | Tools | Inputs | Purpose |
| -------- | ----- | ------ | ------- |
| **Repository** | `list_repositories`, `get_repository` | `local_root`, `limit`, `offset`, `repository_id` | Repository identity, source location, and creation timestamps |
| **Snapshot** | `list_snapshots`, `get_snapshot` | `local_root`, `repository_id`, `snapshot_id`, pagination | Commit / snapshot provenance, branches, file counts |
| **Component** | `list_components`, `get_component` | `local_root`, `run_id`, `component_type`, `component_id` | Architecture modules, libraries, services, dependency counts |
| **Finding** | `list_findings`, `get_finding` | `local_root`, `run_id`, `severity`, `category`, `finding_id` | Detected issues, rules, messages, location, evidence references |
| **Metric** | `list_metrics`, `get_metric` | `local_root`, `run_id`, `category`, `metric_id` | Quality, complexity, security, and debt measurements |
| **Dependency** | `list_dependencies`, `get_dependencies` | `local_root`, `run_id`, `source_component_id`, `target_component_id` | Intra-component relationships, dependency weights |
| **Change** | `list_changes`, `get_change_summary` | `local_root`, `run_id`, `change_type`, pagination | Blast radius, boundaries crossed, diff statistics |
| **Evidence** | `list_evidence`, `get_evidence` | `local_root`, `run_id`, `evidence_kind`, `evidence_id` | AST, source, and rule execution snippets and lines |
| **Lineage** | `list_lineage`, `get_lineage` | `local_root`, `repository_id`, `run_id` | Assessment run provenance, git commit, ruleset versions |

#### Governance and Safety
- **Zero Database Connection:** Pure file reader; zero connection to SQLite, Postgres, or external databases.
- **Read-Only / No Consent Required:** Queries read only existing local output artifacts; no collection consent is required.
- **Root Scoping & Traversal Rejection:** Queries require an explicit `local_root`. Path traversal (`..`), system directory access, and root escaping are rejected with security errors.
- **Schema Validation:** Artifacts must match recognized CodeStrata schema versions (e.g. `1.0`, `1.2`, `codestrata-artifact-manifest:1.0.0`).
- **Bounded Pagination:** Bounded with minimum limit 1 and maximum query budget of 500 records per call. Character budgeting enforces truncation indicators without emitting invalid JSON.
- **Forbidden Operations:** Assessment execution (`run_assessment`), rule activation (`evaluate_rule`), shell execution, hosted telemetry, portfolio cross-repo queries, GraphRAG/answering tools, and the optional explanation tool are strictly prohibited on this server.

### Optional local/BYO explanation (E12.2)

`create_local_explanation_mcp_server` registers one tool, `explain_local_evidence`. It is not registered on the artifact evidence server or by the default assessment MCP registrar.

The tool reuses the existing OpenAI adapter. The optional OpenAI SDK is imported only inside that adapter, and only after a call sets both `enabled=true` and `prompt_evidence_egress_enabled=true`. Product telemetry does not authorize that egress.

| Input | Behavior |
| ----- | -------- |
| `enabled=false` (default) | Returns `ai_disabled`. No provider call. |
| `prompt_evidence_egress_enabled=false` | Returns `egress_not_enabled` even when product telemetry is on. |
| Both flags true | Sends permitted evidence IDs only. The artifact cites those IDs plus provider `openai` and the requested model. |
| Provider or network failure | Returns an explanation error. Assessment status and canonical digest are echoed unchanged. |
| Source text containing tool directives | The text is not forwarded and no tool is executed. |

`local_root` reads evidence IDs through the E12.1 artifact reader. IDs outside that set are rejected. More than 32 evidence IDs is an explanation budget error. The explanation artifact is not part of canonical computation.

### AI-on/off and local MCP equivalence (E12.3)

The same pinned assessment is run through four modes: AI disabled, provider success, provider timeout, and source-instruction injection. Findings, metric values, severity, coverage, and verdicts stay semantically identical. Only the separate explanation export changes.

| Mode | Canonical body | Explanation export |
| ---- | -------------- | ------------------ |
| Disabled | Unchanged. No provider call. | `ai_disabled`. Limitations and missing-citation fields are present. |
| Provider success | Unchanged. | Artifact cites permitted evidence IDs only. Unpermitted citations, limitations, and rejected score claims are listed. |
| Timeout | Unchanged. | Explanation error. No artifact. |
| Injection | Unchanged. No tool execution. | Missing citations and source-instruction limitations are visible. Score, severity, coverage, and verdict claims are rejected. |

The artifact evidence server returns that canonical evidence without constructing an AI provider. `explain_local_evidence` stays on the separate explanation server. An `ai_explanation` object, an `explanation.json` sidecar, or a model field named `health_score` does not become a metric, a severity, a coverage ratio, or a verdict. A missing coverage ratio stays null.

## Result bounding

When `max_result_characters` is exceeded, complete lower-priority collections are
omitted (never mid-JSON truncation), status becomes `partial`, and diagnostics
record exclusions.

## Related

- [overview.md](overview.md) — principles and boundary
- [setup.md](setup.md) — enable and serve
- [client-examples.md](client-examples.md)

