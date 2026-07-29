# Rule engine

Deterministic findings from Assessment Graph context (Community Edition default
assessment path).

```text
Assessment Graph (+ inventory / bindings)
        ↓
Rule Engine (builtin rules)
        ↓
findings.json
```

## Guarantees

* Read-only evaluation (`RuleContext`); no graph mutation
* No AI provider calls
* Stable finding IDs suitable for recommendation mapping and enrichment
  traceability
* Assessment findings use the domain `Finding` model (distinct from analyzer
  finding records produced earlier in the pipeline)

## Artifact

`findings.json` in the run directory.

## Dual stacks

`codestrata assess` continues to evaluate legacy Assessment Graph rules through
the Rule Engine. Optional Analysis Intelligence packs use the Shared Rule
Platform and map into the same shared `Finding` model. See
[analysis-intelligence/shared-rule-platform.md](analysis-intelligence/shared-rule-platform.md).

## Evidence provider limitations

Language and repository evidence providers support rules; they do not replace
them:

* Providers adapt existing extractors; they do not introduce new language parsers.
* Build-module / dependency-manifest capabilities are unsupported in providers.
* Full symbol tables are unsupported.
* JavaScript provider maturity is experimental/partial.
* Framework leakage findings are produced by shared rules, not providers.
* Engineering Knowledge Graph remains optional and separate (Platform).

## Downstream

Findings feed the [Recommendation Engine](recommendation-engine.md). Optional
[AI enrichment](ai-enrichment.md) may reference finding IDs but must not alter
this file.

Rule authoring for shared packs:
[analysis-intelligence/rule-authoring.md](analysis-intelligence/rule-authoring.md).
