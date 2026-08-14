# CLI telemetry consent flags (Slice 9.6 / updated Epic 20)

**Policy:** `community-telemetry-cli-consent-policy:1.0`  
**Scope:** `assess` command only — current CLI process — **not saved** as durable consent

## Flags

| Flag | Meaning |
| ---- | ------- |
| `--telemetry-allow` | Session/frontend **bridge** only when durable consent already permits collection. Does **not** create consent, invent Yes for undecided users, or override Disabled. |
| `--telemetry-deny` | Explicitly deny telemetry for this command/process |

```bash
codestrata assess --repo . --no-ai --telemetry-deny
codestrata assess --repo . --no-ai --telemetry-allow
```

Both flags:

- apply only to the **current** process
- are **never** persisted as durable Engine consent
- never rewrite the preference file
- never create an installation identity by themselves
- take precedence over the interactive prompt for this invocation
- remain subject to privacy filtering

Prefer durable `codestrata telemetry enable` / `disable` for intentional collection
control. Do **not** use `--telemetry-allow` as a CI consent bypass.

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
| `--telemetry-allow` | Bridge only | `cli_flag` | Only if durable consent already allows |
| `--telemetry-deny` | Deny | `cli_flag` | No |

Canonical product docs: https://docs.codestrata.ai/reference/telemetry
