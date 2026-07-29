# Rule authoring

How to implement Shared Rule Platform rules for Community Edition Analysis
Intelligence packs.

Implement `SharedRule`:

1. Immutable `RuleMetadata` with stable `rule_id` and `RuleVersion`
2. `evaluate_applicability(context) -> RuleApplicability`
3. `evaluate(context) -> SharedRuleEvaluationResult`

Rules must not:

- load files / call subprocess / network / AI
- query SQLite or YAML
- mutate graphs
- emit CLI/MCP output

Register explicitly via `RuleRegistry.register` / `register_collection`.
No dynamic imports or entry-point plugins for shared rules.

## Lifecycle

1. Author + unit test with harness
2. Explicit registry registration in application composition
3. Plan (`RulePlanner`) — deterministic selection
4. Execute (`RuleExecutor`) — isolated failures
5. Suppress (application service) — matches remain inspectable
6. Map to `Finding` via `Finding.create` / `build_finding_id`
7. Telemetry + explainability

## Unit testing with `RuleTestHarness`

```python
from codestrata.application.rules.harness import RuleTestHarness
from codestrata.domain.rules.enums import RuleResultStatus

harness = RuleTestHarness([MyRule()])
result = harness.execute_one(MyRule())
harness.assert_status("my.category.rule-id", result, RuleResultStatus.MATCHED)
harness.assert_match_count(result, 1)
findings = harness.map_findings(result)
```

Internal fixtures (`fixture.always-match`, …) live in
`codestrata.application.rules.fixtures` and must be registered with
`production=False`. Fixture rules never appear in production list/inspect
output.

For evidence-backed hygiene rules, prefer in-memory aggregated evidence
fixtures and `rule.evaluate(context)`.

See also [shared-rule-platform.md](shared-rule-platform.md).
