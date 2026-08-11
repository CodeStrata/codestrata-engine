# Assessment analytics (Epic 10 Slice 10.4)

**Policy:** `community-assessment-analytics-policy:1.0`  
**Schema:** `community-assessment-analytics-schema:1.0`  
**Status:** Construction API only — **not wired into assess CLI**; no transmission; no analytics persistence

## Purpose

Construct privacy-safe **assessment** analytics describing command execution
category and coarse outcome — never the repository or findings.

```text
Assessment lifecycle
        │
        ▼
Bounded assessment analytics input
        │
        ▼
Privacy validation
        │
        ▼
Assessment analytics projection
        │
        ▼
Identity-bearing local envelope
        │
        ▼
Identity-free AnalyticsEvent(category=assessment)
        │
        ▼
(Not persisted / not transmitted)
```

## Product-path decision

**Decision A — construction API only.**

`collect_assessment_analytics` / `build_assessment_analytics_event` are available
for tests and future fail-silent integration. The assess CLI and assessment
isolation path do **not** invoke them in this slice. Normal product behavior is
unchanged. Identity is created only when an explicit construction API call
ensures it.

## Collected fields

| Field | Meaning |
| ----- | ------- |
| `installation_id` | Anonymous UUID v4 — **only** identifier (local envelope) |
| `command_category` | `assess` only (`scan` excluded) |
| `duration_bucket` | Coarse bucket only (see below) |
| `outcome` | `success` / `failure` / `cancelled` (command completion, not quality) |
| `enabled_assessment_heads` | Canonical selected/configured heads, sorted |
| `offline_mode` | Boolean |
| `ai_requested` | Boolean (`--with-ai` intent) |
| `ai_used` | Boolean (AI executed, when known) |
| `failure_category` | Bounded category on failure/cancelled; omitted on success |

### Duration buckets

Aligned with telemetry `DurationBucket` names (+ analytics `unknown`):

| Bucket | Elapsed |
| ------ | ------- |
| `lt_1s` | &lt; 1s |
| `s_1_10` | 1s–&lt;10s |
| `s_10_60` | 10s–&lt;60s |
| `m_1_5` | 1m–&lt;5m |
| `gt_5m` | ≥ 5m |
| `unknown` | unavailable |

Exact milliseconds/seconds/timestamps are never collected.

### Enabled assessment heads

Canonical registry (`AssessmentHead`):

`engineering_intelligence`, `technology_inventory`, `architecture_intelligence`,
`technical_debt_intelligence`, `dependency_intelligence`, `security_intelligence`,
`cloud_readiness`, `ai_readiness`, `modernization_assessment`

**Meaning:** selected/configured heads — not “successfully executed”.

## Not collected

Repository/project/org/customer identity, paths, argv, source, Findings,
Evidence, Recommendations, counts, exception text, AI provider/model/tokens/cost,
exact duration, language mix, rule names.

## Package

`codestrata.telemetry.analytics`

- `CommunityAssessmentAnalyticsPolicy` / `default_assessment_analytics_policy()`
- `AssessmentAnalyticsEvent` / `collect_assessment_analytics`
- `project_assessment_analytics_event` / `to_analytics_event()`
- validation, serialization, compatibility, diagnostics helpers

Base `AnalyticsEvent(category=assessment)` remains **identity-free**.

## Boundaries

- No analytics transmission or persistence
- No Community Cloud / Data Lake changes
- No VS Code / Cursor changes
- No assess CLI wiring
- No report schema / Finding / exit-code changes
- Slice 10.5 repository aggregates available as construction APIs
  ([telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md))
- Slice 10.6 AI analytics available as construction APIs
  ([telemetry-ai-analytics.md](telemetry-ai-analytics.md))

## Related

- [telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md)
- [telemetry-runtime-analytics.md](telemetry-runtime-analytics.md)
- [telemetry-installation-identity.md](telemetry-installation-identity.md)
- [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md)
- [telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md)
- [telemetry-ai-analytics.md](telemetry-ai-analytics.md)
- [../PRIVACY.md](../PRIVACY.md)
