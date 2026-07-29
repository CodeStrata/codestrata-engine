# Contributing to CodeStrata Engine

Thanks for contributing to the Community Edition Engine.

Full workflow: [docs/contributor-guide.md](docs/contributor-guide.md).  
Public docs portal: [https://docs.codestrata.ai](https://docs.codestrata.ai).

## Development setup

Requires Python 3.12+.

From a `codestrata-engine` checkout:

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mcp]"
```

Optional extras: `bedrock`, `openai`.

## Quality gates

Canonical contributor / Community Engine release checks (from `engine/`):

```bash
pytest
pytest tests/docs -q
ruff check .
mypy src
```

Format changed files before review (`ruff format <paths>`). Full-tree
`ruff format --check .` still reports historical debt outside the release gate;
do not mass-reformat unrelated files solely to green the check.

Monorepo maintainers also run `python scripts/verify_release.py` from the
platform root (Engine-scoped ruff/mypy, then monorepo pytest excluding
`network`).

## Guidelines

* Prefer small, focused pull requests.
* Deterministic analysis remains the source of truth; do not let AI invent
  findings or recommendations.
* Match existing package layout (`src/codestrata/…`, tests under `tests/`).
* Do not commit secrets, `.env` files, or large generated `reports/` trees.
* Update Engine docs under `docs/` when behavior or artifacts change.
* Prefer a visibility HTML comment on new Markdown docs when useful:
  `<!-- documentation-visibility: public-community|public-contributor|public-contract -->`.
* Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Community vs Platform

This repository is the **Community Engine**. Commercial Platform capabilities
(hosted control plane, organizational Knowledge Graph, portfolio/executive
intelligence) are separate products and are not required to contribute here.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not open public issues for vulnerabilities.

## License

By contributing, you agree that your contributions are licensed under the MIT
License ([LICENSE](LICENSE)).
