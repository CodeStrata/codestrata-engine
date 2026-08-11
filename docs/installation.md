# Installation

> **Canonical public install journey:**
> [Install Engine](https://docs.codestrata.ai/getting-started/install)
>
> Editor client: [Install CodeStrata for VS Code](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment)
> (`CodeStrataAI.codestrata-assessment`). Extension source is private.

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

## Clean installation verification (SV.2)

Maintainers can reproduce a **first-time Community install** (fresh venv, no
editable install, no developer `PYTHONPATH`) with:

```bash
cd engine
python -m verification.cli_installation --method pip_wheel
# or (faster in CI):
python -m verification.cli_installation --method pip_path_non_editable
```

See [`../verification/cli_installation/README.md`](../verification/cli_installation/README.md).
This is verification only — it does not change packaging or CLI behavior.

## Initialization verification (SV.3)

Verify first-time `codestrata init` behavior (existing-config refusal, nested cwd,
non-interactive defaults, source integrity, determinism):

```bash
cd engine
python -m verification.cli_initialization --method pip_path_non_editable
```

See [`../verification/cli_initialization/README.md`](../verification/cli_initialization/README.md).

## Repository assessment verification (SV.4)

Verify a clean non-editable CLI can initialize and assess a repository
(deterministic `--no-ai`, telemetry off / no transmission, structural artifact checks):

```bash
cd engine
python -m verification.repository_assessment --local-only
```

Canonical customer command:

```bash
codestrata assess --repo . --no-ai --no-ai
```

Optional process-local telemetry consent (not saved; no transmission in this
release):

```bash
codestrata assess --repo . --no-ai --no-ai --telemetry-deny
codestrata assess --repo . --no-ai --no-ai --telemetry-allow
```

See [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md).

Catalog-backed remote runs require a `qualified_revision` (full commit SHA) in
`validation/repository-catalog/catalog.json`. Validate pins with:

```bash
python validation/repository-catalog/validate_catalog.py --write-report
cd engine
python -m verification.repository_assessment --with-catalog-network
```

See [`../verification/repository_assessment/README.md`](../verification/repository_assessment/README.md).

## Assessment report verification (SV.5)

Verify assessment artifact quality after SV.4 (schema 1.2, parity, HTML structure,
traceability, credibility, privacy, determinism):

```bash
cd engine
python -m verification.assessment_report --local-only
# catalog-backed CleanArchitecture (policy-selected):
python -m verification.assessment_report --with-catalog-network
```

See [`../verification/assessment_report/README.md`](../verification/assessment_report/README.md).
Does not start CLI UX verification (SV.6).

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
