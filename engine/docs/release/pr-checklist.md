# PR checklist for Engine-only story work (E00.2)

Use this checklist on every PR into `release/engine-next`. A green historical
`engine-tests` pytest job is not evidence that lint, strict typing, or coverage
passed. Root CI must not be edited in this backlog.

## Scope

- [ ] Scope guard PASS: `python -m verification scope` from `engine/` (or
      `PYTHONPATH=engine python -m verification scope` from the repository root).
- [ ] Changed **tracked** files remain under `engine/`.
- [ ] Guard inspected: added/untracked, rename source and destination, deletions,
      staged, unstaged, and cumulative diff vs `release/engine-next`.
- [ ] Pre-existing dirty/untracked inventory was compared; unrelated work was
      not reset.
- [ ] No edits to root scripts, workflows, lockfiles, export manifest,
      root `pyproject.toml`, or files outside `engine/`.

## Quality evidence (mandatory local or authorized runner)

Record true exit codes. Do not relabel G00 baseline failures as new passes.

- [ ] Harness suite PASS (`--suite harness`): ruff, mypy, pytest+coverage on
      `engine/verification` and `engine/tests`.
- [ ] Product suite recorded (`--suite product`): `pip check`, root ruff,
      root mypy, root pytest with `--cov=codestrata --cov-branch --cov-fail-under=80`.
      Current G00 baseline is **failing**; keep it labeled BASELINE_FAIL until
      repaired in allowed Engine scope.
- [ ] Security scanner: `pip-audit` as pinned in `engine/pyproject.toml`
      extra `quality`. Missing tool or feed is **BLOCKED**, not clean.
- [ ] No production publish credentials in normal tests or in the runner env.

## Review

- [ ] Different engineer reviews (no self-merge).
- [ ] Completion record under `engine/docs/implementation/` attached or linked.
- [ ] This PR does not publish, tag, deploy, or notify.

## Outside-Engine consumers

- [ ] Root `tests/`, `verification/`, `examples/`, and `validation/` imports of
      `codestrata` were inspected read-only; this story does not change them.
