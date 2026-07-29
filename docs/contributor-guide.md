# Contributor guide

How to develop CodeStrata Engine safely and consistently.

Also see [CONTRIBUTING.md](../CONTRIBUTING.md),
[coding-standards.md](coding-standards.md), [SECURITY.md](../SECURITY.md),
and the documentation index [README.md](README.md).

## Development setup

From a `codestrata-engine` checkout:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,bedrock,openai,mcp]'
```

Confirm:

```bash
codestrata version
pytest -q tests/test_cli.py
```

## Where docs live

Prefer the public portal ([https://docs.codestrata.ai](https://docs.codestrata.ai))
for end-user journeys. Keep Engine `docs/` for contracts, architecture, MCP,
security, and contributor guidance ([README.md](README.md)).

## Quality gates (required before PR)

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m build
```

Documentation changes should also pass:

```bash
pytest tests/docs -q
```

## Guidelines

* Prefer small, focused pull requests.
* Deterministic analysis is the source of truth — AI must not invent findings.
* Match existing package layout (`application` / `domain` / `infrastructure`).
* Do not commit secrets, `.env`, or large `reports/` trees.
* Update docs when CLI, artifacts, or configuration change.
* Keep Community Edition surfaces free of Platform-only assumptions.

## Adding a language fixture

1. Create `test-fixtures/sample-<lang>-app/` with a minimal build manifest.
2. Add a short README with `codestrata assess --repo …` instructions.
3. Link it from `test-fixtures/README.md`.
4. Ensure documentation validation still passes (`tests/docs`).
5. Do **not** add language samples to the public showcase examples tree.

## Documentation conventions

* Prefer kebab-case topic files under `docs/`.
* Link related guides instead of duplicating long tables.
* Keep command examples copy-pasteable and validated by `tests/docs`.
* Point troubleshooting at `Fix:` style CLI errors where possible.

## Reporting security issues

See [SECURITY.md](../SECURITY.md). Do not open public issues for vulnerabilities.
