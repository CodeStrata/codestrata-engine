# Runtime analytics (Epic 10 Slice 10.3)

**Policy:** `community-runtime-analytics-policy:1.0`  
**Schema:** `community-runtime-analytics-schema:1.0`  
**Status:** Local construction only — **no transmission; no analytics persistence**

## Purpose

Construct anonymous **runtime** analytics events for the Engine CLI using the
Slice 10.1 analytics contract and Slice 10.2 anonymous installation identity.

```text
Telemetry Runtime
        │
        ▼
Privacy Projection
        │
        ▼
Analytics Projection
        │
        ▼
Anonymous Installation Identity
        │
        ▼
Runtime Analytics Event
        │
        ▼
(Not transmitted)
```

## Collected fields (runtime category only)

| Field | Notes |
| ----- | ----- |
| `installation_id` | Anonymous UUID v4 — **only** identifier |
| `cli_version` | CodeStrata package version |
| `os_family` | `linux` / `macos` / `windows` / `other` |
| `architecture` | `x86_64` / `arm64` / `other` |
| `runtime_version` | Python major.minor (for example `3.12`) |
| `release_adoption` | CLI major.minor cohort (for example `0.2`) |

## Not collected

Repository/project/file names, paths, usernames, hostnames, machine/MAC
identifiers, source, findings, evidence, credentials, secrets, customer/org
IDs, command arguments, environment variables.

## Behavior

- Requires prior privacy projection (`privacy_projection_applied=true`)
- Produces `AnalyticsEvent(category=runtime)` **without** embedding
  `installation_id` in the base analytics event
- Runtime envelope may include `installation_id` (local only)
- May ensure the local anonymous installation identity file
- Does **not** persist analytics payloads
- Does **not** invoke transport
- Not wired into the CLI product path in this slice

## Package

`codestrata.telemetry.analytics`

- `collect_runtime_analytics` / `RuntimeAnalyticsEvent`
- `project_runtime_analytics_event` / `RuntimeAnalyticsProjection`
- `validate_runtime_analytics_event`
- `CommunityRuntimeAnalyticsPolicy` / `default_runtime_analytics_policy()`
- diagnostics, serialization, compatibility helpers

## Boundaries

- Does **not** transmit analytics
- Does **not** modify Community Cloud or Data Lake
- Does **not** modify telemetry consent, catalog, preview, or transport
- Does **not** change assessment execution
- Does **not** start Slice 10.4

## Related

- [telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md)
- [telemetry-installation-identity.md](telemetry-installation-identity.md)
- [telemetry-assessment-analytics.md](telemetry-assessment-analytics.md)
- [telemetry-ai-analytics.md](telemetry-ai-analytics.md)
- [telemetry.md](telemetry.md)
- [../PRIVACY.md](../PRIVACY.md)
