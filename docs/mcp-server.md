# CodeStrata MCP server

Local FastMCP server for Community Edition assessment knowledge.

Guides:

- [mcp/overview.md](mcp/overview.md)
- [mcp/setup.md](mcp/setup.md)
- [mcp/tools.md](mcp/tools.md)
- [mcp/client-examples.md](mcp/client-examples.md)
- [mcp/security.md](mcp/security.md)
- [mcp/troubleshooting.md](mcp/troubleshooting.md)

**CodeStrata Engine (Community)** MCP tools query local assessment knowledge.
**CodeStrata Platform** may add organizational tools when installed separately.
Platform API keys are unrelated to MCP and to Engine AI credentials.

## Community vs Platform

RAG projection, embeddings, vector storage, retrieval, and grounded answering
are **Platform** capabilities. They are not required for Community Edition
`codestrata assess`, local knowledge-store queries, or Community MCP assessment
tools.

## Architecture

```text
MCP client (Cursor, etc.)
        ↓
codestrata mcp serve  (stdio | streamable-http)
        ↓
CodeStrata FastMCP tools / resources / prompts
        ↓
KnowledgeQueryService (+ optional retrieval / answering)
        ↓
KnowledgeStore (+ optional VectorStore)
```

MCP never executes SQL, opens blob files, or reads `report.json` / `report.html`
outside application ports.

## Start

```bash
# Enable [mcp].enabled = true in codestrata.toml first
# Requires: pip install 'codestrata[mcp]'
codestrata mcp serve --config codestrata.toml
codestrata mcp tools --config codestrata.toml
codestrata mcp health --config codestrata.toml
```

Transport defaults to **stdio**. HTTP (`--transport http`) binds to `127.0.0.1`
by default.

## Repository intelligence tools

Registered names use underscores (`repository_search`, `repository_answer`, …).
Dotted aliases (`repository.search`, …) are documented in
[mcp/overview.md](mcp/overview.md).

`repository_answer` uses **deterministic extractive** answering — not generative AI.

| Tool | Purpose |
| ---- | ------- |
| `repository_search` | Grounded retrieval |
| `repository_answer` | Grounded extractive answering |
| `get_ai_execution` / `get_ai_enrichment` | Optional AI artifacts |
| `run_assessment` | Execute assessment + persist knowledge |

## Resources

- `codestrata://repositories`
- `codestrata://repositories/{repository_id}`
- `codestrata://repositories/{repository_id}/latest-assessment`
- `codestrata://assessments/{run_id}/findings`
- `codestrata://assessments/{run_id}/recommendations`

## Prompts

- `review_repository`
- `explain_modernization_plan`
- `review_snapshot_changes`

Prompts supply deterministic JSON context; the client model interprets. They do
not call an AI provider inside the MCP server.

## Limits

Collection tools return `{items, returned_count, truncated, limit}`.

Defaults/maxima match KnowledgeQueryService bounds (repositories 50/500,
assessments 20/200, findings 100/500, components 100/1000, dependency depth ≤ 3).

Full graphs, manifests, and HTML reports are not returned by general tools.

## Security / trust model

This server is a **local developer tool**.

- No authentication
- Not safe for untrusted public network exposure
- No arbitrary filesystem/SQL/shell tools
- Local path aliases omitted from public repository DTOs
- Credential-bearing URLs rejected by existing validators
- Errors sanitized (no stack traces, secrets, or sqlite details)

## Assessment execution

`run_assessment` runs the Engine assessment application service, persists
knowledge through the existing store, and returns concise IDs + counts for
follow-up query tools.

## Agent workflow tools

Five additive high-level tools call the Agent Framework (same application
services as granular tools):

| Tool | Workflow |
| ---- | -------- |
| `review_repository_with_agents` | Repository review |
| `assess_repository_with_agents` | Assess + validate |
| `validate_assessment_with_agents` | Validation |
| `compare_snapshots_with_agents` | Snapshot comparison |
| `review_modernization_with_agents` | Modernization review |

Granular tools remain for precise queries. Agent tools return bounded workflow
packages (status, IDs, summaries, steps, validation). Full evidence and HTML are
not returned. Blocking validation is a structured result.

CLI sibling: `codestrata agent …` (see [agent-framework.md](agent-framework.md)).

## Incremental tools

| Tool | Purpose |
| ---- | ------- |
| `create_incremental_assessment_plan` | Plan only |
| `execute_incremental_assessment` | Opt-in execute + validate + provenance |
| `get_incremental_execution` | Load execution record |
| `explain_incremental_execution` | Bounded deterministic explanations |

Requires `[incremental].rollout_mode` of `plan_only` or `opt_in`. Default remains
`off`. CLI sibling: `codestrata incremental …` (see
[incremental-assessment.md](incremental-assessment.md)).

## Related

- [community-vs-platform.md](community-vs-platform.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [https://docs.codestrata.ai](https://docs.codestrata.ai)
