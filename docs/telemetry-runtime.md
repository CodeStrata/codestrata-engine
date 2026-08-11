# Community telemetry runtime (Slice 9.1)

**Policy:** `community-telemetry-runtime-policy:1.0`  
**Event schema:** `community-telemetry-runtime-event:1.0`  
**Default:** Disabled — **no transmission**

This document describes the Engine-owned **telemetry runtime foundation**
introduced in Epic 9 Slice 9.1. It is independent from the legacy
Phase 14.3 [`TelemetryService`](telemetry.md) (prefs, installation id, local
queue, optional HTTP endpoint).

## What Slice 9.1 provides

| Capability | Behavior |
| ---------- | -------- |
| Runtime policy | Versioned product policy; disabled by default |
| Session | Process-scoped decision only; no persisted consent |
| Typed events | Narrow allowlisted runtime event intake |
| Privacy projection | `RuntimeTelemetryEvent` → `PrivacySafeTelemetryEvent` |
| Preview | Deterministic privacy-safe JSON; works while disabled |
| Transport port | Narrow `send(PrivacySafeTelemetryEvent)` |
| Default transport | Unavailable / no-op — never returns `sent` |
| Fail-silent | `record_telemetry_safely` never raises into commands |
| Assessment isolation | Telemetry failure cannot alter primary results |

## What Slice 9.1 does **not** provide

- Interactive consent prompts
- Saved / reused consent
- Installation ID generation or persistence
- Network transmission
- Community Cloud authentication or HTTP
- CLI flags (`--telemetry-allow` / `--telemetry-deny`)
- New CLI commands (`telemetry status` / `preview` runtime commands)
- VS Code / Cursor integration
- Data Lake wiring

Do **not** claim an opt-in flow exists for this runtime yet. Later slices own
consent, flags, and cloud transport.

## Modules

```
codestrata.telemetry.runtime_policy
codestrata.telemetry.session
codestrata.telemetry.decisions
codestrata.telemetry.events
codestrata.telemetry.privacy
codestrata.telemetry.projection
codestrata.telemetry.preview
codestrata.telemetry.transport          # runtime port + legacy HTTP helpers
codestrata.telemetry.diagnostics
codestrata.telemetry.errors
codestrata.telemetry.runtime
codestrata.telemetry.infrastructure.unavailable_transport
codestrata.telemetry.infrastructure.capture_transport   # test-only

Legacy ``configured_endpoint`` / ``send_payload`` remain in ``transport.py`` for
``TelemetryService`` compatibility. The Slice 9.1 runtime never calls them.```

## Default decision

A newly constructed session:

- decision = `disabled_by_default`
- decision source = `default`
- does **not** transmit, queue, persist, or prompt
- does **not** generate installation identity
- does **not** read previously saved consent or environment for implied consent

Absence of a decision is **not** consent.

## Approved event types

- `application_started`
- `application_completed`
- `feature_invoked`
- `feature_completed`
- `operation_failed`

## Approved fields

- `event_type`, `client_name` (`codestrata_cli`)
- `cli_version`, `os_family`, `arch_family`
- `lifecycle`, `result`, `duration_bucket`, `operation_category`
- `enabled_assessment_heads` (sorted categorical heads)
- `offline_mode`, `ai_used` (booleans)
- `failure_category`
- `schema_version`, `runtime_policy_version`

## Never collected

Repository / project / organization identity, paths, cwd, argv, command line,
source code, findings, evidence, recommendations, package names, exception
messages, stack traces, environment variables, credentials, prompts, responses,
exact model IDs, exact token counts, cost, personal / customer identifiers,
installation ID (in this runtime).

## Preview

`preview_runtime_event` returns exactly the privacy-safe projected event that
would later be passed to transport. Preview:

- works when telemetry is disabled
- performs **no** transmission
- generates **no** installation ID
- persists nothing
- uses stable sorted JSON
- identifies telemetry as disabled / `transmission: none`
- never exposes raw pre-filter input

## Transport

Default: `UnavailableTelemetryTransport` → result `unavailable`.

Test-only: `CaptureTelemetryTransport` retains privacy-safe events; never an
implicit production default.

## Fail-silent

Use `record_telemetry_safely(...)` or `TelemetryRuntime.record(...)`. Failures
in creation, projection, preview, transport, or diagnostics must not change CLI
exit codes, assessment results, reports, findings, or AI execution.

## Boundaries

| Layer | Owns |
| ----- | ---- |
| Engine | Local runtime, session decision, projection, preview, transport port |
| Platform | Community Cloud endpoint, auth, rate limits, Data Lake, analytics |

Engine must not import `codestrata_platform`, Community Cloud API models,
Data Lake models, boto3 for telemetry, FastAPI, or AWS/OpenTofu infrastructure.

Community Cloud mapping (`POST /api/v1/telemetry`, CLI events, assessment-
metadata, AI-usage) is **deferred**.

## Legacy `TelemetryService`

The existing opt-in service (installation id under `~/.codestrata/`, prefs,
local queue, optional `CODESTRATA_TELEMETRY_ENDPOINT`) remains for **explicit**
preference commands and focused tests. Slice 9.2 routes normal product execution
through `get_telemetry_service()` → `DisabledTelemetryFacade` so legacy consent
is not reused. See [telemetry-disabled-default.md](telemetry-disabled-default.md).

Migration of anonymous installation-ID behavior is reserved for a later
privacy-reviewed epic.

## Related docs

- Legacy CLI telemetry: [telemetry.md](telemetry.md)
- Disabled-default enforcement: [telemetry-disabled-default.md](telemetry-disabled-default.md)
- Per-session consent: [telemetry-session-consent.md](telemetry-session-consent.md)
- Interactive consent: [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- Non-interactive suppression: [telemetry-non-interactive.md](telemetry-non-interactive.md)
- CLI consent flags: [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- Status: [telemetry-status.md](telemetry-status.md)
- Public event catalog: [telemetry-event-catalog.md](telemetry-event-catalog.md) /
  [telemetry-event-catalog.json](telemetry-event-catalog.json)
- Preview: [telemetry-preview.md](telemetry-preview.md)
- Pre-transport privacy: [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- Transport: [telemetry-transport.md](telemetry-transport.md)
- Assessment isolation: [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md)
- Privacy: [../PRIVACY.md](../PRIVACY.md)
