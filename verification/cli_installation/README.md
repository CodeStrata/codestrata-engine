# SV.2 — Clean CLI Installation Verification

Verification-only suite proving a first-time Community user can install and run
CodeStrata Engine without developer setup (no editable install, no `PYTHONPATH`,
no monorepo assumptions).

## Contract

See `contract.py`:

| Concern | Rule |
| --- | --- |
| OS | `darwin`, `linux`, `win32` (Python layer is OS-independent) |
| Python | `>= 3.12` |
| Methods | `pip_wheel` (preferred), `pip_sdist`, `pip_path_non_editable` |
| Forbidden | editable installs, developer `PYTHONPATH`, pre-existing config |

## Happy path

1. Fresh virtualenv
2. `pip install` (wheel / sdist / non-editable path)
3. `codestrata --version`
4. `codestrata --help` (there is no `codestrata help` subcommand)
5. `codestrata init`
6. `codestrata doctor`

## Failure scenarios

- Unsupported Python version (contract gate)
- Missing dependency (empty venv cannot import `codestrata`)
- Doctor without configuration
- Init when configuration already exists
- Init against an invalid workspace path

## Run

From the Engine root (`engine/`):

```bash
python -m verification.cli_installation --method pip_wheel
python -m verification.cli_installation --method pip_path_non_editable
```

Report: `reports/verification/cli-installation-verification.json`

## Tests

```bash
python -m pytest -q tests/verification/cli_installation
```

## Boundaries

- Not shipped inside the `codestrata` wheel
- Exported with the public Engine repository as `verification/**`
- Does not redesign CLI, packaging, or schemas
- Does not start SV.3
