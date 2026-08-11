# ai-negative (controlled fixture)

Negative control for AI Readiness false positives (Epic 4 Slice 4.13).

## Must NOT invent AI integration

| Path | Content | Must not become |
|------|---------|-----------------|
| `README.md` | Prose mentioning "AI assistant" | ai_integration / LLM SDK |
| `package.json` | Dependency name `agent-utils` | workflow_agent / MCP |

## Explicit absences

- No `openai` import or SDK usage
- No `mcp.json`
- No prompt/RAG/agent workflow artifacts

## Safety

- Static prose and package metadata only
- CodeStrata-owned validation fixture
