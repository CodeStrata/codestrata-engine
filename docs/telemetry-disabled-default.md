# Disabled-by-default telemetry enforcement (Slice 9.2)

**Policy:** `community-telemetry-runtime-policy:1.0`  
**Default decision:** `disabled_by_default`  
**Product entry:** `get_telemetry_service()` → `DisabledTelemetryFacade`

## What Slice 9.2 enforces

Normal Community CLI and assessment execution **must not**:

- prompt for telemetry consent
- reuse saved legacy opt-in consent
- generate or read an installation ID (product path)
- persist telemetry preferences
- queue telemetry events
- send HTTP telemetry
- inspect `CODESTRATA_TELEMETRY_ENDPOINT` for transmission
- change command results because telemetry is unavailable

Absence of an explicit current-session allow decision means telemetry is disabled.
Slice 9.2 provides **no** allow decision.

## Authoritative factory

```python
from codestrata.telemetry.runtime_factory import create_default_telemetry_runtime

runtime = create_default_telemetry_runtime()
# decision=disabled_by_default, transport=unavailable
```

No preference reads, environment enablement, installation identity, filesystem
access, network, or prompts.

## Product vs legacy paths

| Path | Entry | Behavior |
| ---- | ----- | -------- |
| assess / open / UX / welcome | `get_telemetry_service()` | Disabled facade; drop only |
| `codestrata telemetry *` | `get_legacy_telemetry_service()` | Explicit legacy preference commands |
| Focused unit tests | `TelemetryService(home=...)` | Direct legacy construction |

Legacy `TelemetryService` is retained and marked compatibility-only. It is **not**
constructed by default product execution and is **not** an automatic fallback from
the runtime.

## Saved preferences

An existing `~/.codestrata/telemetry.json` with `"enabled": true` does **not**
enable the product runtime. Preferences are not read on assess/report/UX paths.
Legacy files are not deleted or migrated by this slice.

## Installation identity / queue / endpoint

Product paths do not create or read installation IDs, do not touch the local
queue, and do not call `configured_endpoint` / `send_payload`.

`CODESTRATA_TELEMETRY_ENDPOINT` does not activate transmission for product
commands.

## CLI preference commands

Commands `status`, `enable`, `disable`, `reset`, and `show` remain. They manage
**legacy** preference state. `enable` / `disable` from the CLI do not emit or
flush network/queue events in Slice 9.2. Enabling a legacy preference does **not**
cause subsequent `assess` / `open` to transmit through the privacy-first runtime.

## Not yet available

- Interactive prompt UI was Slice 9.4 — see
  [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- Non-interactive / CI suppression was Slice 9.5 — see
  [telemetry-non-interactive.md](telemetry-non-interactive.md)
- CLI consent flags were Slice 9.6 — see
  [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- Status: [telemetry-status.md](telemetry-status.md) (Slice 9.7)
- Catalog: [telemetry-event-catalog.md](telemetry-event-catalog.md) (Slice 9.8)
- Preview: [telemetry-preview.md](telemetry-preview.md) (Slice 9.9)
- Community Cloud HTTP transport

Session consent remains an Engine contract. Interactive allow/deny maps to
`interactive_prompt` source and is process-local only. Non-interactive
suppression maps to `non_interactive_disabled` (not user consent). CLI flags
map to `cli_flag`.

## Related docs

- [telemetry-runtime.md](telemetry-runtime.md) — Slice 9.1 runtime foundation
- [telemetry-session-consent.md](telemetry-session-consent.md)
- [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- [telemetry-non-interactive.md](telemetry-non-interactive.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry.md](telemetry.md) — legacy preference / schema notes
- [../PRIVACY.md](../PRIVACY.md)
