# Anonymous analytics contract (Epic 10 Slice 10.1)

**Policy:** `community-anonymous-analytics-policy:1.0`  
**Schema:** `community-anonymous-analytics-schema:1.0`  
**Status:** Contract only — **no collection, persistence, or transmission**

## Purpose

Define **what** anonymous analytics are for CodeStrata Community Edition.
Anonymous analytics are a separate product capability built on top of the
Epic 9 privacy-first telemetry runtime. This slice does **not** collect data.

```text
Telemetry Runtime
        │
        ▼
Privacy Projection
        │
        ▼
Anonymous Analytics Projection
        │
        ▼
Analytics Contract
        │
        ▼
(Not yet persisted or transmitted)
```

## Principles

| Principle | Behavior |
| --------- | -------- |
| Independent policy/schema | Versioned separately from telemetry runtime |
| Contract only (10.1) | No collection, persistence, or transmission |
| Privacy first | Requires prior privacy projection |
| No installation ID in events | `installation_id_allowed=false` (local identity is Slice 10.2; unused in events) |
| Fail-silent | Future activation must remain fail-silent |
| Validation mandatory | Before any future persistence or transmission |

## Categories (vocabulary only)

- `runtime`
- `assessment`
- `repository_aggregates`
- `ai_usage`
- `vscode_usage`

No emitters or collectors are implemented in Slice 10.1.

## Forbidden fields (non-exhaustive)

Repository/workspace/document paths, source, Findings/Evidence/Recommendations,
prompts/responses, credentials, provider/model IDs, exact token/cost,
installation identity, endpoints, argv/command line.

## Package

Engine module: `codestrata.telemetry.analytics`

Key surfaces:

- `CommunityAnonymousAnalyticsPolicy` / `default_analytics_policy()`
- `AnalyticsEvent` / `AnalyticsCategory`
- `project_analytics_event` / `project_analytics_from_mapping`
- `validate_analytics_event` / `validate_analytics_mapping`
- `AnalyticsDiagnostics` / `empty_analytics_diagnostics()`
- `AnalyticsError` / `AnalyticsErrorCode`
- schema compatibility helpers

## Boundaries

- Does **not** modify Epic 9 telemetry consent, catalog, preview, or transport
- Does **not** change Community Cloud or Data Lake product behavior
- Does **not** import Platform / AWS SDKs
- Does **not** put installation IDs into analytics events
- Does **not** change assessment findings, reports, or exit codes
- Local anonymous installation identity is defined in Slice 10.2
  ([telemetry-installation-identity.md](telemetry-installation-identity.md))
- Local runtime analytics construction is defined in Slice 10.3
  ([telemetry-runtime-analytics.md](telemetry-runtime-analytics.md));
  transmission remains disabled
- Assessment analytics construction APIs are defined in Slice 10.4
  ([telemetry-assessment-analytics.md](telemetry-assessment-analytics.md));
  not wired into assess
- Repository aggregate analytics construction APIs are defined in Slice 10.5
  ([telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md));
  not wired into assess
- AI analytics construction APIs are defined in Slice 10.6
  ([telemetry-ai-analytics.md](telemetry-ai-analytics.md));
  not wired into assess or AI execution

## Related

- [telemetry.md](telemetry.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry-installation-identity.md](telemetry-installation-identity.md)
- [telemetry-runtime-analytics.md](telemetry-runtime-analytics.md)
- [telemetry-assessment-analytics.md](telemetry-assessment-analytics.md)
- [telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md)
- [telemetry-ai-analytics.md](telemetry-ai-analytics.md)
- Epic 9 completion: [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- Epic 10 completion: [`../../verification/anonymous_analytics_completion/README.md`](../../verification/anonymous_analytics_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)

## VS Code analytics (Slice 10.7)

VS Code owns an independently versioned analytics schema (`community-vscode-anonymous-analytics-schema:1.0`). See [`../../vscode-plugin/docs/analytics.md`](../../vscode-plugin/docs/analytics.md). Schemas are not identical; VS Code events are identity-free in Slice 10.7.

## Privacy verification (Slice 10.8)

Epic 10 privacy verification lives in [`../../verification/anonymous_analytics_privacy/`](../../verification/anonymous_analytics_privacy/). It does not enable production analytics collection or transmission.

## Completion verification (Slice 10.9)

Epic 10 completion verification lives in [`../../verification/anonymous_analytics_completion/`](../../verification/anonymous_analytics_completion/). Analytics remain contracts-only and not operational in production.
