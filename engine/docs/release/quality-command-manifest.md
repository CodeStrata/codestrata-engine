# Quality-command manifest (E00.2)

Package revision: `ENGINE-2026-09-15-R1`

Executable source of truth: `engine/verification/quality-commands.yaml`.
Run from the repository root:

```text
python -m verification --help
```

requires `PYTHONPATH` to include `engine/` (PowerShell: `$env:PYTHONPATH = "engine"`).

Alternatively, from `engine/`:

```text
python -m verification scope
python -m verification quality --suite harness
python -m verification quality --suite product
python -m verification quality --suite security
```

## Layout drift vs policy text

The Team Execution document's sample commands are written as if `engine/` is
the product root (`python -m ruff check .` after `cd engine/`). On this
checkout the installable package is still the **repository-root**
`pyproject.toml` (`name = "codestrata"`, `package-dir.src`, `testpaths = ["tests"]`).
`engine/pyproject.toml` configures only the scope/quality harness.

| Suite | Working directory | Config |
|---|---|---|
| product | repository root | root `pyproject.toml` |
| harness | `engine/` | `engine/pyproject.toml` |
| security | repository root | `pip-audit` extra in `engine/pyproject.toml` |

## Coverage

Product coverage source remains `codestrata`, branch measurement enabled, combined
floor **80%**. That floor is not a separate 80% branch threshold. Harness
coverage source is `verification` and does not replace the product floor.

## engine-tests job

This clone has no `.github/workflows/` CI workflow files. The inspected
historical `engine-tests` job installs Engine development extras and runs
pytest only. It does not run ruff, mypy, or coverage, and with root
`testpaths = ["tests"]` it does **not** collect `engine/tests/verification`.
Root CI is out of scope; this harness is the mandatory local/authorized-runner
evidence until a compatible existing runner executes these checks.

## Security scanner

Approved scanner: **pip-audit** `>=2.7,<3.0`, pinned as optional extra
`quality` on `engine/pyproject.toml`. Command:

```text
python -m pip_audit --progress-spinner off
```

Severity: known vulnerabilities FAIL; missing tool or unavailable advisory
feed is BLOCKED, never PASS. This is not the customer vulnerability-feed
decision owned by E01/E06.

Sensitive logs: `engine/.quality-runs/<run-id>/` (gitignored). An ignore rule
is not access control.
