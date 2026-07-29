# MCP security

## Read-only model

Community MCP tools must not:

- write files or edit repositories
- run git / shell / package installs
- execute arbitrary SQL
- read arbitrary filesystem paths
- mutate databases beyond existing indexing workflows
- expose public network endpoints by default
- implement remote multi-user authentication

## Secrets

Responses redact credentials, blob refs, and absolute paths (except bounded
relative evidence paths). Errors are sanitized. Stack traces stay in local
debug logs only.

## Scope

Repository-intelligence tools require `tenant_id` + `repository_id`. Cross-tenant
or cross-repository results are rejected by retrieval scope checks.

## HTTP defaults

`host = 127.0.0.1` — localhost only. Do not bind `0.0.0.0` without an external
access-control plan (out of scope for Community Edition).

## Artifact paths

`allow_artifact_paths = false` by default.

## Related

- [setup.md](setup.md)
- [troubleshooting.md](troubleshooting.md)
- [../security/threat-model.md](../security/threat-model.md)
- [../mcp-server.md](../mcp-server.md)
