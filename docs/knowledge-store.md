# Engineering knowledge store

Local persistence for assessment knowledge used by CLI, MCP, and agents.

Assessment opens the store by default (`.codestrata/knowledge/` via
`[knowledge].directory`).

## Why SQLite + immutable JSON blobs

SQLite indexes repositories, snapshots, runs, and artifact metadata. Graph and
finding payloads remain content-addressed JSON under `blobs/` so schema-rich
graphs stay byte-inspectable and are not forced into relational tables.

## Layout

```text
.codestrata/knowledge/
  knowledge.sqlite
  locks/
  blobs/
    manifests/
    graphs/
    findings/
    recommendations/
    ai/
  tmp/
  incremental_executions/   # optional incremental records
```

## Schema

Current schema version **2** adds:

- `repository_snapshots` — content fingerprint + manifest blob ref
- `assessment_runs` — running / completed / failed / aborted
- `knowledge_artifacts` — kind, schema version, blob ref/hash

Migration from v1 is transactional and preserves repositories/aliases.

## Repository identity vs snapshot identity

| Concept | Identity |
| ------- | -------- |
| Repository | Durable UUID + canonical key |
| Snapshot | `(repository_id, branch_key, content_fingerprint)` |
| Assessment run | New UUID each execution; may reuse a snapshot |

Content fingerprint (not timestamps) decides snapshot reuse.

## Persistence failure semantics

When knowledge persistence is enabled (default):

1. Reports may already be written under `reports/`.
2. If knowledge finalization fails, the assessment fails with a clear error.
3. The knowledge run is marked `failed`, never `completed`.
4. Incomplete runs are never returned by latest-completed queries.

## Recovery

On open, stale `running` rows older than six hours are marked `aborted`.
Temporary files under `tmp/` are cleaned. Corrupt blob hashes raise application
errors; they are not silently repaired.

## Git revision provenance

When `.git` is present, HEAD SHA is stored on the snapshot row. Dirty trees and
non-Git directories fall back safely. Snapshot content identity remains the
manifest fingerprint.

## Reports vs knowledge

Report retention (`keep=3`) does not delete knowledge store rows or blobs.
Reports remain derived outputs. Query services never read `report.json`,
`report.html`, or run-directory artifacts.

## Knowledge query services

Transport-neutral application API:

```text
CLI / FastMCP / agents
        ↓
KnowledgeQueryService
        ↓
KnowledgeStore ports
        ↓
SQLite metadata + verified immutable JSON blobs
```

Package: `codestrata.application.knowledge.queries`

- Depends only on application ports/models and domain payloads.
- Does not import `sqlite3`, Typer, or infrastructure SQLite classes.
- Does not expose blob paths, knowledge-root paths, credentials, or SQL.
- Local path aliases are omitted from public repository DTOs by default.

Composition helper:

`create_knowledge_query_service(store=...)` or
`create_knowledge_query_service(directory=...)` /
`create_knowledge_query_service(settings=...)`.

### Authoritative findings

Query APIs expose stable findings and recommendations (`finding:…`,
`recommendation:…`). Analyzer-only UUID findings are not part of this knowledge
API.

### Artifact validation

Artifacts are selected by run + kind, hash-verified, JSON-parsed, and validated
against domain codecs. Missing required deterministic artifacts raise typed
errors. Optional AI artifacts return `None` when absent. Corrupt or incompatible
payloads raise application query errors (never silent substitution).

### Historical snapshot comparison

`compare_repository_snapshots` diffs two persisted manifests. Results include
added / modified / deleted / metadata-changed paths. Rename detection is
deferred (rename = delete + add). Comparison does not read the live working tree.

### Explanations

`explain_finding` / `explain_recommendation` assemble deterministic provenance
from persisted findings, recommendations, and graphs. They do not call AI and
do not fabricate missing evidence.

### Component / dependency queries

Loaded from the immutable Repository Graph. Dependency traversal uses
`depends_on` edges, default depth 1, maximum depth 3, with cycle protection and
result bounds.

### Why MCP must use query services

MCP (and CLI/agent) adapters must call `KnowledgeQueryService` rather than
opening SQLite or blob files. That keeps validation, privacy filtering, and DTO
stability in one application boundary.

## Legacy aliases

Conflicting optional `legacy_repository_key` aliases are skipped during
`register_or_resolve` and never merge distinct GitHub repositories. Explicit
`add_alias` still raises on conflict.

## Related

- [incremental-assessment.md](incremental-assessment.md) — opt-in incremental
  assessment (full rebuild remains the default assess path)
- [mcp-server.md](mcp-server.md)
- [community-vs-platform.md](community-vs-platform.md) — Platform RAG /
  organizational knowledge beyond the local store
