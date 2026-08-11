# Security Context Classification

<!-- documentation-visibility: internal-engine -->

Phase that classifies *where* secret-like evidence originates before findings
are presented to customers.

## Goal

Preserve detector recall while reducing false positives in leadership and
customer-facing security surfaces.

## Pipeline

```text
Evidence / content detection
        │
        ▼
Security context classification   ← path + value heuristics
        │
        ▼
Severity / confidence adjustment  ← never drops matches
        │
        ▼
Finding generation + reporting
```

## Contexts

| Context | Typical severity |
| ------- | ---------------- |
| `production` | Unchanged (high/critical) |
| `test` / `test_fixture` / `mock_credential` | Low / informational |
| `ci_expression` | Informational |
| `configuration_schema` | Informational |
| `dependency_metadata` | Informational |
| `documentation` / `sample` / `generated` / `build_artifact` | Informational |
| `unknown` | Medium |

## Modules

- `domain/security/context.py` — enum + decision model
- `application/security/context/classifier.py` — heuristics
- `application/security/context/policy.py` — severity/confidence mapping

Wired into:

- `CredentialLiteralRule` / `PrivateKeyMaterialRule` / `PlaceholderCredentialRule`
- Phase 1 `SecurityAnalyzer` (SEC001–SEC006)
- Security inventory `map_source_role`
- Leadership signal filter (informational + context markers)

## Non-goals

- Does not disable or delete detectors
- Does not suppress findings from JSON inventories
- Does not invent vulnerability conclusions
