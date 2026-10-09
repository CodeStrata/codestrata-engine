# Scoped evidence/graph JSON export (E13.2)

**Policy:** `engine-collection-export-policy:1.0`  
**Schemas:** `codestrata.evidence-export.v1` / `codestrata.graph-export.v1` (`1.0.0`)

Existing Community telemetry (legacy aggregate `1.0.0` and privacy-safe runtime
events) is unchanged. Those payloads still do not carry findings, snippets, or
repository names.

Evidence and graph export is a **separate** local JSON envelope with:

| Field | Meaning |
| --- | --- |
| `schema` / `schema_version` | Permitted export schema identity |
| `digest` | SHA-256 of the permitted content slice |
| `notice` | `local_preview_server_not_ready` |
| `category` | `evidence` or `graph` |

The envelope binds an optional local `artifact_digest`. It does not embed
finding rows, source snippets, graph nodes, or repository names.

## Local preview

`codestrata telemetry export-preview --channel evidence|graph` prints the
envelope. `transmission_performed` is always false and `server_readiness` is
`not_ready`. Preview does not require consent and does not call a collector.

Headless full/restricted/no-export modes and signed projections are documented
in `telemetry-export-projection.md` (E13.3).

## Fake collector (capability contract)

A local `FakeCollector` may advertise those schemas and issue receipts. Upload
through `EngineCollectionAdapter` stays **unavailable** unless:

1. Durable opt-in exists (E13.1)
2. The collector kind is `fake` (never a speculative live v2 probe)
3. The collector advertises the exact schema for the channel
4. Receipts/capability checks pass

An unadvertised live collector never performs HTTP and never claims readiness.
Partial advertisement, unsupported schema, missing receipts, and oversized
payloads fail closed.

## Not this story

- Community API, S3, or infrastructure edits
- Claiming a production collector is ready
- Public Sigstore / official release signing (E14.1)
- Actual server deletion/admission
