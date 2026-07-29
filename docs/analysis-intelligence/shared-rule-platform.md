# Shared Rule Platform

Optional, opt-in rule execution for Analysis Intelligence packs in the Community
Edition Engine. Assessment Graph builtin rules continue to run through the
legacy Rule Engine unless you enable shared packs.

```text
Assessment Inputs
      │
      ▼
RuleExecutionContextFactory
      │
      ▼
Typed RuleExecutionContext
      │
      ▼
RuleRegistry → RulePlanner → RuleExecutor
      │
      ├─ applicability / suppression / evidence / telemetry
      ▼
RulePlatformExecutionResult → RuleFindingMapper → Finding
```

## Dual rule stacks (intentional)

| Stack | Package | Used by |
| ----- | ------- | ------- |
| Assessment Graph rules | `domain.rules.models.Rule` + `services.rule_engine` | `codestrata assess` (default) |
| Shared Rule Platform | `domain.rules.contracts.SharedRule` + `application.rules` | Analysis Intelligence packs (opt-in) |

```text
Assessment
    │
    ├── Legacy RuleEngine  →  Finding   (production path for codestrata assess)
    └── Shared Rule Platform → Finding  (opt-in packs)
```

A thin facade (`RuleExecutionFacade`, `LegacyRuleAdapter`) can expose legacy
rules with SharedRule metadata for inspection while preserving finding identity
when adapted evaluation is used. Adapted legacy rules keep the same repository →
rule → finding ID, severity, title, description, evidence, and metadata.

New Analysis Intelligence rules use the Shared Rule Platform only. There is no
third rule engine.

## Analysis Intelligence flow

```text
Repository Inventory
    → reusable Engine evidence providers
    → capability-specific rules
    → shared Findings
    → assessment inventory / section
    → deterministic synthesis (when enabled)
    → presentation-only report adapter (when enabled)
```

There is no generic `IntelligencePack` abstraction. Capability packs register
shared rules and optional assessment/report gates independently.

## Evidence ownership

Engine evidence providers own parsing and normalized facts (for example
dependency manifests, repository-sensitive artifacts, and repository-observable
testing structure). Intelligence verticals **consume** evidence; they do not
reparse repositories as a second source of truth.

Security Intelligence consumes reusable evidence (including
`evidence.repository_sensitive`) and does **not** own repository parsing,
generic evidence truth, package registries, CVE databases, or SAST engines.
Security rules interpret evidence into shared Findings; they do not introduce a
parallel `SecurityFinding` type.

| Concern | Owner |
| ------- | ----- |
| Manifest / lockfile parsing | Dependency evidence |
| Sensitive artifacts & config literals | `evidence.repository_sensitive` |
| Source / language facts | Language evidence providers |
| Shared Finding identity | Shared Finding model |
| Security interpretation | Security Intelligence rules |

## Shared Finding ownership

All intelligence verticals emit or project the shared Finding model.
Capability-specific finding types are forbidden.

Category mapping examples:

- `RuleCategory.ARCHITECTURE` → `FindingCategory.ARCHITECTURE`
- `RuleCategory.TECHNICAL_DEBT` → `FindingCategory.TECHNICAL_DEBT`
- `RuleCategory.DEPENDENCY` → `FindingCategory.DEPENDENCY`
- `RuleCategory.SECURITY` → `FindingCategory.SECURITY`

## Assessment lifecycle

Sections support explicit statuses such as `disabled`, `not_requested`,
`succeeded`, `insufficient_evidence`, `partially_succeeded`, `failed`, and
`not_applicable`. Empty or disabled sections remain deterministic and do not
claim absence of risk.

Where inventories exist, production is the primary health view; test/fixture
observations remain labeled separately. Capability assembly failures must warn,
mark the section failed/unavailable, and continue the remaining assessment.

## Synthesis and report boundaries

Synthesis is inventory-derived and deterministic. It must not invent scores,
financial impact, upgrade targets, or AI narrative.

Report adapters are presentation-only. They consume in-memory assessment
sections, do not recollect evidence or re-run rules, and are gated independently
(`report.sections.*`). Enabling a report gate does not enable analysis or rules.

## Feature gates

Each vertical uses independent opt-in gates, typically:

- `rules.<capability>.enabled`
- `assessment.sections.<capability>.enabled` / `analysis.<capability>.enabled`
- optional evidence and report gates

Defaults are disabled and backward compatible. Enabling one capability does not
enable others.

## Architecture pack compatibility

When architecture packs are disabled, legacy `RuleEngine` / `codestrata-rule-*`
findings are unchanged. Architecture findings that do run enter the same
findings artifact. Deterministic ordering is preserved via sorted rule IDs and
match sort keys.

Incremental invalidation for architecture rules typically depends on dependency
edges, source imports, graph fingerprint, layer markers, and architecture
configuration.

## Identity

Rule IDs use `namespace.kebab-name` (example: `architecture.layer-dependency`).
No UUIDs. No class-name dependency.

Versions are `major.minor.patch` (`RuleVersion`).

Severity reuses `FindingSeverity`. Confidence is `RuleConfidence` (evidence certainty).

IDs for assessment artifacts are derived from stable semantic facts, not
timestamps, absolute paths, UUIDs, or memory addresses. Artifacts serialize with
stable ordering for byte-identical repeated runs.

## Defaults

```toml
[rules]
enabled = false
fail_on_rule_error = false
max_rules_per_run = 1000
max_matches_per_rule = 1000
max_total_matches = 10000
max_evidence_per_match = 100
```

## CLI / MCP

- `codestrata rules list|inspect|explain`
- MCP: `list_shared_rules`, `get_shared_rule`, `explain_shared_rule_metadata`,
  `get_shared_rule_platform_summary`

Fixture rules are never shown in production list/inspect output.

See also [rule-authoring.md](rule-authoring.md) and
[../rule-engine.md](../rule-engine.md).
