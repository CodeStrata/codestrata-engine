# Outside-Engine consumer imports (read-only, E00.2)

Inspected 2026-09-16 on checkout `76173eb0310831529e2021bd8191e502936f2e5c`.
No files outside `engine/` were modified.

The installable package remains `src/codestrata` at the repository root.
Outside-Engine consumers import that package; they are not part of this
story's change set.

| Location | Role | Import style |
|---|---|---|
| `tests/` | Engine product tests (root pytest `testpaths`) | `from codestrata...` / `import codestrata` |
| `verification/` | Historical verification helpers at repo root | `from codestrata...` |
| `examples/` | Consumer examples | CLI / docs; not edited |
| `validation/` | Validation fixtures and runners | mix of local fixtures and Engine usage |
| `docs/` | Contributor commands (`pytest`, `ruff`, `mypy`) | documentation only |

Root pytest `testpaths = ["tests"]` therefore collects `tests/verification/`
and does not collect `engine/tests/verification`. Scope regression tests for
this program live under `engine/tests/verification` and run through the
Engine-owned harness.

Existing tests under `tests/verification/` still assume a future nested
`engine/src/codestrata` layout in some boundary files (for example
`tests/verification/cli_installation/test_boundary.py`). That is pre-existing
product/test drift, recorded here, not repaired in E00.2.
