# Anonymous installation identity (Epic 10 Slice 10.2)

**Policy:** `community-anonymous-installation-identity-policy:1.0`  
**Schema:** `community-anonymous-installation-identity-schema:1.0`  
**Status:** Local-only — available to Slice 10.3 runtime analytics; **no transmission**

## Purpose

Provide a locally generated anonymous installation identifier for future
Community Edition analytics continuity. This is **not** customer identity,
authentication, licensing, or telemetry consent.

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
(Not yet transmitted)
```

## Principles

| Principle | Behavior |
| --------- | -------- |
| Anonymous | Random UUID v4 only |
| Stable | Generated once; reused thereafter |
| Local | Persisted under CodeStrata home |
| Independent | No coupling to consent, auth, licensing, OS user, hostname, repo |
| Non-deterministic derivation | Never hashed from machine properties |
| Recovery | Fresh identity only when `recover_on_corruption=true` |
| No transmission | Identity is not sent in Slice 10.2 |

## Persistence

- Single file: `anonymous-installation-identity.json`
- Location: `$CODESTRATA_HOME` or `~/.codestrata/`
- Atomic write (temp + replace)
- Safe concurrent read
- Independent from `telemetry.json` / consent preferences
- Independent from legacy plain-text `installation_id` file

## Record shape (schema 1.0)

```json
{
  "installation_id": "<uuid-v4>",
  "policy_version": "1.0",
  "schema_id": "community-anonymous-installation-identity-schema",
  "schema_version": "1.0"
}
```

Serialization is deterministic (sorted keys, compact separators).

## Validation

Rejects:

- malformed / corrupt JSON
- missing or extra keys
- non-UUID-v4 identifiers
- unsupported schema or policy versions

## Diagnostics

Bounded counters and versions only. Diagnostics never include:

- identifier values
- filesystem paths
- exception text
- payload echo

## Privacy

Identity records must never contain usernames, emails, hostnames, IPs,
repository/project names, paths, customer/org identifiers, source, findings,
evidence, credentials, secrets, or hardware identifiers.

## Package

Engine module surfaces under `codestrata.telemetry.analytics`:

- `CommunityAnonymousInstallationIdentityPolicy` / `default_installation_identity_policy()`
- `AnonymousInstallationIdentity`
- `ensure_anonymous_installation_identity` / `load_anonymous_installation_identity`
- `diagnose_anonymous_installation_identity`
- `InstallationIdentityError` / `InstallationIdentityErrorCode`
- serialization, validation, compatibility helpers

## Boundaries

- Does **not** collect or transmit analytics
- Does **not** modify Epic 9 telemetry consent, catalog, preview, or transport
- Does **not** modify telemetry runtime product behavior
- Does **not** change Community Cloud or Data Lake
- Does **not** modify VS Code
- Does **not** change assessment execution
- Does **not** put `installation_id` into analytics events (`installation_id_allowed=false`)
- Does **not** start Slice 10.3

## Related

- [telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md)
- [telemetry-runtime-analytics.md](telemetry-runtime-analytics.md)
- [telemetry-ai-analytics.md](telemetry-ai-analytics.md)
- [telemetry.md](telemetry.md)
- [../PRIVACY.md](../PRIVACY.md)
