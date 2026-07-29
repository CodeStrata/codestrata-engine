# Installation

> **Canonical public install journey:**
> [Install Engine](https://docs.codestrata.ai/getting-started/install)

Install CodeStrata Engine (Community Edition) for local development or
day-to-day assessment use. Portal steps are canonical; Engine notes for editable
installs, wheels, and packaged resources remain below.

## Requirements

| Requirement | Notes |
| ----------- | ----- |
| Python 3.12+ | Required |
| Git | Required for GitHub clones (`codestrata scan`) |
| AWS credentials | Only for `assess --with-ai` / Bedrock knowledge providers |
| OpenAI API key | Only for `profile = "openai"` knowledge providers |
| Optional extras | `bedrock`, `openai`, `mcp`, `dev` |

## Clone and editable install (recommended)

```bash
git clone https://github.com/CodeStrata/codestrata-engine.git
cd codestrata-engine

python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .
```

Verify:

```bash
codestrata version
codestrata about
```

If you see `ModuleNotFoundError: No module named 'codestrata'`, the package is
not installed in the active environment. Activate `.venv` and re-run
`python -m pip install -e .`.

## Install from a built wheel

For a clean machine (no editable checkout):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install dist/codestrata-*.whl
# Optional extras:
pip install 'codestrata[mcp]'
pip install 'codestrata[bedrock,openai]'
pip install 'codestrata[dev]'
```

Core install supports deterministic `codestrata onboard` / `codestrata assess`
with no cloud credentials. MCP, Bedrock, and OpenAI remain optional extras.

## Optional extras

```bash
# Tests + linters
python -m pip install -e ".[dev]"

# Amazon Bedrock (AI enrichment / Bedrock knowledge providers)
python -m pip install -e ".[bedrock]"

# OpenAI knowledge providers
python -m pip install -e ".[openai]"

# FastMCP server
python -m pip install -e ".[mcp]"

# Everything commonly needed for contributors
python -m pip install -e ".[dev,bedrock,openai,mcp]"
```

Missing optional dependencies produce actionable CLI errors (for example MCP
commands print the `pip install 'codestrata[mcp]'` hint and exit `1`).

## Packaged resources

Installed under `codestrata.resources`:

- `config/codestrata.defaults.toml`
- assessment report schemas under `schemas/assessment/`
- builtin engineering knowledge catalog YAML

Also packaged: HTML branding assets under `codestrata.reporting.assets`.
HTML report bodies are generated in code (no separate template files).

## Environment file

Copy `.env.example` to `.env` for local overrides. Shell environment variables
always win over `.env`. Never commit real secrets.

```bash
cp .env.example .env
```

Common variables: `CODESTRATA_PROFILE`, `AWS_PROFILE`, `AWS_REGION`,
`OPENAI_API_KEY`, `CODESTRATA_GITHUB_TOKEN`. See
[configuration-profiles.md](configuration-profiles.md).

## First configuration

A starter `codestrata.toml` ships in the repository root. Minimum required:

```toml
profile = "community"

[repository]
path = "test-fixtures/sample-js-app"
```

Validate:

```bash
codestrata config validate --config codestrata.toml
```

## Quality gates (contributors)

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

Release maintainers can also run:

```bash
codestrata release check
codestrata release check --skip-smoke   # metadata/resources only
```

`codestrata release check` validates package metadata, required resources, CLI
registration, schemas, default configuration, and related release gates.

See [contributor-guide.md](contributor-guide.md) for contributor quality gates
and use `codestrata release check` before tagging a Community release.

## Uninstall

```bash
python -m pip uninstall codestrata
```

Remove the virtualenv directory (`.venv`) if you created one.

## Community vs Platform

Installing the Community Engine does not install CodeStrata Platform. Platform
capabilities (organizational Knowledge Graph, RAG retrieval/answering, portfolio
intelligence) are separate products. See
[community-vs-platform.md](community-vs-platform.md).
