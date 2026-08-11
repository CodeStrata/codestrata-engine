# CLI reference

> **Canonical public overview:** [CLI](https://docs.codestrata.ai/reference/cli)

Public journey commands are documented in the docs portal. This file is the
**Engine CLI reference** for Community Edition users and contributors (flags,
behaviors, contracts).

Primary commands for CodeStrata. Run `codestrata COMMAND --help` for full
options. Global: `codestrata --help`, `codestrata version`, `codestrata about`.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | Success |
| `1` | Blocked / validation failure / expected operational failure |
| `2` | Usage error or unexpected error (command-specific; agent/enterprise/incremental use `2` for hard errors) |

Config and assess usage mistakes (for example `--model-id` without `--with-ai`)
exit `2`. Missing config files and most load failures exit `1` with a `Fix:`
hint.

## Core workflow

| Command | Purpose |
| ------- | ------- |
| `codestrata assess` | Full modernization assessment → HTML/JSON reports |
| `codestrata scan` | Clone + analyze the GitHub URL in `codestrata.toml` |
| `codestrata onboard` | Onboard a repository into the knowledge store |
| `codestrata config profile` | Show active execution profile |
| `codestrata config validate` | Validate configuration / profile compatibility |
| `codestrata config effective` | Show effective non-secret settings |
| `codestrata config show` | Alias for `effective` |
| `codestrata telemetry status` | Privacy-first telemetry posture (disabled by default; no side effects) |
| `codestrata telemetry preview` | Illustrative privacy-safe runtime event (local only; no transmission) |
| `codestrata telemetry enable` | Explicit opt-in for anonymous telemetry |
| `codestrata telemetry disable` | Disable anonymous telemetry |
| `codestrata telemetry reset` | Reset installation id + preferences |
| `codestrata telemetry show` | Print sample legacy telemetry payload (no transmit) |

### Assess (canonical)

```bash
codestrata assess --config codestrata.toml --no-ai
codestrata assess --repo test-fixtures/sample-js-app --no-ai --no-ai
codestrata assess --config codestrata.toml --profile local --no-ai
codestrata assess --config codestrata.toml --no-ai --with-ai
```

Important options:

* `--repo` / `-r` — local path or GitHub URL (overrides config)
* `--output` / `-o` — report root directory (default `reports`)
* `--with-ai` / `--no-ai` — AI enrichment (default `--no-ai`)
* `--profile` / `-p` — execution profile override
* `--config` / `-c` — path to `codestrata.toml`
* `--model-id` — Bedrock model (requires `--with-ai`)

### Config

```bash
codestrata config profile --config codestrata.toml
codestrata config validate --config codestrata.toml --profile bedrock
codestrata config effective --config codestrata.toml
```

See [configuration-profiles.md](configuration-profiles.md).

## Knowledge and MCP

| Command | Purpose |
| ------- | ------- |
| `codestrata repository search` | Grounded retrieval |
| `codestrata repository answer` | Grounded answering |
| `codestrata mcp serve` | Start FastMCP server |
| `codestrata mcp tools` | List tools |
| `codestrata mcp health` | Sanitized health (no secrets) |

Requires `[mcp].enabled = true` and usually `pip install 'codestrata[mcp]'`.
Guide: [mcp/setup.md](mcp/setup.md).

## AI providers

| Command | Purpose |
| ------- | ------- |
| `codestrata ai` | Community: supported assess providers, Configured / Not Configured, required env vars |
| `codestrata ai doctor` | Community: validate Bedrock / OpenAI / OpenRouter setup without assessing (local readiness only; no secrets; no provider calls) |

Portal guide: [AI Providers](https://docs.codestrata.ai/ai-providers/).

When CodeStrata Platform is installed separately, additional RAG provider
helpers may appear. Community `codestrata ai` remains the assess discovery
surface for Bedrock / OpenAI enrichment.

## Analysis intelligence helpers

| Command group | Purpose |
| ------------- | ------- |
| `codestrata rules` | Shared Rule Platform discovery |
| `codestrata evidence` | Language evidence providers |
| `codestrata architecture` | Architecture conclusions / assessment / report helpers |
| `codestrata report validate` | Validate report contract JSON |

## Optional analysis packs

Architecture, cloud, performance, AI readiness, and related packs are **opt-in**
and default **disabled**. Evidence, rules, analysis, and report gates are
independent: enabling rules does not collect evidence or write an assessment
section; enabling a report section does not run analysis.

Common pattern (Cloud shown; AI readiness and performance use the same shape
with `ai_readiness` / `performance` keys):

```toml
[analysis.cloud]
enabled = false
# include_synthesis = true

[evidence.repository_cloud]
enabled = false

[rules]
enabled = false

[rules.cloud]
enabled = false

[report.sections.cloud]
enabled = false
```

AI readiness uses `[analysis.ai_readiness]`,
`[evidence.repository_ai_readiness]`, `[rules.ai_readiness]`, and
`[report.sections.ai_readiness]`.

Performance uses `[analysis.performance]`,
`[evidence.repository_performance]`, `[rules.performance]`, and
`[report.sections.performance]`.

When analysis is enabled and the pack is on, assessment JSON is written with
inventories and (unless `include_synthesis = false`) deterministic synthesis.
Existing configs without these keys remain valid. Shared rule defaults:
[analysis-intelligence/shared-rule-platform.md](analysis-intelligence/shared-rule-platform.md).

## Other command groups

| Command group | Purpose |
| ------------- | ------- |
| `codestrata agent` | Agent Framework workflows |
| `codestrata incremental` | Incremental assessment (opt-in) |
| `codestrata enterprise` | Enterprise Knowledge Graph (not a Community default) |
| `codestrata roadmap` | Modernization roadmap helpers |
| `codestrata release` | Release readiness helpers |

## First-run tips

1. Prefer `codestrata assess --repo …` before editing a large `codestrata.toml`.
2. Run `codestrata config validate` after changing profiles or AI providers.
3. Keep secrets in the environment (`.env`), never in TOML values.
4. When a command fails, read the `Fix:` line in the error message.

Troubleshooting: [troubleshooting.md](troubleshooting.md).
