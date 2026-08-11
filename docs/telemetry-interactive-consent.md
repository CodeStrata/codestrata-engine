# Interactive per-session telemetry consent (Slice 9.4)

**Policy:** `community-telemetry-interactive-consent-policy:1.0`  
**Default answer:** No (`[y/N]`)  
**Scope:** current CLI process only — not saved

## Prompt wording

```
Optional privacy-safe telemetry
-------------------------------
Telemetry is disabled by default. If you allow it, consent applies only to this
command/process and is not saved. No installation identity is created. Source
code, repository names, paths, findings, prompts, credentials, and personal
identifiers are not collected. Telemetry failures cannot block this command.
Transport is not operational in this release — allowing only prepares a
privacy-filtered session decision.

Allow privacy-safe telemetry for this command only? [y/N]:
```

## Eligible commands

- `assess`

## Excluded commands

- `--help` / help
- `--version` / `version` / `about`
- `welcome`
- `telemetry status|enable|disable|reset|show`
- shell completion helpers
- other non-assess product commands (including `open` / report helpers)

Conservative: only the primary assessment workflow prompts.

## Answers

| Input | Result |
| ----- | ------ |
| `y` / `yes` (case-insensitive, trimmed) | `allowed_for_session` + `interactive_prompt` |
| `n` / `no` / empty | `denied_for_session` + `interactive_prompt` |
| anything else | denied (one attempt; no retry loop) |
| EOF | denied |
| KeyboardInterrupt during prompt | denied; **primary command continues** |

Silence is never consent. Enter alone is denial.

## Behavior

- at most **one** prompt attempt per process
- early in `assess`, before telemetry recording
- no preference / consent / identity / queue files written
- legacy prefs, installation IDs, queues, and endpoints are ignored
- allow does **not** transmit (transport remains unavailable)
- privacy projection remains mandatory
- non-TTY / missing stdin / `--quiet` / `--json-summary` / CI / automation →
  no prompt (see [telemetry-non-interactive.md](telemetry-non-interactive.md))

## Mapping

| Outcome | Consent |
| ------- | ------- |
| Prompt not shown (non-interactive policy) | `non_interactive_disabled` + `non_interactive_policy` |
| Prompt not shown (excluded / help / completion) | `disabled_by_default` + `default` |
| User declined / empty / invalid / EOF / interrupt | `denied_for_session` + `interactive_prompt` |
| User allowed | `allowed_for_session` + `interactive_prompt` |

## Not yet available

- Public catalog: [telemetry-event-catalog.md](telemetry-event-catalog.md)
- Preview: [telemetry-preview.md](telemetry-preview.md)
- Community Cloud HTTP transport

Automation-safe flags: [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md).

## Related

- [telemetry-status.md](telemetry-status.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry-non-interactive.md](telemetry-non-interactive.md)
- [telemetry-session-consent.md](telemetry-session-consent.md)
- [telemetry-disabled-default.md](telemetry-disabled-default.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [../PRIVACY.md](../PRIVACY.md)
