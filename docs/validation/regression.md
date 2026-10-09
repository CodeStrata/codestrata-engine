# Engine validation regression harness (E15.2)

**Status:** `PASS`  
**Measurement:** M33  
**Story:** E15.2

This harness extends E00.2 quality commands and the E15.1 corpus labels.
Default execution uses Engine-owned planted artifacts. It does not clone
the 50 remotes, does not run assessed-project tests or builds, and is not
G50/G52 release evidence.

## Outcomes

- `meta:story`: **PASS** — E15.2/M33
- `quality:coverage_source`: **PASS** — codestrata
- `quality:coverage_branch`: **PASS** — branch=True
- `quality:fail_under`: **PASS** — 80
- `quality:not_separate_branch_threshold`: **PASS** — combined floor with branch measurement; not a second 80% branch gate
- `quality:required_commands`: **PASS** — e00.2 commands present
- `quality:engine_tests_not_coverage`: **PASS** — proves=('pytest-unit',)
- `contract:old_client`: **PASS** — OfflinePlatformClient
- `install:wheel_include`: **PASS** — codestrata* only
- `install:verification_not_in_src`: **PASS** — harness stays beside src/
- `install:harness_present`: **PASS** — maintainer regression package
- `repeats:policy`: **PASS** — 3
- `repeats:configurations`: **PASS** — planted-local,representative-java,dogfood
- `repeats:planted-local`: **PASS** — equal
- `repeats:representative-java`: **PASS** — equal
- `repeats:dogfood`: **PASS** — equal
- `adversarial:resource-exhaustion`: **PASS** — exhaustion is ERROR
- `adversarial:corruption`: **PASS** — ERROR
- `adversarial:sigint-sigterm-hard-kill`: **PASS** — CANCELLED
- `adversarial:disk-full`: **PASS** — ERROR
- `adversarial:output-collision`: **PASS** — baseline retained
- `adversarial:concurrent-reader`: **PASS** — stable_read
- `adversarial:retention-active-baseline`: **PASS** — retained
- `adversarial:audit-redaction`: **PASS** — redacted
- `coverage:unknown_denominator`: **PASS** — UNKNOWN
- `contract:tamper`: **PASS** — TAMPERED
- `report:escaping`: **PASS** — escaped
- `parity:full_vs_incremental`: **PASS** — semantic digest
- `scan:invocation`: **PASS** — assess --no-ai; no project tests/builds
- `malicious-source:not_executed`: **PASS** — planted scripts were not invoked
- `egress:policy`: **PASS** — default no egress
- `egress:attempts`: **PASS** — no URLs fetched
- `egress:redaction`: **PASS** — remaining credential keys: none
- `scan:silent_fetch`: **PASS** — no silent fetch
- `labels:m33_kinds`: **PASS** — all nine kinds have harness classifiers
- `skips:inflation`: **PASS** — 4 disclosed

## Not yet due

- `G30`
- `G40`
- `G50`
- `G52`
- `E15.3`
- `published-m33-budgets`
- `e11.2-html-views`
- `g40-install-smoke`

## Notes

- Default tests do not clone the 50 remotes; E15.3/G50 execute the three tiers.
- Quality-command argv stay in E00.2; this harness asserts the floor and required ids.
- Proposed M33 time/RSS budgets remain unpublished.
- Failed or unrun required checks are never PASS.
