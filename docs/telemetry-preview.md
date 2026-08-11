# Privacy-first telemetry preview (Slice 9.9)

**Policy:** `community-telemetry-preview-policy:1.0`  
**Preview schema:** `privacy-first-telemetry-preview` `1.0.0`  
**Command:** `codestrata telemetry preview`

## Purpose

Show exactly the privacy-safe event object that the privacy-first runtime would
give to a future transport for a selected **illustrative** event.

```bash
codestrata telemetry preview
codestrata telemetry preview --event feature_invoked
```

Default event: `feature_invoked`.

Supported `--event` values (runtime enum only):

- `application_started`
- `application_completed`
- `feature_invoked`
- `feature_completed`
- `operation_failed`

Invalid selectors exit **2** with no preview output and no side effects.

## Projection chain

```text
illustrative RuntimeTelemetryEvent
  → privacy projection
  → PrivacySafeTelemetryEvent.to_stable_dict()
  → preview wrapper JSON (stdout)
```

The nested `event` is produced by actual projection — not a hand-built dict.

## Output

Stdout is deterministic JSON only (sorted keys, 2-space indent, trailing
newline). Success exits **0**. No stderr on success. No timestamps, paths,
installation IDs, endpoints, credentials, or raw pre-filter input.

Wrapper highlights:

| Field | Meaning |
| ----- | ------- |
| `preview_type` | Always `illustrative` |
| `transmission_performed` | Always `false` |
| `transport_status` | Always `unavailable` |
| `consent_required_for_transmission` | Future transmission would require consent |
| `consent_persisted` | Always `false` |
| `installation_identity_used` | Always `false` |
| `omitted_optional_fields` | Optional catalog fields not present in `event` |
| `catalog_id` / `catalog_schema_version` | Public catalog reference |

Values are fixed categorical placeholders (for example `os_family=linux`).
They are **not** taken from the current machine, repository, or CLI run.

Preview validates illustrative events through the same pre-transport privacy
gate used before a future transport handoff. Preview still performs **no**
transport call and requires no consent.

## What preview does **not** do

- transmit or invoke transport / HTTP
- create or flush queues
- read or write preferences
- read or generate installation identity
- prompt or consume assess consent / prompt-guard state
- authorize a later command
- inspect repositories, source, findings, or reports
- accept arbitrary JSON / `--payload` / `--send`
- accept `--telemetry-allow` / `--telemetry-deny` (assess-only)

## Relationship to legacy `show`

| Command | Role |
| ------- | ---- |
| `codestrata telemetry preview` | Privacy-first illustrative transport-safe event |
| `codestrata telemetry show` | Legacy compatibility sample payload |

Preview does not read the legacy queue. Show does not use the new preview.

## Catalog

Preview reconciles with the public event catalog:

- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-event-catalog.json](telemetry-event-catalog.json)

Never-collected categories live in the catalog; preview references the catalog
rather than repeating the full list.

## Status

`codestrata telemetry status` reports the preview command as available. Status
does not execute preview or embed a sample event.

## Boundaries

Engine-owned and public. Preview never invokes HTTP transport and never shows
the Community Cloud request body, event ID, Authorization, or endpoint.
Cloud mapping is independently versioned — see
[telemetry-transport.md](telemetry-transport.md).

## Related

- [telemetry-transport.md](telemetry-transport.md)
- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry.md](telemetry.md)
- Cross-client verification (Slice 9.14): [`../../verification/privacy_first_telemetry/README.md`](../../verification/privacy_first_telemetry/README.md)
- Epic 9 completion (Slice 9.15): [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)
