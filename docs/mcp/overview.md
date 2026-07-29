# CodeStrata MCP Overview

<!-- documentation-visibility: public-contributor -->

**Status:** Community MCP tools for local assessment knowledge are documented here.

CodeStrata Engine exposes assessment knowledge through a standards-compliant
Model Context Protocol server. MCP is an **interface layer only**; tools
delegate to existing Engine services.

```text
MCP Client
   ↓
CodeStrata MCP Transport (stdio | streamable-http)
   ↓
MCP Tool Registry
   ↓
MCP Application Adapters
   ↓
Local assessment knowledge / assess runtime
```

## Community vs Platform

| Edition | What MCP exposes |
| ------- | ---------------- |
| **CodeStrata Engine** (Community) | Local assessment knowledge: list/get/explain, `run_assessment`, optional AI artifacts |
| **CodeStrata Platform** | Additional organizational MCP tools when Platform is installed |

Platform REST and organizational MCP details are Platform documentation.
Community docs only state that Platform capabilities exist separately.

Platform API keys are not used by Community MCP and are not AI provider credentials.

## Principles

- Model-independent defaults for Community Engine tools
- Structured, bounded, traceable JSON outputs
- Never expose credentials, database URLs, env values, or embeddings
- Read-only tools except explicit assessment operations

## Schemas

- `mcp-tool-response` 1.0.0
- `mcp-health-response` 1.0.0
- `mcp-server-manifest` 1.0.0

## Related

See [setup.md](setup.md), [tools.md](tools.md), [client-examples.md](client-examples.md),
[security.md](security.md), and [troubleshooting.md](troubleshooting.md).

Boundary: [https://docs.codestrata.ai/community/vs-platform](https://docs.codestrata.ai/community/vs-platform).
