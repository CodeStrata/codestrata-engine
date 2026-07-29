# Extension Architecture

<!-- documentation-visibility: public-contributor -->

**Audience:** Engine contributors and extension authors.  
**Scope:** Community Edition extension contracts — not a plugin marketplace.

## Philosophy

* Engine remains the single source of truth for findings, recommendations, and reports.
* Deterministic analysis does not require extensions or Platform.
* Extensions are **contracts + entry points + explicit allowlists** — not a plugin framework.
* Installing a Python package is the trust boundary (same process as the CLI).

Extension API version: defined as `EXTENSION_API_VERSION` in
`codestrata.extensions.version` (currently **1.0.0**). Major mismatches are rejected.

## Entry-point groups

| Group | Purpose | Default |
| ----- | ------- | ------- |
| `codestrata.cli_extensions` | Typer registrar `(app) -> None` | Soft-discover |
| `codestrata.mcp_extensions` | MCP registrar | Soft-discover |
| `codestrata.ai_provider_extensions` | Optional AI embed/answer factories | Soft-discover |
| `codestrata.assess_ai_provider_extensions` | Extra assess AI providers | Optional |
| `codestrata.analyzer_extensions` | Analyzer contributions | **Opt-in allowlist** |
| `codestrata.report_renderer_extensions` | `CustomerReportDocument` renderers | Optional |
| `codestrata.acceptance_extensions` | Acceptance helpers | Soft-discover |

Soft-discover means entry points load when present on `PYTHONPATH`. Community
Engine never imports Platform packages; optional integrators may register via
entry points only. Unpublished commercial capabilities are out of scope for this
document.

## Contracts

* **AnalyzerExtension** — `id`, `api_version`, `create() -> Analyzer`
* **AssessAIProviderExtension** — `id`, `api_version`, `create(settings) -> AIModelProvider`
* **ReportRenderer** — `id`, `media_type`, `api_version`, `render(document, destination) -> Path`

Built-in assess providers: `bedrock`, `openai` (registry-backed; behavior unchanged).  
Built-in report renderer: `html` (`HtmlCustomerReportRenderer`).

## Configuration

```toml
[extensions]
api_version = "1"

[extensions.analyzers]
# Empty = built-ins only (Community default)
enabled = []
# enabled = ["com.example.license_scan"]

[extensions.renderers]
enabled = []

[extensions.cli]
disabled = []

[extensions.mcp]
disabled = []
```

## Reserved namespaces

Third-party analyzer IDs must **not** use:

* `codestrata.`
* `com.codestrata.`
* `org.codestrata.`
* `io.codestrata.`

Reserved assess AI ids: `bedrock`, `openai`.  
Reserved renderer ids: `html`, `json`.  
Reserved CLI verbs: `assess`, `init`, `doctor`, `version`, `scan`, `extensions`, …

## CLI

```bash
codestrata extensions list
codestrata extensions list --json
codestrata doctor --extensions
codestrata version   # includes Extension API
```

## Compatibility

* Additive Protocol changes within a major are preferred.
* Breaking contract changes bump `EXTENSION_API_VERSION` major.
* Community Edition never imports Platform packages.

## Security

Entry points execute as the CLI user. Only enable analyzer IDs from packages you trust.
See [security/threat-model.md](security/threat-model.md).

## Out of scope (intentionally)

Rule/section plugins, process sandboxes, remote marketplaces, IDE plugins.
