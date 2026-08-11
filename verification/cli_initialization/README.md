# SV.3 — CLI Initialization Workflow Verification

Verification-only suite for first-time `codestrata init` behavior.

## Verified product behavior (current)

| Topic | Behavior |
| --- | --- |
| Command | `codestrata init` (`--config/-c`, `--force`) |
| Help | `codestrata --help` (no `help` subcommand) |
| Output | Writes `codestrata.toml` only |
| Root discovery | **None** — config is written in the working directory |
| Existing config | Refused without `--force` (valid or malformed) |
| Interactive | No prompts |
| Network | Not required |
| Telemetry | No telemetry section; not enabled by init |
| AI | `[ai].provider = "bedrock"` may appear; assess still needs `--with-ai` |
| Profile | `profile = "community"` currently nests under `[repository]` (TOML table rules) |
| Workspace dirs | Declared in config; **not** created by init |

## Scenarios

A minimal · B empty · C existing valid · D malformed · E unwritable · F nested cwd ·
G path with spaces · H non-interactive · I unsupported shape · J unrelated files ·
K determinism pair

## Run

```bash
cd engine
python -m verification.cli_initialization --method pip_path_non_editable
```

Report: `reports/verification/cli-initialization-verification.json`

## Isolation

Reuses SV.2 principles: fresh venv, non-editable install, scrubbed `PYTHONPATH`,
temporary `HOME`, no network, no developer checkout assumptions for the CLI under
test.

## Boundaries

- Not shipped in the `codestrata` wheel
- Does not modify the repository catalog
- Does not start SV.4
- Product code is unchanged unless a reproducible verification failure is found
