# E02.1 — Active SQLite, hosted and portfolio call paths

Read-only inventory of **current** Engine composition after E02.3 Community surface narrowing. Platform and `workers/` trees were scanned, not edited.

## Factory runtime composition

- Module: `codestrata.infrastructure.knowledge_store.factory`
- `create_knowledge_store()` constructs **`FileKnowledgeStore`**
- Source imports `SqliteKnowledgeStore`: `False`
- Annotated return type: `FileKnowledgeStore`

Imports alone are not the evidence. The factory's runtime return type is.

## Default package dependency closure

- `certifi>=2024.0,<2027.0`
- `cryptography>=50.0,<51.0`
- `pydantic>=2.10,<3.0`
- `PyYAML>=6.0,<7.0`
- `rich>=13.9,<15.0`
- `typer>=0.15,<1.0`

- `sqlite3` is stdlib: `True` (not declared in pyproject)
- `mcp` optional extra present: `True`
- Forbidden DB/hosted drivers in default extras: `(none)`

## Persisted snapshot layout (current)

- Knowledge directory: `.codestrata/knowledge`
- Database file: `(none; legacy knowledge.sqlite is left untouched)` (schema v1)
- Blob kinds: `ai_enrichment`, `ai_execution`, `assessment_graph`, `engineering_knowledge_graph`, `findings`, `knowledge_bindings`, `recommendations`, `repository_graph`, `repository_manifest`

- production factory constructs FileKnowledgeStore (JSON/JSONL)
- repositories/{id}/{repository.json,aliases.json,snapshots/,runs/}
- indexes/{repositories,aliases,snapshots,runs}.jsonl (derived, bounded)
- locks/
- blobs/{manifests,graphs,findings,recommendations,ai}/
- tmp/
- knowledge.sqlite leftover in defaults; factory does not open it
- assessment reports remain under .codestrata-artifacts/assessments
- legacy intelligence/<portfolio_id>/ trees are left untouched

## Composition call sites

- `src/codestrata/application/agents/factory.py` — `create_knowledge_query_service`
- `src/codestrata/application/assessment/service.py` — `create_knowledge_store`
- `src/codestrata/application/incremental/factory.py` — `create_knowledge_query_service`
- `src/codestrata/application/onboarding/service.py` — `create_knowledge_store`
- `src/codestrata/cli/agent.py` — `create_knowledge_query_service`
- `src/codestrata/cli/incremental.py` — `create_knowledge_query_service`
- `src/codestrata/infrastructure/knowledge_store/__init__.py` — `FileKnowledgeStore`, `SqliteKnowledgeStore`, `create_knowledge_query_service`, `create_knowledge_store`, `open_file_knowledge_store`, `open_knowledge_store`
- `src/codestrata/infrastructure/knowledge_store/factory.py` — `FileKnowledgeStore`, `create_knowledge_query_service`, `create_knowledge_store`
- `src/codestrata/infrastructure/knowledge_store/file/__init__.py` — `FileKnowledgeStore`, `open_file_knowledge_store`
- `src/codestrata/infrastructure/knowledge_store/file/store.py` — `FileKnowledgeStore`, `open_file_knowledge_store`
- `src/codestrata/infrastructure/knowledge_store/sqlite/__init__.py` — `SqliteKnowledgeStore`, `open_knowledge_store`
- `src/codestrata/infrastructure/knowledge_store/sqlite/store.py` — `SqliteKnowledgeStore`, `open_knowledge_store`
- `src/codestrata/interfaces/mcp/factory.py` — `create_knowledge_query_service`, `create_knowledge_store`, `open_default_knowledge_store`

## Production `sqlite3` imports

- `src/codestrata/infrastructure/knowledge_store/sqlite/assessment_run_store.py`
- `src/codestrata/infrastructure/knowledge_store/sqlite/export.py`
- `src/codestrata/infrastructure/knowledge_store/sqlite/migrations.py`
- `src/codestrata/infrastructure/knowledge_store/sqlite/repository_registry.py`
- `src/codestrata/infrastructure/knowledge_store/sqlite/snapshot_store.py`
- `src/codestrata/infrastructure/knowledge_store/sqlite/store.py`

## Hosted / Platform ingest markers

- `src/codestrata/application/assessment/service.py`
- `src/codestrata/community_cloud/__init__.py`
- `src/codestrata/community_cloud/public_api_authority.py`
- `src/codestrata/community_cloud/report_publishing.py`
- `src/codestrata/integration/commercial/__init__.py`
- `src/codestrata/integration/commercial/artifacts/publisher.py`
- `src/codestrata/integration/commercial/client.py`
- `src/codestrata/integration/commercial/configuration.py`
- `src/codestrata/integration/commercial/publisher.py`

## Portfolio / EIR markers

- `src/codestrata/artifacts/__init__.py`
- `src/codestrata/artifacts/lifecycle.py`
- `src/codestrata/artifacts/portfolio_identity.py`

## Outside-Engine consumers (read-only)

Recorded **before** any later interface narrowing. Do not copy Engine
code into `platform/` or `workers/` to satisfy these imports.

- vscode-plugin Python `codestrata` imports: `0`
- workers Python `codestrata` imports: `0`

- `platform/src/codestrata_platform/rag/acceptance/qa.py:11` → `codestrata.application.knowledge.ports` (platform)
- `platform/src/codestrata_platform/rag/acceptance/qa.py:12` → `codestrata.application.knowledge.queries` (platform)
- `platform/src/codestrata_platform/rag/acceptance/qa.py:19` → `codestrata.infrastructure.knowledge_store` (platform)
- `platform/src/codestrata_platform/rag/cli/repository.py:14` → `codestrata.application.knowledge.queries` (platform)
- `platform/src/codestrata_platform/rag/cli/repository.py:54` → `codestrata.infrastructure.knowledge_store` (platform)
- `platform/src/codestrata_platform/rag/mcp/composition.py:7` → `codestrata.application.knowledge.queries` (platform)
- `platform/src/codestrata_platform/rag/mcp/repository_common.py:8` → `codestrata.application.knowledge.queries` (platform)
- `platform/src/codestrata_platform/rag/mcp/repository_common.py:9` → `codestrata.application.knowledge.queries.models` (platform)
- `platform/tests/api/test_rest_platform_contract.py:11` → `codestrata.integration.commercial.client` (platform)
- `platform/tests/api/test_rest_platform_contract.py:12` → `codestrata.integration.commercial.models` (platform)
- `platform/tests/rag/mcp/test_mcp_dogfood.py:15` → `codestrata.application.knowledge.queries` (platform)
- `platform/tests/rag/mcp/test_mcp_dogfood.py:22` → `codestrata.infrastructure.knowledge_store` (platform)
- `platform/tests/rag/mcp/test_repository_intelligence_mcp.py:14` → `codestrata.application.knowledge.queries` (platform)
- `platform/tests/rag/mcp/test_repository_intelligence_mcp.py:21` → `codestrata.infrastructure.knowledge_store` (platform)
- `verification/community_22_repository_validation/suite_execution.py:168` → `codestrata.artifacts.repository_identity` (verification)
- `verification/community_assessment_engineering_intelligence/eir_generation.py:109` → `codestrata.artifacts.lifecycle` (verification)
- `verification/community_assessment_engineering_intelligence/eir_lifecycle.py:71` → `codestrata.artifacts.lifecycle` (verification)
- `verification/community_telemetry_consent/report_publish.py:71` → `codestrata.community_cloud.report_publishing` (verification)
- `verification/release_corpus_19_3/__main__.py:268` → `codestrata.artifacts.repository_identity` (verification)

## Classification

| ID | Class | In runtime | In default closure | Summary |
|---|---|---|---|---|
| `knowledge-ports-and-queries` | retain | yes | yes | Application KnowledgeStore protocol, query service, session and staged artifact models stay as the Engine-local contract. E02.2 replaced the production adapter; ports remain. |
| `knowledge-store-factory-sqlite` | retain | yes | yes | codestrata.infrastructure.knowledge_store.factory.create_knowledge_store currently constructs FileKnowledgeStore. Production composition, not a dead import. |
| `sqlite-knowledge-store` | quarantine | no | yes | SQLite adapter is not factory-composed. A lazy compatibility export exists for Platform tests. A separately invoked maintainer helper (`python -m codestrata.infrastructure.knowledge_store.sqlite.export`) may read leftover knowledge.sqlite files. Community runtime does not import the helper. |
| `sqlite-maintainer-export` | retain | no | yes | Legacy SQLite JSON/JSONL export is a maintainer helper only. It is never imported by create_knowledge_store, assess, compare, or MCP. |
| `cli-assess-mcp-agent-incremental-onboard` | adapt | yes | yes | CLI assess, MCP server factory, agent, incremental and onboard compose through create_knowledge_store / create_knowledge_query_service. codestrata scan comparison writes file reports and does not open SQLite. |
| `cli-scan-file-comparison` | retain | yes | yes | codestrata scan uses ScanComparisonService against file reports. It does not call create_knowledge_store. codestrata agent compare reads knowledge snapshots through the query service (file store today). |
| `offline-platform-client-default` | retain | yes | yes | platform_client_from_settings always returns OfflinePlatformClient. Local assess/compare/MCP stay no-consent without hosted calls. |
| `hosted-platform-ingest-and-community-cloud` | quarantine | no | yes | Community composition never constructs RestPlatformClient. publish_assessment_to_platform and publish_artifacts_to_platform return status=removed. codestrata report publish and Community Cloud upload functions refuse hosted submission. RestPlatformClient remains importable as a compatibility projection for outside-Engine hosts. |
| `portfolio-eir-artifacts` | quarantine | no | yes | promote_intelligence_run refuses Community portfolio/EIR lifecycle. Identity helpers remain as read-only compatibility projections. Existing intelligence/ files are not migrated or deleted. |
| `knowledge-vector-store-pgvector-settings` | deprecate | yes | yes | KnowledgeSettings.vector_store allows provider=pgvector and CODESTRATA_DATABASE_URL. No Engine pgvector adapter module exists; the setting is still loaded with every CodestrataSettings parse so it is not isolated from the default package. |
| `optional-mcp-extra` | retain | yes | no | MCP is an optional extra. Default wheel dependencies do not include mcp. When installed, create_mcp_server still opens the factory knowledge store. |
| `sqlite-adapter-not-runtime-exported` | quarantine | no | no | SqliteKnowledgeStore is a lazy compatibility projection, not factory-composed. Tests may import it from the package. Community runtime composition uses FileKnowledgeStore. |

### Classification rules used

- **retain** — local YAML/file Engine ports, optional MCP extra,
  always-offline Platform client, maintainer SQLite export helper.
- **adapt** — on the supported runtime today (CLI/MCP composition).
- **deprecate** — still loaded with every settings parse (pgvector
  setting) but has no Engine adapter.
- **quarantine** — absent from Community runtime composition. SQLite
  adapter, hosted ingest, and portfolio lifecycle are not executed.

