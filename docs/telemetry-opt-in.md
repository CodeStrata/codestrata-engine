# Durable opt-in and no-egress defaults (E13.1)

**Policy:** `engine-collection-opt-in-policy:1.0`  
**Adapter:** `codestrata.telemetry.opt_in.EngineCollectionAdapter`

Engine local adapters do not transmit telemetry, evidence, or graph payloads
unless an explicit durable opt-in exists. Missing consent is a no-egress
default, not an implied Yes. Evidence/graph *live* upload remains unavailable
until a collector advertises a supported schema (E13.2). Local scoped JSON
preview/export constructs a separate envelope and does not claim server
readiness. Signed projections and full/restricted/no-export modes are
documented in `telemetry-export-projection.md` (E13.3).

## Durable preference

Local versioned consent lives under `CODESTRATA_HOME` (`telemetry.json`).
States: `undecided` | `v1_yes` | `v2_yes` | `disabled`. Inspect with
`codestrata telemetry status` or `codestrata telemetry inspect`.

| Control | Persistence | Transmission |
| --- | --- | --- |
| Default / missing file | none | none |
| `telemetry enable` | durable v2 | telemetry only, after privacy gate |
| `telemetry disable` | durable disabled; **queued sends cancelled** | none after restart |
| `--telemetry-deny` | none (this run only) | none this run |
| `--telemetry-allow` | none | does not invent consent |
| CI / `CODESTRATA_TELEMETRY=1` | none | does not invent consent |

## Pending collection

`telemetry disable` and `EngineCollectionAdapter.disable()` delete the local
retry queue (`telemetry-queue.jsonl`) and in-memory pending items. A later
process must not flush leftovers. Re-enable starts from an empty queue.

## Failure isolation

Upload or analytics errors are fail-silent. They cannot change assessment
status, artifacts, or exit code. See `run_primary_with_isolated_collection`
and the existing assessment isolation path.

## Prohibited data

Canaries cover logs, retry queues, and telemetry serialization. Forbidden
field names and value markers drop the payload; they are never an analysis
failure.

## Not this story

- Community API / S3 / infrastructure edits
- Live v2 evidence/graph upload (requires an actual collector advertisement)
- Public Sigstore / official release signing (E14.1)
