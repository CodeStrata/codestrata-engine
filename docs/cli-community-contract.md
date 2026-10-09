# Community CLI contract (E11.1)

Package revision `ENGINE-2026-09-15-R1`.

Local use does not require an account, a login prompt, or a collection opt-in.

| Command | Role | Exit |
|---|---|---|
| `codestrata init` | Write a Community `codestrata.toml` | 0 written, 1 already exists without `--force` |
| `codestrata doctor` | List capabilities, trust, and config | 0 when required checks pass, 1 when one fails |
| `codestrata assess --repo <path> --no-ai` | Deterministic local assessment | 0 success, 1 failure, 2 invalid usage |
| `codestrata compare --baseline <report.json> --candidate <report.json>` | Explicit comparison | 2 when a path is missing, 1 when a report cannot be compared |

`compare` never chooses a baseline. Both files are caller-supplied.

## Bundled defaults

The Community default catalog id is `codestrata.engineering-standard`.
Documented parameter: `max_cycle_length = 8`.

Documented exclusions in the init file:

- `[knowledge].enabled = false`
- `[static_analysis].enabled = false`

Suppressions are unsigned local configuration. They do not author a customer RuleSet and they do not rewrite historical findings.

## Migration

- `codestrata scan` remains a legacy clone path. Prefer `assess --repo <path> --no-ai`.
- `codestrata report publish` is not a Community upload.
- `codestrata rules create` and `codestrata rules load` are not supported. `rules` exposes `list`, `inspect`, and `explain` only.

Doctor reports capabilities, trust, and config. It does not require cloud credentials.
