# AI Readiness signals fixture (validation only)

Purpose-built CodeStrata validation fixture for **AI Readiness** signal accuracy
(Epic 4 Slice 4.9). Already mapped as `local-ai-readiness` in the
ACTIVE_VALIDATION_SET.

## Intentional positives

| Path | Family | Kind | Notes |
|------|--------|------|-------|
| `requirements.txt` | *(tech/dependency)* | openai declare | Not an AI evidence path by itself |
| `src/openai_agent.py` | `ai_integration` | `llm_sdk` | Path + `import openai` |
| `mcp.json` | `tool_mcp` | `mcp_server` | `mcpServers` stub |
| `openapi.yaml` | `api_boundary` | `openapi` | Structured API spec stub |
| `README.md` | `documentation` | `readme` | Fixture documentation |

Expected SharedRules include: `ai_readiness.ai-002`, `ai-030`, `ai-040`,
`ai-051` (AI assets without observability), `ai-060` (≥3 families).  
`ai-003` must **not** fire once OpenAPI is present.

## Negative controls (must not invent)

| Path | Must not become |
|------|-----------------|
| `docs/mentions-ai-only.md` | LLM/prompt/RAG/agent integration |
| `notes/fake-agent-package-name.txt` | workflow_agent / ai_integration |
| `src/helpers/utility_helpers.py` | tool_mcp / MCP tool definition |
| `notes/assistant-shaped-prose.md` | prompt asset (`ai-031`) |
| `notes/ordinary-build-pipeline.md` | workflow_agent (`ai-041`) |

## Safety

- No API keys or credentials
- No live model / MCP / network calls
- Static assessment only; do not execute agents or install SDKs for validation
- Owned by CodeStrata for internal assessment-accuracy validation

This is **not** a customer example application.
