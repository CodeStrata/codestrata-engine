# Anonymous telemetry (Community Edition)

**Default:** Disabled  
**Schema:** `1.0.0`

CodeStrata Community telemetry is **privacy-first**: anonymous, minimal,
versioned, and **explicit opt-in only**.

## Principles

| Principle | Behavior |
| --------- | -------- |
| Disabled by default | No events leave the machine until you opt in |
| Explicit opt-in | First-run prompt defaults to **No**; or `codestrata telemetry enable` |
| Transparent | `codestrata telemetry show` prints the exact payload shape |
| Anonymous | Random UUID v4 installation id under `~/.codestrata/` |
| Minimal | Bands and categories only — never source or repository identity |
| Non-blocking | Local queue + short timeout; assessments never wait on network |

## Commands

```bash
codestrata telemetry status
codestrata telemetry enable
codestrata telemetry disable
codestrata telemetry reset
codestrata telemetry show
```

## Events

- `installation_created`
- `telemetry_enabled` / `telemetry_disabled`
- `assessment_started` / `assessment_completed` / `assessment_failed`
- `report_opened`
- `ai_used`
- `version_check`
- `upgrade_completed`

## Size bands

`0-100` · `101-500` · `501-1000` · `1001-5000` · `5001-10000` · `10000+`

## Language categories

`python` · `java` · `javascript` · `typescript` · `go` · `csharp` · `rust`

## FAQ

**Is telemetry on after install?**  
No.

**Can I inspect payloads?**  
Yes — `codestrata telemetry show`.

**Does offline mode break assess?**  
No. Events queue under `~/.codestrata/telemetry-queue.jsonl`.

**How do I turn it off forever on this machine?**  
`codestrata telemetry disable` or `CODESTRATA_TELEMETRY=0`.

**How do I get a new anonymous id?**  
`codestrata telemetry reset`.

See also: [PRIVACY.md](../PRIVACY.md).
