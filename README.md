# CodeStrata Engine (Community Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Edition: Community](https://img.shields.io/badge/edition-Community-brightgreen.svg)](https://docs.codestrata.ai/community/vs-platform)

> The Engine produces structured engineering intelligence.

Open-source CLI that assesses a software repository and produces deterministic
findings, recommendations, and a self-contained HTML/JSON **Engineering
Assessment** report.

**Audience:** engineers and engineering leaders evaluating a codebase for
modernization, due diligence, or portfolio discovery.

## Documentation

| Need | Where |
| ---- | ----- |
| Install, first assessment, reports, extensions | [Public docs](https://docs.codestrata.ai/getting-started/) |
| Community vs Platform | [Community vs Platform](https://docs.codestrata.ai/community/vs-platform) |
| Engine contracts and contributor docs | [docs/README.md](docs/README.md) in this repository |

---

## Why CodeStrata Engine?

| You need | Community Engine delivers |
| -------- | ------------------------- |
| A fast read on stack, risks, and next steps | Local or GitHub `codestrata assess` |
| Evidence you can trust | Deterministic rules (AI optional, never invents findings) |
| Something you can share | Self-contained HTML + JSON assessment artifacts |
| Automation | CLI, optional MCP, optional Agent Framework |

**Not in Community Engine:** hosted SaaS, SSO/billing, multi-tenant control planes,
or CodeStrata Platform capabilities (Engineering Knowledge Graph, Repository
Retrieval / Answering, Portfolio Intelligence, Executive Intelligence, Strategic
Roadmap). Details:
[Community vs Platform](https://docs.codestrata.ai/community/vs-platform).

---

## How CodeStrata fits together

| Product | Role | Public? |
| ------- | ---- | ------- |
| **codestrata-engine** (this repo) | Assessment CLI, reports, Engine docs | Yes |
| **codestrata-examples** | Pinned real-world showcase manifests + fetch scripts | Yes |
| **CodeStrata Platform** | Knowledge Graph, Retrieval, Answering, Portfolio / Executive Intelligence | Commercial product |
| **VS Code / Cursor extensions** | Editor integrations | Community packages |

Product statement: *The Engine produces structured engineering intelligence.
The Platform stores, connects, retrieves, and reasons over that intelligence.*

---

## Quick start

Requires **Python 3.12+**. Guides:
[docs/quick-start.md](docs/quick-start.md) ·
[docs/installation.md](docs/installation.md).

```bash
git clone https://github.com/CodeStrata/codestrata-engine.git
cd codestrata-engine

python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
codestrata version
codestrata init
codestrata doctor
codestrata assess --repo test-fixtures/sample-js-app --output reports --no-ai
```

Optional MCP server support (not required for Quick Start):

```bash
python -m pip install -e '.[mcp]'
```

If you see `ModuleNotFoundError: codestrata`, confirm the active interpreter:

```bash
python -c "import codestrata; print(codestrata.__file__)"
```

Open the newest `reports/sample-js-app/<timestamp>/report.html`.

### Real-world showcases

Install Engine first (commands above), then:

```bash
git clone https://github.com/CodeStrata/codestrata-examples.git
cd codestrata-examples
python real-world/scripts/run_showcase.py spring-petclinic
```

Or fetch + assess separately (this repository ships `codestrata.toml`):

```bash
python real-world/scripts/fetch_example.py spring-petclinic
codestrata assess \
  --repo .codestrata-examples/spring-petclinic \
  --output reports/showcases/spring-petclinic \
  --profile community \
  --no-ai
```

Assess your own tree:

```bash
codestrata assess --repo /path/to/your-app --output reports --no-ai
```

Guides: [docs/getting-started.md](docs/getting-started.md) ·
[docs/installation.md](docs/installation.md) ·
[docs/tutorial.md](docs/tutorial.md) ·
[docs/community-vs-platform.md](docs/community-vs-platform.md).

## What an assessment does

```text
codestrata.toml / CLI
        │
        ▼
Local path or GitHub clone
        │
        ▼
Detect technologies + extract facts
        │
        ▼
Repository graph → assessment graph
        │
        ▼
Deterministic rules → findings → recommendations
        │
        ├──────────────────┐
        ▼                  ▼
HTML + JSON reports   optional AI narrative (one provider call)
```

Default mode is **deterministic** (`--no-ai`: zero provider calls). Optional
`--with-ai` adds narrative only; it never rewrites findings or recommendations.

---

## Example workflows

**Config-driven assess** (default `codestrata.toml` points at the bundled JS sample):

```bash
codestrata config validate --config codestrata.toml
codestrata assess --config codestrata.toml --output reports --no-ai
```

**GitHub repository:**

```toml
# codestrata.toml
[repository]
url = "https://github.com/YOUR_ORG/YOUR_REPO"
branch = "main"
```

```bash
codestrata assess --config codestrata.toml --output reports --no-ai
```

**Execution profile** (optional): `--profile local` — see
[docs/configuration-profiles.md](docs/configuration-profiles.md).

**Optional AI narrative** (Bedrock or OpenAI; never rewrites findings):

```bash
codestrata assess --config codestrata.toml --output reports --with-ai
```

**Real-world showcases** (separate public repo):
[codestrata-examples](https://github.com/CodeStrata/codestrata-examples).

---

## Output artifacts

```text
reports/<repository-name>/<YYYYMMDD-HHMMSS>/
├── report.html
├── report.json
├── findings.json
├── recommendations.json
├── advisor.json      # only with successful --with-ai
└── graphs/
```

How to read reports: [docs/report-interpretation.md](docs/report-interpretation.md).

---

## Supported technologies

| Area | Support |
| ---- | ------- |
| Languages | Java, JavaScript/TypeScript, Python, PHP, C# / .NET |
| Build / deps | Maven, npm, Composer, NuGet / MSBuild |
| CI | GitHub Actions discovery |
| Static analysis | Optional PMD (Java) |
| AI enrichment | Optional Amazon Bedrock or OpenAI |
| Sources | Local filesystem, GitHub HTTPS/SSH |

This package ships `test-fixtures/sample-js-app` for offline smoke tests.

---

## Documentation

| Doc | Topic |
| --- | ----- |
| [docs/README.md](docs/README.md) | Docs index |
| [docs/community-edition.md](docs/community-edition.md) | Community scope |
| [docs/cli-reference.md](docs/cli-reference.md) | CLI reference |
| [docs/architecture-guide.md](docs/architecture-guide.md) | Architecture map |
| [docs/mcp/setup.md](docs/mcp/setup.md) | MCP setup |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Troubleshooting |
| [SUPPORT.md](SUPPORT.md) | How to get help |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/contributor-guide.md](docs/contributor-guide.md).

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Satish Nampally — https://github.com/sknampally
