# Changelog

All notable changes to CodeStrata Engine (Community Edition) are documented in
this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-11

### Added

* Deterministic multi-head Engineering Assessment with Assessment Overview
* Community report publishing with opaque public report URLs
* Privacy-first telemetry consent (default deny; opt-in is not publish authorization)
* Community Cloud client flows for published reports
* Provider platform: AWS Bedrock live E2E validated; OpenAI/OpenRouter supported
  with qualification (owner live E2E not completed)

### Changed

* Engine package version aligned to the v0.2.0 Community cut
* Community public source is this Engine repository plus `codestrata-examples`.
  The VS Code extension is Marketplace distribution (source private). Platform
  and infrastructure remain private.

### Notes

* This changelog describes the v0.2.0 cut. Publication (PyPI, GitHub Release,
  Marketplace) is a separate step and is not implied by this file.

## [0.1.0] - 2026-07-22

### Added

* CLI (`codestrata version`, `codestrata scan`, `codestrata assess`) with local
  and GitHub sources
* Analysis: detection, analyzers, optional PMD static analysis
* Repository Inventory, Repository Graph, and Assessment Graph
* Deterministic Rule Engine → `findings.json`
* Deterministic Recommendation Engine → `recommendations.json`
* Optional one-call Bedrock AI enrichment → `advisor.json`
* HTML Report (`report.html`) and companion `report.json`
* Deterministic mode (zero AI calls) and AI mode (exactly one call)
* Multi-language detection and evidence: Java, JavaScript/TypeScript, Python,
  PHP, C#/.NET
* Local knowledge store, optional MCP server extra, and Agent Framework
* Execution profiles (`community`, `local`, `enterprise`, `bedrock`, `openai`)
* Open-source documentation, examples, and community files

### Notes

* Deterministic findings and recommendations are the source of truth.
* AI enrichment is interpretive only and does not mutate deterministic artifacts.
* Community defaults include repository assessment, local graphs, deterministic
  rules, and HTML/JSON reports. Organizational Knowledge Graph features and
  Platform services (SSO, billing, multi-tenancy) are not Community defaults.
* This release uses the **CodeStrata** package and CLI exclusively.
* Known limitations: alpha software status; many analysis packs are
  feature-gated and off by default; broader executive report methodology may be
  ahead of runtime presentation.
