# Engine-only PR checklist (E00.2)

Use this checklist on every Engine story PR into `release/engine-next`.
It is a **reviewer checkpoint**, not an automatic GitHub branch-protection
rule. Root CI job `engine-tests` runs pytest only; it does not prove ruff,
mypy, coverage, or pip-audit.

## Scope

- [ ] From `engine/`: `python -m verification.engine_scope --baseline origin/main` exits 0
      (must run from `engine/` — the repository root has a different `verification/` package)
- [ ] Every added, modified, renamed, copied, deleted, staged, unstaged and untracked path is under `engine/`
- [ ] Rename source **and** destination were inspected
- [ ] Root `scripts/`, `.github/workflows/`, lockfiles and `public-export-manifest.yaml` were not edited
- [ ] Pre-existing dirty/untracked inventory was captured (`--write-inventory`) and **not reset**
- [ ] Cumulative diff versus the recorded release baseline is Engine-only
- [ ] No outside-Engine consumer tree was written (Platform / extension / root verification imports are read-only)

## Quality evidence

- [ ] `python -m pip check` recorded with true exit code
- [ ] `python -m ruff check .` recorded with true exit code
- [ ] `python -m mypy --config-file pyproject.toml` recorded with true exit code
- [ ] `python -m pytest tests --import-mode=importlib --cov=codestrata --cov-branch --cov-report=term-missing --cov-fail-under=80 -q` recorded with true exit code
- [ ] `python -m pip_audit --progress-spinner off` recorded as PASS, FAIL, or BLOCKED (missing tool/feed is BLOCKED, never clean)
- [ ] G00 baseline failures remain labeled `BASELINE_FAIL`; they were not relabeled as new passing tests
- [ ] Coverage source remains `codestrata`, branch measurement on, floor 80
- [ ] Logs live under `engine/.quality-runs/<run-id>/` (gitignored); summaries under `engine/docs/implementation/gates/`
- [ ] No production publish credentials in tests or quality logs

## Review

- [ ] Author is not the integrator
- [ ] Story completion record lists SHA, commands, skip reasons, defects
- [ ] This PR does not publish, tag, deploy or notify
- [ ] Candidate work used `.venv-engine-next` and `engine/.tmp-assess/engine-next-candidate/` (or a versioned `engine/.tmp-assess/candidates/<label>/`); live installs and `.codestrata/` snapshots were not rewritten
- [ ] Live hotfixes, if any, landed on `main` and were recorded before backport into `release/engine-next`
