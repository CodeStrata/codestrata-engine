# Assessment telemetry failure isolation (Slice 9.12)

**Policy:** `community-telemetry-assessment-isolation-policy:1.0`  
**Assessment schema:** remains `1.2`  
**Runtime event schema:** remains `1.0`

## Purpose

Prove that privacy-first telemetry is an optional side effect throughout the
real `codestrata assess` lifecycle. The primary assessment result is always
authoritative.

## Authoritative isolation principle

```text
primary_result = run_assessment()   # always wins

telemetry side effects (fail-silent):
  feature_invoked → feature_completed | operation_failed
```

Telemetry must never control whether assessment starts, analyzers run, Findings
or Recommendations are created, AI runs, reports are written, which exit code
is returned, or which product exception is shown.

## Lifecycle events (bounded)

| Outcome | Events |
| ------- | ------ |
| Success | `feature_invoked` → `feature_completed` |
| Failure | `feature_invoked` → `operation_failed` |

No per-file, per-rule, per-Finding, or per-head events.

## Assess integration

`codestrata assess` wraps `run_assessment` with
`run_assessment_with_telemetry_isolation`:

1. Consent / session construction (flags, prompt, or non-interactive)
2. Isolated lifecycle: invoke → primary → complete/fail
3. Product exit-code and error formatting unchanged

CLI configuration conflicts (`--telemetry-allow` + `--telemetry-deny`) remain
exit **2** before assessment — that is intentional CLI validation, not a
telemetry runtime failure.

## Guarantees

| Scenario | Assessment |
| -------- | ---------- |
| Telemetry unavailable / rejected / timeout / malformed ack | Unchanged |
| Privacy-gate or mapping failure | Unchanged |
| Telemetry exception during record | Unchanged (fail-silent) |
| Primary failure + telemetry success or failure | Primary exit/error wins |
| Prompt EOF / interrupt inside telemetry prompt | Assessment continues |
| Primary `KeyboardInterrupt` | Preserved (not swallowed) |
| `--telemetry-allow` | Does **not** activate HTTP |
| Normal assess | Network-free; default unavailable transport |

## Test injection seam

Tests may inject a transport into `ensure_interactive_product_telemetry(..., transport=...)`
or `create_session_telemetry_runtime(..., transport=...)`.

No public CLI option or environment variable activates HTTP.

## What this slice does not do

- Former Cursor extension integration — removed in Epic 12 (not deferred work)
- Installation IDs, consent persistence, queues, workers
- Endpoint / credential CLI flags
- Assessment schema or analyzer changes
- Community Cloud / Data Lake product changes

## Related

- [telemetry-transport.md](telemetry-transport.md)
- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- Cross-client verification (Slice 9.14): [`../../verification/privacy_first_telemetry/README.md`](../../verification/privacy_first_telemetry/README.md)
- Epic 9 completion (Slice 9.15): [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)
