# Pre-transport privacy gate (Slice 9.10)

**Policy:** `community-telemetry-pre-transport-privacy-policy:1.0`  
**Runtime event schema:** remains `1.0`  
**Role:** Final privacy boundary immediately before `TelemetryTransport.send()`

## Authoritative send flow

```text
RuntimeTelemetryEvent
  → privacy projection
  → PrivacySafeTelemetryEvent
  → pre-transport privacy gate
  → TelemetryTransport.send()   # default: unavailable
  → (optional explicit HTTP) map → Community Cloud request
```

Transport never receives raw runtime events, arbitrary dictionaries, preview
wrappers, catalog entries, legacy payloads, or unvalidated objects. HTTP mapping
is independently versioned — see [telemetry-transport.md](telemetry-transport.md).

## What the gate does

1. Exact type check (`PrivacySafeTelemetryEvent` only; subclasses rejected)
2. Stable-dict reconstruction through strict projection
3. Schema / runtime-policy version enforcement (`1.0` / `1.0`)
4. Public catalog reconciliation (event, fields, enums, requiredness)
5. Field-count and serialized-size limits from runtime policy
6. Forbidden-name and unsafe-value defense in depth
7. Canonical comparison (no silent field stripping)

Rejected values are never echoed. Consent cannot expand fields or bypass the
gate. Allowed sessions still must pass the gate before any transport handoff.

## Product behavior

- Gate failures / rejections are **fail-silent** for primary CLI operations
- Default / denied / non-interactive sessions still skip transport (no gate
  attempt for send)
- Unavailable transport remains the product default
- Capture transport (tests only) receives only accepted gated events
- Preview validates illustrative events through the same gate without invoking
  transport
- Status reports: `Pre-transport privacy gate: Required / Available`

## What this slice does **not** do

- Queues, installation IDs, consent persistence
- New CLI commands or options
- Catalog field expansion
- VS Code / Cursor changes

HTTP transport is implemented in Slice 9.11 and remains unavailable by default.

## Related

- [telemetry-transport.md](telemetry-transport.md)
- [telemetry-preview.md](telemetry-preview.md)
- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- Epic 9 completion: [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)
