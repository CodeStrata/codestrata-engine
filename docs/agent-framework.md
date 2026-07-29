# CodeStrata Agent Framework

Transport-neutral workflows that coordinate existing Engine application
services. Agents are orchestrators — not MCP clients, chat bots, or alternate
business-logic implementations.

Public product name: **CodeStrata**. Package and CLI remain `codestrata`.

## Purpose

Provide bounded, deterministic workflows that:

- review persisted repository knowledge
- run a new assessment through `AssessmentApplicationService`
- validate persisted assessment completeness
- compare repository snapshots
- assemble grounded repository and modernization review packages

Agents **orchestrate**; they do not reimplement scanning, graph construction,
rules, recommendations, persistence, AI providers, or report generation.

## Deterministic-first design

Core workflow behavior works fully without AI:

- agent selection and step order are fixed plans
- validation, evidence retrieval, and snapshot comparison are deterministic
- AI is never required to decide whether an assessment completed

The framework does **not** implement LLM-based tool selection, ReAct loops,
autonomous retries, or reflection.

## Architecture

```text
CLI / MCP / other adapters
        │
        ├───────────────┐
        │               │
        ▼               ▼
Agent Framework    Application Services
        │               ▲
        └───────────────┘
```

- MCP and agents are **sibling** interfaces over the same application services.
- Agents call `KnowledgeQueryService` and `AssessmentApplicationService` directly.
- Agents must **not** call the FastMCP server, open SQLite, read blobs, or read
  `report.json` / `report.html`.

Package: `codestrata.application.agents`

| Module | Role |
| ------ | ---- |
| `orchestrator.py` | Explicit workflow coordination |
| `knowledge_agent.py` | Persisted knowledge assembly |
| `assessment_agent.py` | Assessment execution |
| `validation_agent.py` | Completeness / grounding checks |
| `planner.py` | Deterministic planner (+ extension protocol) |
| `policies.py` | Conservative execution bounds |
| `evidence.py` | Grounded evidence records |
| `factory.py` | Injectable composition |

## Workflows

| Workflow | Entry |
| -------- | ----- |
| Repository review | `AgentOrchestrator.review_repository` |
| Repository assessment | `AgentOrchestrator.assess_repository` |
| Snapshot comparison | `AgentOrchestrator.compare_repository_snapshots` |
| Assessment validation | `AgentOrchestrator.validate_assessment` |
| Modernization review | `AgentOrchestrator.modernization_review` |

Each workflow has a typed request/result, explicit steps, bounded execution,
captured evidence, and a validation outcome when applicable.

### Assessment workflow (recommended order)

1. Resolve prior repository context (when registered)
2. Capture previous assessment IDs
3. Call `AssessmentApplicationService`
4. Retrieve the new persisted run
5. Validate the persisted run
6. Return the grounded result

### Review workflow

1. Resolve repository + latest completed assessment
2. Retrieve findings, recommendations, components, optional AI artifacts
3. Validate evidence completeness
4. Assemble `RepositoryReviewResult`

## Evidence model

Conclusions are grounded with `AgentEvidence`:

- stable `source_id` / `evidence_id`
- `source_kind` (repository, run, finding, recommendation, …)
- concise summary
- `deterministic` flag
- related IDs

AI content may **reference** evidence; it cannot replace evidence. Full source
code, blob paths, credentials, and knowledge-store paths are never stored in
evidence.

## Validation model

`ValidationAgent` checks runs, artifacts, findings, recommendations, graph
references, and optional AI artifacts through query DTOs only.

Issues use severities: `info`, `warning`, `error`, `blocking`.

When `stop_on_blocking_validation` is true (default), the orchestrator marks the
workflow `blocked` instead of successful completion.

## Policies

```toml
[agents]
enabled = true
max_steps = 10
max_findings = 100
max_recommendations = 100
max_components = 100
dependency_depth = 2
stop_on_blocking_validation = true
```

Omitted `[agents]` keeps defaults. Dependency depth cannot exceed 3. Existing
`codestrata.toml` files remain valid without this section. AI provider settings
stay under `[ai]` / `[aws]`.

## Composition

```python
from codestrata.application.agents import create_agent_orchestrator

orchestrator = create_agent_orchestrator(
    query_service=queries,
    assessment_service=assessment_service,  # optional for review-only
    policy=None,  # or AgentExecutionPolicy(...)
)
result = orchestrator.review_repository(
    RepositoryReviewRequest(repository_identifier=repo_id)
)
```

Tests should inject fake services. Importing `codestrata.application.agents`
does not open a database or call an AI provider.

## CLI and MCP adapters

Thin transport adapters call `AgentOrchestrator` only — no duplicated workflow
logic.

### CLI: `codestrata agent`

| Command | Workflow |
| ------- | -------- |
| `codestrata agent review --repository <id>` | Repository review |
| `codestrata agent assess --repository <path-or-url>` | Assess + retrieve + validate |
| `codestrata agent validate --run-id <id>` | Assessment validation |
| `codestrata agent compare --previous-snapshot … --current-snapshot …` | Snapshot comparison |
| `codestrata agent modernization-review --repository <id>` | Modernization review |

Common options: `--config`, `--json`. Review also accepts bound overrides
(`--max-findings`, `--dependency-depth`, …) within hard framework limits.

**`codestrata assess` vs `codestrata agent assess`**

- `codestrata assess` — direct assessment entry (reports + persistence)
- `codestrata agent assess` — orchestrated assessment plus prior context,
  persisted IDs, validation, evidence summaries, and workflow steps

Exit codes: `0` completed, `1` blocked (validation), `2` configuration/execution
failure.

### MCP: high-level agent tools

Additive tools on the CodeStrata FastMCP server:

- `review_repository_with_agents`
- `assess_repository_with_agents`
- `validate_assessment_with_agents`
- `compare_snapshots_with_agents`
- `review_modernization_with_agents`

Granular tools remain for precise queries. Agent tools return bounded multi-step
workflow results. Blocking validation is returned as a structured result.

`create_mcp_server(..., agent_orchestrator=…)` accepts an injected orchestrator;
when omitted, the factory composes one from the same query/assessment services.

## Security

- No credentials, AWS profiles, SQL, blob paths, or stack traces in agent results
- Unexpected exceptions are wrapped as agent errors
- Structured logs include workflow/run/repository IDs and statuses only
- Adapters do not enable shell/SQL/blob/report access

## Current limitations

- No LLM planner (extension point only: `AgentPlanner`)
- No autonomous loops or retries
- No new recommendation / rule / graph engines
- Review narratives remain deterministic aggregations (no required AI prose)

## Related

- [incremental-assessment.md](incremental-assessment.md)
- [mcp-server.md](mcp-server.md)
- [community-vs-platform.md](community-vs-platform.md) — organizational
  capabilities beyond local agents
