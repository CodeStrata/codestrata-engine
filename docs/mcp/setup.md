# MCP setup

## Configuration

```toml
[mcp]
enabled = false
transport = "stdio"          # or "http" / "streamable-http" / "sse"
host = "127.0.0.1"
port = 8765
server_name = "codestrata"
max_result_characters = 50000
include_diagnostics = true
include_traceability = true
allow_artifact_paths = false
log_level = "INFO"

[mcp.tools]
repository_search = true
repository_answer = true
# … see codestrata.toml for the full tool list
```

MCP defaults **disabled**. HTTP binds to localhost only by default.

Dependent gates:

- `repository.search` also needs `[knowledge.retrieval].enabled = true`
- `repository.answer` needs retrieval **and** `[knowledge.answering].enabled = true`

## Start

```bash
codestrata mcp serve --config codestrata.toml
codestrata mcp serve --config codestrata.toml --transport http --host 127.0.0.1 --port 8765
codestrata mcp tools --config codestrata.toml
codestrata mcp health --config codestrata.toml
```

Install the optional extra first: `pip install 'codestrata[mcp]'`.

## Memory vs pgvector

| Mode | Notes |
| ---- | ----- |
| memory | Process-lifetime only; MCP server and indexer must share the same process |
| pgvector | Recommended for persistent MCP usage; Docker Compose + `CODESTRATA_DATABASE_URL` |

Never silently falls back from pgvector to memory.

## Transports

- **stdio** — default for Cursor / Claude Desktop
- **streamable-http** (`--transport http`) — localhost developer use
- **sse** — supported by the MCP SDK when needed

Community Edition does not provide remote authentication or public multi-user
hosting. Keep HTTP bound to `127.0.0.1`.

## Community vs Platform

Local MCP assessment tools are Community Engine features. Organizational RAG /
portfolio tools appear only when CodeStrata Platform is installed separately.
See [../mcp-server.md](../mcp-server.md) and
[../community-vs-platform.md](../community-vs-platform.md).

## Related

- [security.md](security.md)
- [troubleshooting.md](troubleshooting.md)
- [../cli-reference.md](../cli-reference.md)
