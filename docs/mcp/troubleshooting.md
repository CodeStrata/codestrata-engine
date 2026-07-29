# MCP troubleshooting

| Symptom | Likely cause | Action |
| ------- | ------------ | ------ |
| `MCP is disabled` | `[mcp].enabled = false` | Set `enabled = true` |
| `Unknown MCP transport` | typo | Use `stdio`, `http`, or `sse` |
| `repository_search` → `disabled` | retrieval off | Enable `[knowledge.retrieval]` |
| `repository_answer` → `disabled` | answering/retrieval off | Enable answering + retrieval |
| `provider_unavailable` | composition failed | Check MCP health diagnostics |
| pgvector FAILED | URL/extension | Verify `CODESTRATA_DATABASE_URL`; no silent memory fallback |
| Empty findings | no completed assessment | Run assessment / seed knowledge store |
| Memory mode empty after restart | expected | Use pgvector for persistence |
| Secret-looking paths stripped | redaction | Use relative repo paths in evidence |
| `No module named 'mcp'` / missing extra | optional dep | `pip install 'codestrata[mcp]'` |

## Health check

```bash
codestrata mcp health --config codestrata.toml
```

Confirm `vector_store_provider`, `retrieval_available`, `answering_available`,
and that no database URL appears in the JSON.

## Related

- [setup.md](setup.md)
- [security.md](security.md)
- [../mcp-server.md](../mcp-server.md)
