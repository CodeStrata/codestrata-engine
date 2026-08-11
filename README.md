# CodeStrata Engine (Community Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Edition: Community](https://img.shields.io/badge/edition-Community-brightgreen.svg)](https://docs.codestrata.ai/community/vs-platform)
[![Install CodeStrata for VS Code](https://img.shields.io/badge/Install-CodeStrata%20for%20VS%20Code-007ACC?logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment)

> The Engine produces structured Engineering Assessments (single repository)
> and can contribute to portfolio Engineering Intelligence Reports (EIR).

Open-source CLI that assesses a software repository and produces deterministic
findings, recommendations, and a self-contained HTML/JSON **Engineering
Assessment** report.

**Audience:** engineers and engineering leaders evaluating a codebase for
modernization, due diligence, or portfolio discovery.

## Documentation

| Need | Where |
| ---- | ----- |
| Install, first assessment, reports, extensions | [Public docs](https://docs.codestrata.ai/getting-started/) |
| Community Cloud architecture | [Community Cloud](https://docs.codestrata.ai/architecture/community-cloud) |
| Data Lake / Insights | [Data Lake](https://docs.codestrata.ai/architecture/data-lake) · [Insights](https://docs.codestrata.ai/architecture/insights) |
| Community API / Source Locality | [Community Cloud API](https://docs.codestrata.ai/reference/community-api/) · [Source Locality](https://docs.codestrata.ai/security/source-locality) |
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
| **codestrata-engine** (this repo) | Assessment CLI, reports, Engine docs | Yes — Community source |
| **codestrata-examples** | Pinned real-world showcase manifests + fetch scripts | Yes — Community source |
| **CodeStrata Platform** | Knowledge Graph, Retrieval, Answering, Portfolio / Executive Intelligence | Private implementation |
| **VS Code extension** | Editor integration | [Public Marketplace](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment) (`CodeStrataAI.codestrata-assessment`); source private |

Product statement: *The Engine produces structured engineering intelligence.
The Platform stores, connects, retrieves, and reasons over that intelligence.*

---

## Quick start

Community users can use CodeStrata through the **CLI** or **VS Code**.

### CLI

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
codestrata assess --repo test-fixtures/sample-js-app --no-ai
```

Optional MCP server support (not required for Quick Start):

```bash
python -m pip install -e '.[mcp]'
```

If you see `ModuleNotFoundError: codestrata`, confirm the active interpreter:

```bash
python -c "import codestrata; print(codestrata.__file__)"
```

Open the current assessment HTML under:

```text
.codestrata-artifacts/assessments/<repository-id>/current/assessment.html
```

### VS Code

[![Install CodeStrata for VS Code](https://img.shields.io/badge/Install-CodeStrata%20for%20VS%20Code-007ACC?logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment)

Install **[CodeStrata for VS Code](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment)**
from Visual Studio Marketplace (`CodeStrataAI.codestrata-assessment`).
The extension is publicly distributed there; extension source remains private.
It is a thin client of the Engine CLI — keep the CLI installed and discoverable
(commands above).

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
  --profile community \
  --no-ai
```

Assess your own tree:

```bash
codestrata assess --repo /path/to/your-app --no-ai
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
codestrata assess --config codestrata.toml --no-ai
```

**GitHub repository:**

```toml
# codestrata.toml
[repository]
url = "https://github.com/YOUR_ORG/YOUR_REPO"
branch = "main"
```

```bash
codestrata assess --config codestrata.toml --no-ai
```

**Execution profile** (optional): `--profile local` — see
[docs/configuration-profiles.md](docs/configuration-profiles.md).

**Optional AI narrative** (Bedrock live-proven; OpenAI/OpenRouter require owner
credentials — see public AI Providers docs):

```bash
codestrata assess --config codestrata.toml --with-ai
```

**Optional Community telemetry** (disabled by default; process-local only):

```bash
codestrata assess --repo . --no-ai --telemetry-allow
codestrata assess --repo . --no-ai --telemetry-deny
```

**Explicit public report publish** (never automatic; not the same as telemetry):

```bash
codestrata report publish --type assessment --confirm-public-publish
# → https://reports.codestrata.ai/r/<opaque-id>
```

**Real-world showcases** (separate public repo):
[codestrata-examples](https://github.com/CodeStrata/codestrata-examples).

---

## Output artifacts

```text
.codestrata-artifacts/
  assessments/<repository-id>/
    current/
      assessment.html
      assessment.json
      heads/                 # eight modular assessment head JSON files
                             # (architecture, security, technical-debt, cloud,
                             #  ai, dependencies, testing, performance)
    previous/                # prior slot when replaced
  intelligence/<portfolio-id>/
    current/
    previous/
```

How to read reports: [docs/report-interpretation.md](docs/report-interpretation.md).
Canonical public docs: https://docs.codestrata.ai/reference/cli

---

## Supported technologies

| Area | Support |
| ---- | ------- |
| Languages | Java, JavaScript/TypeScript, Python, PHP, C# / .NET |
| Build / deps | Maven, npm, Composer, NuGet / MSBuild |
| CI | GitHub Actions discovery |
| Static analysis | Optional PMD (Java) |
| AI enrichment | Optional (Bedrock live-proven; OpenAI/OpenRouter owner credentials) |
| Sources | Local filesystem, GitHub HTTPS/SSH |

This package ships `test-fixtures/sample-js-app` for offline smoke tests.

---

## Documentation

| Doc | Topic |
| --- | ----- |
| [docs/README.md](docs/README.md) | Docs index |
| [docs/community-edition.md](docs/community-edition.md) | Community scope |
| [docs/cli-reference.md](docs/cli-reference.md) | CLI reference |
| [docs/telemetry-runtime.md](docs/telemetry-runtime.md) | Telemetry runtime (disabled by default; no transmission) |
| [docs/telemetry-disabled-default.md](docs/telemetry-disabled-default.md) | Slice 9.2 disabled-default enforcement |
| [docs/telemetry-session-consent.md](docs/telemetry-session-consent.md) | Slice 9.3 per-session consent (process-local) |
| [docs/telemetry-interactive-consent.md](docs/telemetry-interactive-consent.md) | Slice 9.4 interactive consent prompt |
| [docs/telemetry-non-interactive.md](docs/telemetry-non-interactive.md) | Slice 9.5 non-interactive prompt suppression |
| [docs/telemetry-cli-consent-flags.md](docs/telemetry-cli-consent-flags.md) | Slice 9.6 assess `--telemetry-allow` / `--telemetry-deny` |
| [docs/telemetry-status.md](docs/telemetry-status.md) | Slice 9.7 privacy-first telemetry status |
| [docs/telemetry-transport.md](docs/telemetry-transport.md) | Slice 9.11 fail-silent HTTP transport (explicit) |
| [docs/telemetry-assessment-isolation.md](docs/telemetry-assessment-isolation.md) | Slice 9.12 assessment isolation |
| [../verification/privacy_first_telemetry/README.md](../verification/privacy_first_telemetry/README.md) | Slice 9.14 cross-client privacy verification |
| [../verification/privacy_first_telemetry_completion/README.md](../verification/privacy_first_telemetry_completion/README.md) | Slice 9.15 Epic 9 completion (v0.2.0) |
| [docs/telemetry-anonymous-analytics.md](docs/telemetry-anonymous-analytics.md) | Slice 10.1 anonymous analytics contract (no collection) |
| [docs/telemetry-installation-identity.md](docs/telemetry-installation-identity.md) | Slice 10.2 anonymous installation identity (local only) |
| [docs/telemetry-runtime-analytics.md](docs/telemetry-runtime-analytics.md) | Slice 10.3 runtime analytics (local construction only) |
| [docs/telemetry-assessment-analytics.md](docs/telemetry-assessment-analytics.md) | Slice 10.4 assessment analytics (construction API only) |
| [docs/telemetry-repository-aggregate-analytics.md](docs/telemetry-repository-aggregate-analytics.md) | Slice 10.5 repository aggregate analytics (construction API only) |
| [docs/telemetry-ai-analytics.md](docs/telemetry-ai-analytics.md) | Slice 10.6 AI analytics (construction API only) |
| [VS Code extension docs](https://docs.codestrata.ai/extensions/vscode) | VS Code extension ([Marketplace](https://marketplace.visualstudio.com/items?itemName=CodeStrataAI.codestrata-assessment); source private) |
| [../verification/anonymous_analytics_privacy/README.md](../verification/anonymous_analytics_privacy/README.md) | Slice 10.8 anonymous analytics privacy verification |
| [../verification/anonymous_analytics_completion/README.md](../verification/anonymous_analytics_completion/README.md) | Slice 10.9 Epic 10 completion verification (contracts-only; not operational) |
| [docs/ai-enrichment.md](docs/ai-enrichment.md) | AI providers / Modernization Advisor enrichment |
| [verification/ai_provider_baseline/README.md](verification/ai_provider_baseline/README.md) | Slice 11.1 existing AI provider compatibility baseline (characterization only) |
| [docs/ai-provider-contracts.md](docs/ai-provider-contracts.md) | Slice 11.2 Common AI Provider Contracts (new, unwired) |
| [docs/ai-provider-configuration.md](docs/ai-provider-configuration.md) | Slice 11.3 Standardized Provider and Model Configuration (new, unwired) |
| [docs/ai-provider-execution.md](docs/ai-provider-execution.md) | Slice 11.4 Standardized Execution, Errors, Timeouts, and Retries (new, unwired) |
| [docs/ai-provider-capabilities.md](docs/ai-provider-capabilities.md) | Slice 11.5 Provider Usage Metadata and Capability Discovery (new, unwired) |
| [docs/ai-provider-openai.md](docs/ai-provider-openai.md) | Slice 11.6 OpenAI Provider Migration (wired) |
| [docs/ai-provider-bedrock.md](docs/ai-provider-bedrock.md) | Slice 11.7 AWS Bedrock Provider Migration (wired; default provider) |
| [docs/ai-provider-platform.md](docs/ai-provider-platform.md) | Slice 11.8 Cross-Provider Contract Verification (Decision B) |
| [docs/ai-provider-openrouter.md](docs/ai-provider-openrouter.md) | Slice 11.9 OpenRouter adapter |
| [docs/ai-provider-openrouter-configuration.md](docs/ai-provider-openrouter-configuration.md) | Slice 11.10 OpenRouter configuration/authentication (explicit) |
| [docs/ai-provider-openrouter-doctor.md](docs/ai-provider-openrouter-doctor.md) | Slice 11.11 OpenRouter doctor local readiness + mocked integration |
| [docs/ai-provider-security-boundaries.md](docs/ai-provider-security-boundaries.md) | Slice 11.12 provider privacy, failure-isolation, and architecture boundaries |
| [verification/ai_provider_platform_completion/README.md](verification/ai_provider_platform_completion/README.md) | Slice 11.13 Epic 11 completion verification (Epic 11 complete; Epic 12 not started) |
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
