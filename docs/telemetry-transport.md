# Fail-silent telemetry transport (Slice 9.11)

**Policy:** `community-telemetry-transport-policy:1.0`  
**Event-identity policy:** `community-telemetry-transport-event-identity-policy:1.0`  
**Cloud wire mapping contract:** Engine-owned `1.0` (Community Cloud telemetry schema `1.0`)  
**Runtime event schema:** unchanged `1.0`

## Purpose

Provide an explicit, privacy-first HTTP transport that maps gated Engine events
to the independently versioned Community Cloud telemetry request contract.

Default product behavior remains **unavailable** and **network-free**.

## Authoritative send path

```text
RuntimeTelemetryEvent
  → privacy projection
  → PrivacySafeTelemetryEvent
  → pre-transport privacy gate
  → explicit cloud-request mapping
  → fail-silent HTTP transport
```

The transport never accepts raw runtime events, arbitrary dictionaries, preview
wrappers, catalog objects, legacy payloads, queue records, or consent objects.

## Default and activation

| Path | Transport |
| ---- | --------- |
| `create_default_telemetry_runtime()` | `UnavailableTelemetryTransport` |
| Normal `assess` / CLI construction | Unavailable (no HTTP) |
| Explicit factory + validated config | `HttpTelemetryTransport` (opt-in only) |

`CODESTRATA_TELEMETRY_ENDPOINT` is **not** read by the privacy-first transport.
Legacy helpers remain isolated for compatibility only.

No endpoint/token CLI flags were added in this slice.

## Configuration

Immutable `TelemetryTransportConfiguration`:

- explicit HTTPS endpoint (full URL including path; no hostname guessing)
- in-memory bearer credential (`cscc_v1_…`)
- bounded connect/read timeouts (defaults 3s / 5s)
- maximum attempts default **1** (no retry)
- optional localhost HTTP only via explicit `allow_http_localhost`
- optional injected event-ID factory / client for tests

Public serialization redacts the bearer token and omits the endpoint URL.

## Credential model

`TelemetryTransportCredential` holds the bearer token in process memory only.
It is never serialized, logged, previewed, cataloged, or included in status /
diagnostics / exception messages. No refresh, issuance, or preference reuse.

## Event identity

Community Cloud requires `event_id`. The Engine privacy-safe event has none.

- Generated once per `send()` (random UUID by default; injectable)
- Reused only for bounded synchronous retries within that `send()`
- Request-envelope only — not an Engine catalog/preview field
- Never persisted, logged, or returned to users
- No installation ID is generated or sent

## Engine → Cloud mapping

| Engine field | Cloud destination |
| ------------ | ----------------- |
| `event_type` | `event_type` |
| `client_name` | `client.name` (`codestrata_cli`) |
| `cli_version` | `client.version` |
| `os_family` | `client.platform` |
| `result` | `properties.outcome` (`success`→`succeeded`, …) |
| `operation_category` | `properties.feature` + `operation=run` |
| `duration_bucket` | only exact map `lt_1s`→`under_1s`; otherwise omitted |
| `offline_mode` / `ai_used` / heads | optional `properties.flags` |
| `arch_family`, `lifecycle`, `failure_category`, Engine schema versions | **omitted** |

Omitted:

- `installation_id`
- `occurred_at`
- `request_id`
- repository / path / consent / transport diagnostics

Preview shows the Engine privacy-safe event, **not** the HTTP body.

## HTTP behavior

- Stdlib `urllib` client (no new HTTP dependency)
- Bearer `Authorization`, `Content-Type` / `Accept` JSON, bounded `User-Agent`
- TLS verification enabled
- Redirects rejected (no credential forwarding)
- Environment proxies disabled for this client
- Stable compact JSON (`sort_keys`, UTF-8, no NaN)
- Success: HTTP **202** + `status=accepted`, or **200** + `status=already_accepted`
- Malformed acknowledgment bodies are never marked accepted
- Auth (401/403), conflict (409), validation (400/422), and privacy failures do not retry
- Rate limit (429) classified and not retried by default
- Failures are fail-silent for primary operations

## Status wording

- Default transport: Unavailable
- Operational transport configured: No
- HTTP transport implementation: Present, explicit configuration required
- Transmission: Not operational

Status never inspects credentials or endpoints.

## Boundaries

- No Platform / Data Lake imports in Engine runtime packages
- No VS Code / Cursor changes
- No Community Cloud product behavior changes
- Assessment lifecycle isolation finalized in Slice 9.12
- No durable queue, retry files, batching, or background workers

## Related

- [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md)
- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- [telemetry-preview.md](telemetry-preview.md)
- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- Epic 9 completion: [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)
