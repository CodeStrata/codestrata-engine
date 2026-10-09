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

## Artifact paths and evidence queries

- `allow_artifact_paths = false` by default for the primary assessment server.
- The standalone bounded evidence server (`create_artifact_mcp_server`) provides read-only queries directly against local run artifacts without needing a database connection.
- Local root scoping rejects directory traversal (`..`), system directories, and unauthorized file extensions.
- Read-only artifact queries operate without collection consent, preserving offline no-consent utility for inspecting completed local runs.
- The optional explanation tool is a separate server. It stays disabled unless explanation and prompt/evidence egress are both set. Product telemetry consent does not enable that egress. Source instructions are not executed as tools. A provider or network failure is an explanation error and does not change assessment status or the canonical digest.
- Disabled, successful, timed-out, and injection explanation modes leave canonical findings, metrics, severity, coverage, and verdicts unchanged. Export of the explanation shows limitations and missing citations. Unsupported score, severity, coverage, and verdict claims are rejected and do not enter metric scores. The artifact evidence server does not require an AI provider.

## Related

- [setup.md](setup.md)
- [troubleshooting.md](troubleshooting.md)
- [../security/threat-model.md](../security/threat-model.md)
- [../mcp-server.md](../mcp-server.md)
- [tools.md](tools.md)

