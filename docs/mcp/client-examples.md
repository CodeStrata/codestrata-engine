# MCP Client Examples

<!-- documentation-visibility: public-contributor -->

Placeholders only — do not embed secrets, usernames, or absolute private paths.

## Cursor

```json
{
  "mcpServers": {
    "codestrata": {
      "command": "/path/to/.venv/bin/codestrata",
      "args": ["mcp", "serve", "--config", "/path/to/codestrata.toml"]
    }
  }
}
```

Enable `[mcp].enabled = true`. Community assessment tools work with Engine alone.

## Claude Desktop

```json
{
  "mcpServers": {
    "codestrata": {
      "command": "/path/to/.venv/bin/codestrata",
      "args": ["mcp", "serve", "--config", "/path/to/codestrata.toml"]
    }
  }
}
```

## Generic streamable HTTP (localhost)

```bash
codestrata mcp serve --config codestrata.toml --transport http --host 127.0.0.1 --port 8765
```

Point an MCP HTTP client at `http://127.0.0.1:8765/mcp` (SDK default path).
Do not expose this port publicly.

## Community Engine examples

Run a local assessment (optional AI uses Engine AI provider credentials):

```json
{
  "name": "run_assessment",
  "arguments": {
    "repository": ".",
    "with_ai": false
  }
}
```

```json
{
  "name": "list_findings",
  "arguments": {
    "run_id": "assessment-run-id",
    "severity": "high",
    "limit": 20
  }
}
```

## Related

- [tools.md](tools.md)
- [overview.md](overview.md)
- [setup.md](setup.md)
