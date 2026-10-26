# Changelog

All notable changes to CodeStrata Engine (Community Edition) are documented in
this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-10-22

### Changed

* Package version in this tree is **0.3.1**. It is not a PyPI release. Public
  installs remain `pip install 'codestrata==0.3.0'`.
* `knowledge.max_json_bytes` configures the file knowledge-store JSON document
  bound. The local default stays **16 MiB** (`16777216`). Hosted worker
  configuration sets **32 MiB** (`33554432`) and does not change the local
  default. The hosted completion persistence cap is a separate **32 MiB** limit.
* Generated HTML reports embed the current website SVG favicon
  (`sha256 cd5eac6e9a8ff66d77b61e8523ee1d280c56d63082a4909902685b72471e008a`)
  as `data:image/svg+xml`. The 0.2.1 favicon was a PNG data URI. Report schema
  remains **1.2**.

### Notes

* Hosted workers consume unpublished wheel
  `ab10df61c5bb3124dcce742f9465bb8acba4702be9d9704a5bd3a6b1c5c427fb`
  built from source commit `51cf17da03076658a6e92038c784ad56b24f8ca0`.
  That wheel is not the public GitHub Release. The latest GitHub Release
  remains **v0.2.1**, and public `codestrata-engine` `main` remains **0.3.0**.
* Hosted Try stays limited to the qualification recipient while public opening
  is disabled.
* The **0.3.0** section below keeps the publication status written for that
  cut. PyPI later received **0.3.0**. This **0.3.1** section does not rewrite
  that cut.

## [0.3.0] - 2026-10-08

### Changed

* Engine / CLI package version **0.3.0**. Ruleset schema remains **1.2.0**.
* The effective-ruleset engine digest constant remains **0.2.1**. It is a
  pinned rule-catalog identity for candidate `engine_digest` and is not an
  input to admitted Effective RuleSet seals. Runtime package identity is
  **0.3.0**. New change-cache keys record that runtime version.

### Notes

* This cut is selected and not published. PyPI `0.2.1` stays the rollback identity.
* Local AI remains optional. Hosted baseline trials are a later workflow.
* The 22-repository SV.10 corpus is not in this checkout. That full SV.11 run
  is not recorded as PASS.
* Publication (PyPI, GitHub Release, container registry, Marketplace, docs site)
  is a separate step and is not implied here.

## [0.2.1] - 2026-08-14

### Added

* Consent v2: durable Engine-owned Yes/No for lifecycle telemetry and privacy-safe
  assessment intelligence (`assessment_metadata`), with decline-upgrade and disable
* Privacy-safe assessment intelligence emission (schema 1.0 / 1.1) gated on v2 consent
* Favicon embedded in generated public HTML reports (presentation-only)

### Fixed

* Public report Yes/No feedback acknowledgement under published CSP (nonce +
  `connect-src 'self'`); local offline CSP remains `script-src`/`connect-src` none

### Changed

* Engine / CLI package version **0.2.1** (Community patch on the accepted
  `e818ae6f` release candidate)

### Notes

* Does **not** collect graph telemetry, numeric assessment scores, source uploads,
  or repository identity in report feedback
* Patch validation: five representative frozen repos matched baselines exactly;
  full 22-repo corpus rerun not required
* Publication (PyPI / GitHub Release) is a separate step and is not implied here

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
