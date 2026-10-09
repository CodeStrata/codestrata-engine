# Quality baseline (G00) — do not relabel as PASS

Recorded on `release/engine-next` at G00 (`bca0a44960bdc8a668681f073905b492562ced4b`).
Host: Windows, Python 3.14.7, venv `.venv-engine-next`. Commands run from `engine/`.

These exits remain **FAIL / BASELINE_FAIL** until repaired inside Engine.
They are not new passing tests for E00.2.

| Command | G00 exit | Status |
|---|---|---|
| `python -m pip check` | 0 | PASS |
| `python -m ruff check .` | 1 | BASELINE_FAIL (644 ruff findings) |
| `python -m mypy --config-file pyproject.toml` | 1 | BASELINE_FAIL (133 errors / 55 files; includes POSIX-only APIs on Windows) |
| `python -m pytest tests --import-mode=importlib --cov=codestrata --cov-branch --cov-report=term-missing --cov-fail-under=80 -q` | 2 | BASELINE_FAIL (collection errors: missing `resource` module) |
| `python -m pip_audit --progress-spinner off` | 0 after extra install on E00.2 | PASS for the isolated venv (`pip-audit` 2.10.1, “No known vulnerabilities found”). Missing-module run is BLOCKED, not clean. |

Raw logs: `engine/.quality-runs/g00-preflight/` (gitignored).

Root job `engine-tests` invoking pytest is **not** evidence that lint, types or coverage ran.
