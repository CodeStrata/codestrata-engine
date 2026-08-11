# Repository aggregate analytics (Epic 10 Slice 10.5)

**Policy:** `community-repository-aggregate-analytics-policy:1.0`  
**Schema:** `community-repository-aggregate-analytics-schema:1.0`  
**Status:** Construction API only — **not wired into assess**; no transmission; no analytics persistence

## Purpose

Construct de-identified repository **aggregate** analytics:

- language mix as bounded file counts by language group
- rule execution counts as bounded totals (optional per canonical head)

```text
Assessment aggregate source
        │
        ▼
Aggregate-only input
        │
        ▼
Privacy validation
        │
        ▼
Repository aggregate projection
        │
        ▼
Identity-bearing local envelope
        │
        ▼
Identity-free AnalyticsEvent(category=repository_aggregates)
        │
        ▼
(Not persisted / not transmitted)
```

## Product-path decision

**Construction API + aggregate extractor only.** Normal assess does not invoke
repository aggregate analytics and does not auto-create installation identity.

## Exact-count decision

**Decision A — bounded exact non-negative integer counts.**

- Matches the backlog wording (“aggregated counts”)
- Cap: language file counts and rule counts ≤ **10 000** (overflow rejected)
- Zero-count language groups are **omitted**
- Documented limitation: aggregate shape can still fingerprint large repos

Coarse buckets were considered for privacy; exact capped counts were chosen to
satisfy the product requirement while remaining bounded.

## Language mix

Closed vocabulary:

| `language_group` | Maps from |
| ---------------- | --------- |
| `python` | python / Python |
| `java` | java / Java |
| `javascript_typescript` | javascript, typescript, JS/TS |
| `php` | php / PHP |
| `csharp_dotnet` | csharp / C# / C#/.NET |
| `unclassified` | unknown / other (never raw custom strings) |

**Count meaning:** number of assessed source files classified into each group.

Unknown raw language strings are rejected (`invalid_language_group`).

## Rule execution counts

Overall totals (required):

| Field | Meaning |
| ----- | ------- |
| `attempted` | Rules planned/selected |
| `completed` | Rules that finished evaluation (including zero Findings) |
| `skipped` | Rules not executed |
| `failed` | Internal evaluation failures |

Optional per-head groups use canonical `AssessmentHead` IDs only.

**Semantics:**

- completed ≠ Finding produced
- zero Findings ≠ repository health
- failed ≠ assessment command failure

No rule IDs, names, descriptions, detectors, thresholds, Findings, or Evidence.

## Aggregate input

`RepositoryAggregateAnalyticsInput` accepts only typed aggregates. The extractor
collapses label counts and rule totals — it does **not** traverse repositories
or read report JSON.

## Identity

Local envelope may include `installation_id`. Base `AnalyticsEvent` remains
identity-free. Diagnostics omit identity values.

## Boundaries

- AI provider/model analytics: see [telemetry-ai-analytics.md](telemetry-ai-analytics.md) (Slice 10.6)
- No VS Code analytics (Slice 10.7)
- No Cloud / Data Lake / transmission / persistence
- Report schema 1.2 unchanged

## Related

- [telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md)
- [telemetry-assessment-analytics.md](telemetry-assessment-analytics.md)
- [telemetry-runtime-analytics.md](telemetry-runtime-analytics.md)
- [../PRIVACY.md](../PRIVACY.md)
