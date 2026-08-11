# Engine verification

Repository-local verification suites for CodeStrata Engine (Community Edition).

These packages are **not** part of the installed `codestrata` wheel. They live
beside `src/` so maintainers and the public Engine mirror can reproduce
first-time Community journeys.

| Suite | Purpose |
| --- | --- |
| [`cli_installation/`](./cli_installation/) | **SV.2** — clean CLI installation verification |
| [`cli_initialization/`](./cli_initialization/) | **SV.3** — CLI initialization workflow verification |
| [`repository_assessment/`](./repository_assessment/) | **SV.4** — repository assessment end-to-end verification |
| [`assessment_report/`](./assessment_report/) | **SV.5** — assessment report quality/integrity verification |
| [`curated_repository_validation/`](./curated_repository_validation/) | **SV.10** — validate 22 curated OSS repositories |
| [`assessment_consistency/`](./assessment_consistency/) | **SV.11** — assessment consistency across the 22 SV.10 outputs |
| [`ai_provider_baseline/`](./ai_provider_baseline/) | **Epic 11, Slice 11.1** — existing AI provider (Bedrock/OpenAI) architecture and compatibility baseline (characterization only; no Slice 11.2 platform work) |
| [`ai_provider_contracts/`](./ai_provider_contracts/) | **Epic 11, Slice 11.2** — new, unwired Common AI Provider Contracts (`codestrata.ai.provider_contracts`); dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, privacy, determinism (no provider migration, no runtime wiring) |
| [`ai_provider_configuration/`](./ai_provider_configuration/) | **Epic 11, Slice 11.3** — new, unwired Standardized Provider and Model Configuration (`codestrata.ai.provider_contracts.configuration_*`); dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, provider/model resolution correctness, privacy, determinism (no provider migration, no runtime wiring, no default/precedence change) |
| [`ai_provider_execution/`](./ai_provider_execution/) | **Epic 11, Slice 11.4** — new, unwired Standardized Execution, Errors, Timeouts, and Retries (`codestrata.ai.provider_contracts.executor`/`execution_*`/`retry_*`/`timeout_policy`/`backoff`/`error_classification`); dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, retry/backoff/timeout correctness, fail-soft, privacy, determinism (no provider migration, no runtime wiring, executor unwired) |
| [`ai_provider_capabilities/`](./ai_provider_capabilities/) | **Epic 11, Slice 11.5** — new, unwired Provider Usage Metadata and Capability Discovery (`codestrata.ai.provider_contracts.capability_*`/`usage_*`); dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, catalog correctness, privacy, determinism (no provider migration, no runtime wiring, no OpenRouter) |
| [`openai_provider_migration/`](./openai_provider_migration/) | **Epic 11, Slice 11.6** — wired OpenAI migration (`provider_adapters.openai` + executor behind `OpenAIAIModelProvider`); Bedrock migration is SV.11.7 |
| [`bedrock_provider_migration/`](./bedrock_provider_migration/) | **Epic 11, Slice 11.7** — wired Bedrock migration (`provider_adapters.bedrock` + executor behind `BedrockAIModelProvider`); both providers on contracts; OpenRouter completed in Slices 11.9–11.11; see `ai_provider_platform_completion` |
| [`ai_provider_cross_provider/`](./ai_provider_cross_provider/) | **Epic 11, Slice 11.8** — cross-provider contract verification; Decision B compatibility registry retained |
| [`openrouter_provider/`](./openrouter_provider/) | **Epic 11, Slice 11.9** — OpenRouter adapter; Decision B retained; doctor local readiness in 11.11 |
| [`openrouter_configuration/`](./openrouter_configuration/) | **Epic 11, Slice 11.10** — OpenRouter configuration/authentication; explicit assess selection; Bedrock remains default |
| [`openrouter_doctor_integration/`](./openrouter_doctor_integration/) | **Epic 11, Slice 11.11** — OpenRouter doctor local readiness + mocked E2E integration; no live provider calls |
| [`ai_provider_privacy_boundaries/`](./ai_provider_privacy_boundaries/) | **Epic 11, Slice 11.12** — provider privacy, failure-isolation, and architecture boundary verification across bedrock/openai/openrouter |
| [`ai_provider_platform_completion/`](./ai_provider_platform_completion/) | **Epic 11, Slice 11.13** — Epic 11 completion verification (13/13); Decision B retained; Bedrock default; Epic 12 not started |

Platform-owned SV packages (EI, website export, Community Cloud, SV.13 defect
fixes, SV.14 cross-schema compatibility, **SV.15 deterministic outputs**) live
under `platform/verification/` and are documented in those package READMEs.

Unit tests for the Epic 9 telemetry runtime (Slices 9.1–9.12) live under
`engine/tests/telemetry/`. See `engine/docs/telemetry-runtime.md`,
`engine/docs/telemetry-disabled-default.md`,
`engine/docs/telemetry-session-consent.md`,
`engine/docs/telemetry-interactive-consent.md`,
`engine/docs/telemetry-non-interactive.md`,
`engine/docs/telemetry-cli-consent-flags.md`,
`engine/docs/telemetry-status.md`,
`engine/docs/telemetry-pre-transport-privacy.md`,
`engine/docs/telemetry-transport.md`, and
`engine/docs/telemetry-assessment-isolation.md`.

Permanent catalog (SV.4A / SV.10A):

`validation/repository-catalog/catalog.json`

- Single source of truth for smoke, regression, engineering intelligence, and
  release-validation repository identity.
- Release-validation target for **v0.2.0** is exactly **22** curated
  repositories (`release_validation_target`). Later releases may expand the
  catalog to 30 or more.
- Unsupported-language repositories (for example Groovy-only HiveMind) must not
  be relabeled as supported; HiveMind was retired from the v0.2.0 set and
  replaced by owner-approved BookStack.
- SV.10A readiness gate must PASS before the full SV.10 multi-repository
  assessment run. SV.11 consumes completed SV.10 records/artifacts and does not
  reassess by default.
- Dataset limitation: this catalog is a curated CodeStrata verification
  dataset. Its results describe only the included pinned repositories and are
  not a product-wide accuracy or industry benchmark claim.

```bash
python validation/repository-catalog/validate_catalog.py
python validation/repository-catalog/validate_catalog.py --write-readiness-report --write-import-template
```

See [`validation/repository-catalog/README.md`](../../validation/repository-catalog/README.md)
for qualification, roles/tiers, execution batches, and how to add or retire
repositories.

Run:

```bash
cd engine
python -m verification.cli_installation
python -m verification.cli_initialization
python -m verification.repository_assessment --local-only
python -m verification.assessment_report --local-only
python -m verification.curated_repository_validation --tier tier1
python -m verification.assessment_consistency
python -m verification.ai_provider_baseline
python -m verification.ai_provider_contracts
python -m verification.ai_provider_configuration
python -m verification.ai_provider_execution
python -m verification.ai_provider_capabilities
python -m verification.openai_provider_migration
python -m verification.bedrock_provider_migration
python -m verification.ai_provider_cross_provider
python -m verification.openrouter_provider
python -m verification.openrouter_configuration
python -m verification.openrouter_doctor_integration
python -m verification.ai_provider_privacy_boundaries
```
