# CodeStrata Engine documentation

<!-- documentation-visibility: public-contributor -->

**Audience:** Community users and contributors working on CodeStrata Engine.

**Product journeys** (install, first assessment, reports, extensions, Community
vs Platform) are canonical in the public portal:

- [https://docs.codestrata.ai](https://docs.codestrata.ai)

```text
Public journeys  →  docs.codestrata.ai
Engine contracts →  docs/ in this repository
```

Prefer linking the portal for end-user tutorials. Keep Engine `docs/` focused on
CLI contracts, architecture, MCP, security, and contributor guidance.

## Getting started

| Topic | Document |
| ----- | -------- |
| Getting Started | [getting-started.md](getting-started.md) |
| Installation | [installation.md](installation.md) |
| Quick Start | [quick-start.md](quick-start.md) |
| First assessment | [tutorial.md](tutorial.md) |
| Reports | [report-interpretation.md](report-interpretation.md) |
| AI enrichment | [ai-enrichment.md](ai-enrichment.md) |
| AI provider contracts (Slice 11.2, unwired) | [ai-provider-contracts.md](ai-provider-contracts.md) |
| AI provider configuration (Slice 11.3, unwired) | [ai-provider-configuration.md](ai-provider-configuration.md) |
| AI provider execution (Slice 11.4, unwired) | [ai-provider-execution.md](ai-provider-execution.md) |
| AI provider capabilities (Slice 11.5, unwired) | [ai-provider-capabilities.md](ai-provider-capabilities.md) |
| OpenAI provider migration (Slice 11.6, wired) | [ai-provider-openai.md](ai-provider-openai.md) |
| Bedrock provider migration (Slice 11.7, wired) | [ai-provider-bedrock.md](ai-provider-bedrock.md) |
| AI provider platform / Decision B (Slice 11.8) | [ai-provider-platform.md](ai-provider-platform.md) |
| OpenRouter adapter (Slice 11.9) | [ai-provider-openrouter.md](ai-provider-openrouter.md) |
| OpenRouter configuration/auth (Slice 11.10) | [ai-provider-openrouter-configuration.md](ai-provider-openrouter-configuration.md) |
| OpenRouter doctor / mocked integration (Slice 11.11) | [ai-provider-openrouter-doctor.md](ai-provider-openrouter-doctor.md) |
| AI provider security/privacy boundaries (Slice 11.12) | [ai-provider-security-boundaries.md](ai-provider-security-boundaries.md) |
| AI provider platform completion (Slice 11.13; Epic 11 complete) | [ai-provider-platform.md](ai-provider-platform.md) |
| CLI reference | [cli-reference.md](cli-reference.md) |
| Telemetry (opt-in, legacy) | [telemetry.md](telemetry.md) |
| Telemetry runtime (Slice 9.1) | [telemetry-runtime.md](telemetry-runtime.md) |
| Telemetry disabled-default (Slice 9.2) | [telemetry-disabled-default.md](telemetry-disabled-default.md) |
| Telemetry session consent (Slice 9.3) | [telemetry-session-consent.md](telemetry-session-consent.md) |
| Telemetry interactive consent (Slice 9.4) | [telemetry-interactive-consent.md](telemetry-interactive-consent.md) |
| Telemetry non-interactive (Slice 9.5) | [telemetry-non-interactive.md](telemetry-non-interactive.md) |
| Telemetry CLI consent flags (Slice 9.6) | [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md) |
| Telemetry status (Slice 9.7) | [telemetry-status.md](telemetry-status.md) |
| Telemetry event catalog (Slice 9.8) | [telemetry-event-catalog.md](telemetry-event-catalog.md) / [JSON](telemetry-event-catalog.json) |
| Telemetry preview (Slice 9.9) | [telemetry-preview.md](telemetry-preview.md) |
| Pre-transport privacy (Slice 9.10) | [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md) |
| Telemetry transport (Slice 9.11) | [telemetry-transport.md](telemetry-transport.md) |
| Assessment telemetry isolation (Slice 9.12) | [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md) |
| Anonymous analytics contract (Slice 10.1) | [telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md) |
| Anonymous installation identity (Slice 10.2) | [telemetry-installation-identity.md](telemetry-installation-identity.md) |
| Runtime analytics (Slice 10.3) | [telemetry-runtime-analytics.md](telemetry-runtime-analytics.md) |
| Assessment analytics (Slice 10.4) | [telemetry-assessment-analytics.md](telemetry-assessment-analytics.md) |
| Repository aggregate analytics (Slice 10.5) | [telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md) |
| AI analytics (Slice 10.6) | [telemetry-ai-analytics.md](telemetry-ai-analytics.md) |
| Privacy | [../PRIVACY.md](../PRIVACY.md) |
| Examples | [examples.md](examples.md) |
| Community vs Platform | [community-vs-platform.md](community-vs-platform.md) |
| Troubleshooting | [troubleshooting.md](troubleshooting.md) |

## Technical reference

| Document | Description |
| -------- | ----------- |
| [configuration-profiles.md](configuration-profiles.md) | Execution profiles and configuration |
| [public-contracts.md](public-contracts.md) | Community SDK/CLI contracts |
| [report-contract.md](report-contract.md) | Report schema contract |
| [report-generation.md](report-generation.md) | HTML/JSON generation |
| [runtime.md](runtime.md) | Assess runtime and performance controls |
| [architecture-guide.md](architecture-guide.md) | Architecture overview |
| [rule-engine.md](rule-engine.md) | Deterministic rule engine |
| [analysis-intelligence/shared-rule-platform.md](analysis-intelligence/shared-rule-platform.md) | Shared Rule Platform |
| [analysis-intelligence/rule-authoring.md](analysis-intelligence/rule-authoring.md) | Shared rule authoring |
| [analysis-intelligence/security-context-classification.md](analysis-intelligence/security-context-classification.md) | Security context classification (precision) |
| [analysis-intelligence/recommendation-prioritization-calibration.md](analysis-intelligence/recommendation-prioritization-calibration.md) | Recommendation prioritization calibration |
| [analysis-intelligence/recommendation-confidence.md](analysis-intelligence/recommendation-confidence.md) | Recommendation Confidence |
| [analysis-intelligence/finding-severity-calibration.md](analysis-intelligence/finding-severity-calibration.md) | Finding severity calibration |
| [mcp/README.md](mcp/README.md) | MCP technical reference |
| [apis.md](apis.md) | Integration surfaces |
| [security/](security/) | Threat model and hardening |
| [extension-architecture.md](extension-architecture.md) | Extension API |
| [contributor-guide.md](contributor-guide.md) | Contributor guide |
| [CHANGELOG.md](../CHANGELOG.md) | Changelog / release notes |

## Related entry points

- [README.md](../README.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [https://docs.codestrata.ai](https://docs.codestrata.ai)
