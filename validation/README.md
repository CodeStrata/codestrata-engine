# Multi-repository assessment validation harness

Internal CodeStrata assessment-accuracy infrastructure (Epic 4).

This is **not** a customer multi-repository / portfolio scan product surface.

## Purpose

Run deterministic assessments against a small, intentionally diverse repository set
and compare outputs to repository-specific expectations.

- Slice **4.1** — harness infrastructure
- Slice **4.2** — initial 5–7 repository validation set (this document)
- Slices **4.3–4.10** — pack-specific expectation depth
- Slice **4.11** — permanent expected/actual/comparison records per repository
- Slice **4.12** — cross-repository validation summary artifacts from records
- Slice **4.13** — expanded 24-repository validation set (this document)

## Selected repository set (Slice 4.13)

Exactly **24** active repositories (controlled fixtures first, workspace samples, then pinned remotes):

| Tier | ID | Role | Source |
| --- | --- | --- | --- |
| 1 | `local-cloud-signals` | Cloud/deploy positive control | controlled local |
| 1 | `local-security-hygiene` | Security hygiene positive control | controlled local |
| 1 | `local-ai-readiness` | AI readiness positive control | controlled local |
| 1 | `local-ai-negative` | AI prose/package-name negative control | controlled local |
| 1 | `local-architecture-signals` | Architecture cycle + layer skip | controlled local |
| 1 | `local-complexity-signals` | Technical debt threshold boundaries | controlled local |
| 1 | `local-dependency-signals` | Dependency hygiene (5 rules) | controlled local |
| 1 | `local-terraform-signals` | Terraform IaC / AWS stub | controlled local |
| 1 | `local-serverless-signals` | Serverless framework stub | controlled local |
| 1 | `local-compose-managed` | Compose postgres/redis managed services | controlled local |
| 1 | `local-library-npm` | npm library shape | controlled local |
| 1 | `local-cli-python` | Python argparse CLI (tests absent) | controlled local |
| 2 | `local-sample-js` | JS/npm baseline | workspace fixture |
| 2 | `local-sample-python` | Python/Flask + pytest | workspace fixture |
| 2 | `local-sample-php` | PHP/Laravel + PHPUnit | workspace fixture |
| 2 | `local-sample-csharp` | C#/ASP.NET + xUnit | workspace fixture |
| 2 | `local-sample-java` | Java/Maven + Spring Boot | workspace fixture |
| 2 | `local-typescript-app` | TypeScript/Express + Jest | controlled local |
| 2 | `local-gradle-multimodule` | Gradle multi-module Java | controlled local |
| 3 | `remote-java-spring-petclinic` | Java/Maven layered app | remote (pinned) |
| 3 | `remote-python-fastapi` | FastAPI full-stack template | remote (pinned) |
| 3 | `remote-typescript-angular` | Angular RealWorld example | remote (pinned) |
| 3 | `remote-php-bookstack` | BookStack (Laravel) | remote (pinned) |
| 4 | `remote-csharp-eshop` | .NET eShop | remote (pinned) |

### Selection principles

- **Tier 1** — small controlled fixtures with deterministic positive/negative signals per pack
- **Tier 2** — workspace or controlled samples covering language/ecosystem diversity
- **Tier 3–4** — pinned public remotes for real-world architecture, debt, dependency, and modernization depth
- Every active repository has all **8** expectation packs (schema 1.2)
- Tags (`controlled`, `real-world`, `fast`, `medium`, `slow`, language tags) support filtered execution

### Execution modes

| Mode | Flag | Scope |
| --- | --- | --- |
| All local (offline CI) | `--local-only` | 19 local repositories |
| Full active set | `--include-remote` | All 24 (network for remotes) |
| Filter by tag | `--tag controlled` / `--tag fast` | Subset by tag intersection |
| Single repository | `--repository <id>` | One repository |

Remotes classify as **SKIPPED** (not FAIL) when `--include-remote` is absent or network/checkout fails.

## Selected repository set (Slice 4.2 — superseded)

The initial six-repository set remains a subset of Slice 4.13:

| ID | Role | Source | Why selected |
| --- | --- | --- | --- |
| `local-sample-js` | A — JS/npm baseline | local fixture | Technology Inventory + Dependency; limited tests |
| `local-sample-python` | C — Python/Flask | local fixture | Dependency + Testing + Technical Debt; tests present |
| `remote-java-spring-petclinic` | B — Java/Maven | remote (pinned) | Architecture + Debt + Dependency; layered + tests; some cloud |
| `local-cloud-signals` | D — cloud/deploy | controlled local | Dockerfile, compose, k8s, deploy workflow |
| `local-security-hygiene` | E — security | controlled local | Intentional fake credential / key-marker signals |
| `local-ai-readiness` | F — AI readiness | controlled local | openai path/import + `mcp.json` (pack enabled via config) |

### Candidates reviewed

| Candidate | Decision |
| --- | --- |
| `test-fixtures/sample-js-app` | **Accepted** as Repository A |
| `test-fixtures/sample-python-app` | **Accepted** as Repository C |
| `test-fixtures/sample-java-app` | **Rejected** — too small for architecture; overlaps Petclinic for Java/Maven |
| `test-fixtures/sample-php-app` / `sample-csharp-app` | **Deferred** — language diversity for 20–30 expansion |
| Spring Petclinic (dogfood pin) | **Accepted** as Repository B (remote, pinned SHA) |
| FastAPI full-stack template | **Deferred** — overlaps Python + cloud; keep for expansion |
| Angular RealWorld | **Deferred** — JS already covered by sample-js |
| .NET eShop | **Deferred** — large; optional Repository G later |
| BookStack / VS Code | **Deferred** — size / expansion set |
| New controlled cloud / security / AI fixtures | **Accepted** as D / E / F |
| architecture/complexity/dependency fixtures | **Promoted** in Slice 4.13 |
| PHP/C#/TypeScript samples + remotes | **Accepted** in Slice 4.13 expansion |

## Validation matrix

Machine-readable matrix: `validation/matrix.py` (`ACTIVE_VALIDATION_SET`, `VALIDATION_MATRIX`).

Each row includes: tier, source type, pinned identity, language, framework, ecosystem,
approximate size, expected runtime, test posture, per-pack coverage labels,
controlled vs real-world, fast/medium/slow, and license.

Legacy Slice 4.2 table (six repositories):
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| local-sample-js | local | JavaScript | Express | npm | limited/absent | simple | baseline | npm | — | — | — | inventory | `test-fixtures/sample-js-app` |
| local-sample-python | local | Python | Flask | pip / pyproject | present | service | measurable | pip | — | — | — | dep+test+debt | `test-fixtures/sample-python-app` |
| remote-java-spring-petclinic | remote | Java | Spring Boot | Maven | present | layered | measurable | Maven | uncontrolled | compose/devcontainer | — | arch+debt+mod | `…/spring-petclinic@f182358d…` |
| local-cloud-signals | local | shell | n/a | Docker/Compose | absent | deploy-oriented | minimal | images | — | Dockerfile+k8s+GHA | — | cloud | `validation/fixtures/cloud-signals` |
| local-security-hygiene | local | Python | n/a | n/a | absent | minimal | minimal | — | controlled fake signals | — | — | security precision | `validation/fixtures/security-hygiene` |
| local-ai-readiness | local | Python | OpenAI SDK | pip | absent | agent stub | minimal | pip | — | — | openai+mcp | AI (later) | `validation/fixtures/ai-readiness` |

See `validation/matrix.py` for the full 24-repository matrix.

Tags on a repository indicate **intended coverage dimensions**, not that pack
precision has already been validated.

## Pinned commit policy

- Remote repositories **must** use a pinned commit SHA (or immutable tag).
- Floating `main` / `master` / `HEAD` / `develop` are rejected by the harness.
- `expected_commit` is verified after checkout.
- Petclinic pin: `f182358d02e4a68e52bdbabf55ca7800288511e7` (Apache-2.0, public).
- FastAPI pin: `c9e70d65c74f7adda417fc8de0757207ff77514c` (MIT).
- Angular RealWorld pin: `dd99ed2cf39c805d719f943c5d7061a5683d98a8` (MIT).
- BookStack pin: `4e406c41c4c8060a5795e74c66fb96362e54f400` (MIT).
- eShop pin: `9b4f9434f46fdc5c1a6e9e936af2868340cdbc48` (MIT).
- No credentials; no private repositories in committed definitions.

## Local versus remote execution

- **Local** fixtures assess offline (normal unit / CI path).
- **Remote** repositories require `--include-remote` (network + `git`).
- Unavailable remotes classify as **SKIPPED**, not accuracy **FAIL**.
- Normal unit tests never clone remotes.

## How to run

From `engine/` (venv with CodeStrata installed; `PYTHONPATH` includes `.`):

```bash
# List the validation set
python -m validation.run_validation --list

# All local repositories (offline)
python -m validation.run_validation --local-only --json-summary

# One repository
python -m validation.run_validation --repository local-sample-js --keep-results

# Full set including pinned remotes (network)
python -m validation.run_validation --include-remote --json-summary
```

Exit `1` on any `FAIL` / `ERROR`. Exit `0` when all selected repos `PASS` or `SKIPPED`.

## Technology Inventory accuracy (Slice 4.3)

Each repository expectation includes a `technology_inventory` block authored from
repository evidence (manifests, source extensions, build files) — not by copying
the latest `report.json`.

Classification for inventory facts:

- `TRUE_POSITIVE` / `FALSE_POSITIVE` / `FALSE_NEGATIVE` / `AMBIGUOUS` / `NOT_APPLICABLE`

Precision and recall use standard definitions. When a denominator is zero, the
metric is **unavailable** (not forced to 0 or 100). Ambiguous facts are excluded
from TP scoring.

Focused detector corrections in this slice:

- OpenAI declared/imported as **library** (not language/framework)
- `engines.node` → Node.js version
- Java `java.version` and Spring Boot parent/plugin versions when declared

Pack precision for Architecture/Debt/Dependency/Cloud/AI/Modernization belongs
to later slices.

## Security precision (Slice 4.4)

Each repository expectation includes a `security` block authored from
repository-sensitive evidence — not by copying the latest `report.json`.

Classification for Security facts:

- `TRUE_POSITIVE` / `FALSE_POSITIVE` / `FALSE_NEGATIVE` / `AMBIGUOUS` / `NOT_APPLICABLE`

Precision and recall use standard definitions for **this validation set only**.
When a denominator is zero, the metric is **unavailable** (not forced to 0 or 100).
Ambiguous results (for example legacy `SEC002` overlap) are excluded from TP scoring.

Controlled fixture (`local-security-hygiene`) is the primary positive-signal
repository. Other repositories are negative controls for credential/private-key
false positives, CI secret expressions, documentation examples, and package-name
inventions. Raw fixture values must never appear in report/findings/HTML.

Focused precision corrections in this slice:

- CI `${{ secrets.* }}` expressions classified as environment references (not
  live credential literals)
- Customer-universe dedupe preserves distinct `finding:*` evidence-scoped IDs
- Configuration rule evidence sets `line_end` with `line_start` so properties
  facts can form valid `RuleEvidence`

## Architecture precision (Slice 4.5)

Each repository expectation includes an `architecture` block authored from
repository structure (packages, imports, framework symbols) — not by copying
current findings alone.

Spring Petclinic is the primary real-world Architecture repository (framework
leakage on domain JPA entities). The other five repositories are negative
controls for invented cycles, layering, and unsupported runtime claims.

A small controlled fixture `validation/fixtures/architecture-signals` is in the
ACTIVE_VALIDATION_SET as `local-architecture-signals` (Slice 4.13).

Focused precision corrections in this slice:

- `architecture.` added to `TRACEABLE_PACK_PREFIXES` so SharedRules Architecture
  findings emit EvidenceRef envelopes
- Test/fixture-only dependency evidence paths excluded from the production
  primary architecture graph

Metrics apply only to this validation set. No runtime / microservices /
deployed-topology claims.

## Technical Debt precision (Slice 4.6)

Each repository expectation includes a `technical_debt` block authored from
complexity evidence and configured thresholds — not by copying current findings.

Default thresholds (operator `>`): large-callable 50 lines, branching 10,
nesting 4, parameters 5, oversized-type 300 lines.

A controlled fixture `validation/fixtures/complexity-signals` is in the
ACTIVE_VALIDATION_SET as `local-complexity-signals` (Slice 4.13).

Focused precision corrections in this slice:

- Technical Debt rules skip test/fixture/generated/vendor/example/documentation
  complexity subjects so they do not inflate production debt
- EvidenceMeasurement scope uses `type` for oversized-type (`type_kind` present)

Metrics apply only to this validation set. No rewrite/cost/productivity claims.

## Dependency precision (Slice 4.7)

Each repository expectation includes a `dependency` block authored from
manifest evidence and declaration-hygiene rules — not by copying current
findings.

SharedRules in scope: `dependency.unresolved-version`,
`dependency.mutable-version`, `dependency.unbounded-requirement`,
`dependency.conflicting-exact-versions`, `dependency.duplicate-declaration`.

npm / `package.json` remains out of collector scope (limitation, not a
hygiene finding). Ordinary version ranges are not mutable. Maven properties
resolved inside the repository are not unresolved.

A controlled fixture `validation/fixtures/dependency-signals` is in the
ACTIVE_VALIDATION_SET as `local-dependency-signals` (Slice 4.13).

Metrics apply only to this validation set. No CVE / license / freshness /
registry claims.

## Cloud Readiness accuracy (Slice 4.8)

Each repository expectation includes a `cloud` block authored from repository
cloud evidence — not by copying current findings.

Families in scope: `platform`, `container`, `orchestration`, `iac`,
`serverless`, `managed_service`, `deployment`.

SharedRules include `cloud.cloud-010` (containers), `cloud.cloud-011`
(orchestration), `cloud.cloud-040` (confirmed deployment pipelines),
`cloud.cloud-060` (≥3 families), `cloud.cloud-061` (deployment assets without
provider platforms), and related platform/IaC/serverless/managed-service rules.

`local-cloud-signals` is the primary positive control. Build-only CI workflows
are not confirmed deployment pipelines. Generic YAML / ordinary handlers must
not invent Kubernetes or serverless signals.

Metrics apply only to this validation set. No live cloud posture, cost,
security, or readiness claims.

## AI Readiness accuracy (Slice 4.9)

Each repository expectation includes an `ai_readiness` block authored from
repository AI-enablement evidence — not by copying current findings.

Families in scope: `api_boundary`, `documentation`, `data_retrieval`,
`ai_integration`, `tool_mcp`, `workflow_agent`, `observability_governance`.

SharedRules include `ai_readiness.ai-002` (OpenAPI), `ai-030` (LLM SDK),
`ai-040` (MCP/tools), `ai-051` (AI assets without observability),
`ai-060` (≥3 families), and related API/docs/data/prompt/RAG/workflow rules.

`local-ai-readiness` is the primary positive control. Package-name-only
“agent” tokens, prose AI mentions, generic helpers, and ordinary CI notes must
not invent integration, prompt, MCP, workflow, or RAG signals.

Metrics apply only to this validation set. No organizational AI readiness,
model quality, prompt quality, RAG quality, AI safety, or runtime agent claims.

## Modernization recommendation accuracy (Slice 4.10)

Each repository expectation includes a `modernization` block authored from
Findings that have Phase-3 recommendation providers — not by copying current
recommendation titles alone.

Canonical chain validated:

Evidence → Finding → Recommendation → Priority Action → Roadmap Initiative

Finding-backed recommendations must reference Findings. Priority Actions must
be Recommendation-backed. Canonical roadmap initiatives must be Priority
Action-backed (legacy roadmaps must be explicitly marked). Pack observation
recommendations remain under pack slices; they do not invent modernization
Priority Actions.

Forbidden conclusions include modernization/production/cloud/AI readiness,
rewrite/ROI/staffing/migration-success claims. AI Advisor content is out of
scope; validation runs with AI disabled.

Metrics apply only to this validation set.

## Validation records (Slice 4.11)

Every repository execution writes a permanent comparison record under
`validation/results/{repository_id}/` (gitignored runtime history):

```
results/{repository_id}/
  latest/
    expected.json
    actual.json
    comparison.json
    record.json
  latest_run_id.txt
  runs/{YYYYMMDDTHHMMSSZ}/
    expected.json
    actual.json
    comparison.json
    record.json
  assessment-output/   # only with --keep-results
```

- `expected.json` — loaded expectation contract
- `actual.json` — comparison-relevant actuals (no source bodies, no abs paths)
- `comparison.json` — verdict, mismatches, pack precision/recall
- `record.json` — canonical combined payload for Slice 4.12

Records are written even when assessment outputs are cleaned. Use
`--records-dir` to override the root, or `--no-record` to disable.

## Validation summaries (Slice 4.12)

Cross-repository engineering summaries are built **only** from Slice 4.11
`record.json` files. Summary generation never reruns assessments.

```
results/summaries/
  latest/
    validation-summary.json
    validation-summary.md
  runs/{summary_run_id}/
    validation-summary.json
    validation-summary.md
  latest_summary_run_id.txt
```

```bash
python -m validation.generate_summary --local-only --print-summary
python -m validation.run_validation --summarize --active-set
```

- Summary schema version: **1.0** (separate from record 1.0 and assessment 1.2)
- Default scope label: `latest-per-repository` (not an atomic suite run)
- Overall verdict precedence: ERROR → FAIL → PASS → SKIPPED
- Aggregate pack precision uses sum(TP)/sum(TP+FP); never averages repository %
- Unavailable metrics stay unavailable (not 0 or 1)
- Coverage gaps are informational; they are not automatic failures
- Exit code 0 on successful summary write regardless of overall verdict

Required disclaimer in Markdown:

> These results describe only the repositories and controlled fixtures included
> in this validation set. They are not a product-wide accuracy claim.

## Layout

```
engine/validation/
  repositories/     # definitions
  expectations/     # minimal expected-result contracts
  fixtures/         # controlled local fixtures (cloud, security, AI, IaC, …)
  configs/          # optional per-repo assessment overlays
  baselines/        # safe summary snapshots (optional)
  matrix.py
  results/          # runtime only (not committed clones/source)
  …
```

## How to add a repository

1. Add a definition under `repositories/{repository_id}.toml` (relative paths only).
2. Add `expectations/{repository_id}.json` with all eight pack blocks (schema 1.2).
3. Optional: `fixtures/` tree (static only), `configs/` overlay, `baselines/` summary.
4. Register the ID in `matrix.py` (`ACTIVE_VALIDATION_SET` + `VALIDATION_MATRIX` row).
5. Extend registry/coverage tests under `engine/tests/validation/`.

Remote repositories require a pinned commit SHA and MIT/Apache-compatible public license.
Do not commit credentials, source bodies, or absolute user paths.

## Safety

- No real secrets; security fixture uses unmistakably fake / test-only values
- No source bodies in summary or validation-record artifacts
- No absolute user paths in committed definitions or recorded comparison paths
- AI enrichment disabled; no Platform / RAG / KG dependency
- Recording failures never mask PASS/FAIL/ERROR/SKIPPED harness verdicts
- Summary generation is offline/record-only (no network, LLMs, package managers)
- Temporary clones/outputs cleaned unless `--keep-results`

## Coverage gaps (future expansion)

- Additional remotes at tier 3–4 for modernization synthesis depth
- Richer multi-language monorepo shapes beyond Gradle stub
- Pack-precision baselines per assessment head (ongoing)
- Slice 4.12 surfaces zero-TP / unavailable metrics as coverage gaps, not failures

## Schema

Assessment JSON schema remains **1.2**. Record schema remains **1.0**.
Summary schema is separately versioned at **1.0**. This harness does not change
analyzers, rules, findings, recommendations, Priority Actions, roadmap logic,
report organization, MCP, Platform, AI, RAG, or Knowledge Graph.
