# Privacy-first telemetry status (Slice 9.7–9.9)

**Policy:** `community-telemetry-status-policy:1.0`  
**Status schema:** `privacy-first-telemetry-status` `1.0.0`  
**Command:** `codestrata telemetry status`

## Purpose

Report the authoritative privacy-first telemetry posture in developer-facing
language. Status describes **facts and capabilities**, not the consent decision
of a future `assess` run.

```bash
codestrata telemetry status
```

## Authoritative answers (v0.2.0 / Slice 9.7–9.9)

| Topic | Status |
| ----- | ------ |
| Default runtime | Disabled |
| Consent scope | Current command/process only |
| Consent saved | No |
| Prior consent reused | No |
| Interactive prompt | `assess` only, when eligible (default No) |
| Explicit flags | `--telemetry-allow` / `--telemetry-deny` on `assess` |
| Non-interactive | Prompt suppressed |
| Privacy filtering | Required |
| Transport | Unavailable (default) |
| Operational transport configured | No |
| HTTP transport implementation | Present, explicit configuration required |
| Transmission | Not operational |
| Installation identity | Not used by the privacy-first runtime |
| Status side effects | None |
| Legacy controls | Separate; do not authorize the privacy-first runtime |
| Public event catalog | Available (`telemetry-event-catalog`, schema `1.0.0`) |
| Preview command | Available (`codestrata telemetry preview`; local only; no transmission) |
| Pre-transport privacy gate | Required / Available (policy `1.0`) |

Status reports catalog schema version, documentation label, event count, and
field count. It reports that preview and the pre-transport privacy gate are
available but does **not** execute preview, dump diagnostics, or embed a sample
event. It does **not** print filesystem paths or dump the full catalog.
See [telemetry-event-catalog.md](telemetry-event-catalog.md),
[telemetry-event-catalog.json](telemetry-event-catalog.json),
[telemetry-preview.md](telemetry-preview.md), and
[telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md).

## Side-effect-free

Status does **not**:

- prompt or consume stdin
- construct the active legacy telemetry service
- read or generate installation identity
- read preferences, queues, or endpoint configuration
- create directories or mutate files
- transmit or queue events
- alter the assess prompt-attempt guard
- authorize a later assess invocation

Existing legacy files remain untouched.

## Legacy compatibility

Legacy preference commands remain:

- `codestrata telemetry enable`
- `codestrata telemetry disable`
- `codestrata telemetry reset`
- `codestrata telemetry show`

They manage **separate compatibility state** only. A legacy “enabled”
preference does **not** change privacy-first status or authorize normal
product commands.

Status does **not** inspect legacy filesystem state by default (safer and
deterministic). It does not display installation IDs, endpoints, queue
contents, or paths.

## Output

Human-readable stdout only (no new `--json` option in this slice). Internal
tests use the typed status model’s stable serialization.

Successful inspection exits **0**.

## Deferred / historical

- Former CodeStrata Cursor Extension telemetry — **removed** in Epic 12; not an
  active Community product surface

VS Code command-local telemetry (Slice 9.13) and cross-client / Epic completion
verification (Slices 9.14–9.15) are documented under
`verification/privacy_first_telemetry/` and
`verification/privacy_first_telemetry_completion/`.

HTTP transport exists but is **not** activated by normal CLI construction.
Assessment lifecycle isolation is documented in
[telemetry-assessment-isolation.md](telemetry-assessment-isolation.md).

## Related

- [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md)
- [telemetry-transport.md](telemetry-transport.md)
- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- [telemetry-preview.md](telemetry-preview.md)
- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry-non-interactive.md](telemetry-non-interactive.md)
- [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- [telemetry-session-consent.md](telemetry-session-consent.md)
- [telemetry-disabled-default.md](telemetry-disabled-default.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry.md](telemetry.md)
- Epic 9 completion: [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md)
- [../PRIVACY.md](../PRIVACY.md)
