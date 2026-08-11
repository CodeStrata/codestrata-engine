# CLI telemetry consent flags (Slice 9.6)

**Policy:** `community-telemetry-cli-consent-policy:1.0`  
**Scope:** `assess` command only — current CLI process — **not saved**

## Flags

| Flag | Meaning |
| ---- | ------- |
| `--telemetry-allow` | Explicitly allow privacy-safe telemetry **attempts** for this command/process |
| `--telemetry-deny` | Explicitly deny telemetry for this command/process |

```bash
codestrata assess --repo . --no-ai --telemetry-deny
codestrata assess --repo . --no-ai --telemetry-allow
```

Both flags:

- apply only to the **current** process
- are **never** persisted
- never reuse prior consent or legacy preferences
- never create an installation identity
- never create or flush a telemetry queue
- never enable HTTP transmission in this release
- take precedence over the interactive prompt and non-interactive suppression
- remain subject to privacy filtering

They provide automation-safe **consent semantics**. They do **not** make
telemetry operational.

## Mutual exclusivity

```bash
codestrata assess --telemetry-allow --telemetry-deny
```

Fails with exit code 2 and:

```text
--telemetry-allow and --telemetry-deny cannot be used together.
```

Assessment does not start. No prompt, transport, preference, identity, queue, or
network side effects.

## Mapping

| Flag | Decision | Source | Transmission authorized |
| ---- | -------- | ------ | ----------------------- |
| `--telemetry-allow` | `allowed_for_session` | `cli_flag` | yes |
| `--telemetry-deny` | `denied_for_session` | `cli_flag` | no |

`transmission_authorized=true` means the runtime **may** call the transport port
after privacy projection. Default transport remains unavailable → result
`unavailable`, never `sent`.

## Precedence

1. Both flags → CLI error (stop)
2. Either flag → explicit `cli_flag` consent; **no prompt**; stdin unused
3. No flags → existing Slice 9.4 / 9.5 interactive or non-interactive behavior

Explicit allow in CI / pipes / quiet / JSON:

- no prompt
- allow takes precedence over `non_interactive_disabled`
- unavailable transport may be invoked
- no success/telemetry banner

## Command scope

Flags are on **`assess` only**.

`scan` is a separate legacy/advanced command (not an assess alias) and does **not**
receive these flags. It does not prompt for telemetry consent.

Do not use environment variables, `codestrata.toml`, or user preferences as
equivalents.

## Legacy telemetry commands

`codestrata telemetry enable|disable|status|…` remain separate compatibility
commands. Enabling a legacy preference does **not** authorize the privacy-first
runtime for `assess`. Assess flags do not persist as a default for later runs.

## Deferred

- Community Cloud HTTP transport

## Related

- [telemetry-preview.md](telemetry-preview.md)
- [telemetry-event-catalog.md](telemetry-event-catalog.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-non-interactive.md](telemetry-non-interactive.md)
- [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- [telemetry-session-consent.md](telemetry-session-consent.md)
- [telemetry-disabled-default.md](telemetry-disabled-default.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry.md](telemetry.md)
- [../PRIVACY.md](../PRIVACY.md)
