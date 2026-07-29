"""Repository AI-readiness evidence tests (Phase 4.8.2)."""

from __future__ import annotations

import ast
import random
from pathlib import Path

from codestrata.application.evidence.repository_ai_readiness.artifacts import (
    repository_ai_readiness_evidence_payload,
    write_repository_ai_readiness_evidence_artifact,
)
from codestrata.application.evidence.repository_ai_readiness.discovery import (
    classify_ai_readiness_candidate,
    discover_ai_readiness_candidates,
    is_ignored_path,
)
from codestrata.application.evidence.repository_ai_readiness.service import (
    RepositoryAiReadinessEvidenceService,
)
from codestrata.config import load_settings
from codestrata.config.settings import RepositoryAiReadinessEvidenceSettings
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessEvidenceFamily,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
    EvidenceConfirmationLevel,
    RepositoryAiReadinessParseStatus,
)
from codestrata.domain.evidence.repository_ai_readiness.identifiers import (
    REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_APP_PACKAGE = Path("src/codestrata/application/evidence/repository_ai_readiness")
_FORBIDDEN_IMPORT_PREFIXES = (
    "codestrata.domain.ai_readiness",
    "codestrata.application.ai_readiness",
    "codestrata.domain.findings",
    "codestrata.application.reporting",
    "codestrata.reporting",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]  # engine root


def test_package_boundary_no_forbidden_imports() -> None:
    package_dir = _repo_root() / _APP_PACKAGE
    assert package_dir.is_dir()
    for path in sorted(package_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    assert not any(
                        mod == prefix or mod.startswith(prefix + ".")
                        for prefix in _FORBIDDEN_IMPORT_PREFIXES
                    ), f"{path.name} imports {mod}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                assert not any(
                    mod == prefix or mod.startswith(prefix + ".")
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES
                ), f"{path.name} imports from {mod}"
        assert "FindingCategory" not in source
        assert "emit_finding" not in source.lower()


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.repository_ai_readiness.enabled is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.evidence.repository_cloud.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_ai_readiness]
        enabled = true
        max_files = 100
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_ai_readiness.enabled is True
    assert settings.evidence.repository_ai_readiness.max_files == 100
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.evidence.repository_cloud.enabled is False


def test_disabled_returns_not_applicable() -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=False)
    )
    evidence = service.collect(
        repository_id="repo:x",
        relative_paths=("openapi.yaml",),
        file_texts={"openapi.yaml": "openapi: 3.0.0\n"},
    )
    assert evidence.status is RepositoryAiReadinessParseStatus.NOT_APPLICABLE
    assert evidence.file_candidates == ()


def test_no_ai_artifacts_succeeds_empty() -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:plain",
        relative_paths=("src/main.py", "src/utils.py"),
        file_texts={"src/main.py": "print('hi')\n", "src/utils.py": "x = 1\n"},
    )
    assert evidence.status is RepositoryAiReadinessParseStatus.SUCCEEDED
    assert evidence.file_candidates == ()
    assert evidence.coverage.candidate_files_discovered == 0
    assert evidence.limitations


def test_false_positive_storage_not_rag() -> None:
    assert classify_ai_readiness_candidate("src/storage.py") is None
    assert classify_ai_readiness_candidate("src/average.py") is None
    assert classify_ai_readiness_candidate("src/paragraph.py") is None
    hit = classify_ai_readiness_candidate("openapi.yaml")
    assert hit is not None
    assert hit.api_kind is AiReadinessApiBoundaryKind.OPENAPI


def test_discover_sorted_and_ignored() -> None:
    paths = [
        "node_modules/pkg/openapi.yaml",
        "openapi.yaml",
        "README.md",
        "prompts/template.txt",
    ]
    found = discover_ai_readiness_candidates(paths)
    assert [item.path for item in found] == [
        "README.md",
        "openapi.yaml",
        "prompts/template.txt",
    ]
    assert is_ignored_path("node_modules/pkg/openapi.yaml", ignore_markers=("/node_modules/",))


def test_collect_rich_ai_rag_fixture() -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=True)
    )
    paths = (
        "openapi.yaml",
        "README.md",
        "src/langchain_app.py",
        "mcp.json",
        "config/chroma.yaml",
        "workflows/temporal_workflow.py",
        "otel-collector.yaml",
        "prompts/template.txt",
    )
    texts = {
        "openapi.yaml": "openapi: 3.0.3\ninfo:\n  title: Demo\npaths:\n  /health:\n    get: {}\n",
        "README.md": "# AI Demo\n\nRAG-enabled service.\n",
        "src/langchain_app.py": (
            "from langchain.chains import RetrievalQA\n"
            "from langchain_openai import ChatOpenAI\n"
            "llm = ChatOpenAI()\n"
        ),
        "mcp.json": '{"mcpServers": {"demo": {"command": "uvx", "args": ["demo"]}}}\n',
        "config/chroma.yaml": "chromadb:\n  path: ./chroma\n",
        "workflows/temporal_workflow.py": (
            "from temporalio import workflow\n@workflow.defn\nclass IngestWorkflow:\n    pass\n"
        ),
        "otel-collector.yaml": (
            "receivers:\n  otlp:\n"
            "processors:\n  batch:\n"
            "exporters:\n  logging:\n"
            "service:\n  pipelines:\n    traces:\n"
            "      receivers: [otlp]\n"
            "# opentelemetry collector config\n"
        ),
        "prompts/template.txt": "You are a helpful assistant.\n",
    }
    evidence = service.collect(
        repository_id="repo:ai-rag",
        relative_paths=paths,
        file_texts=texts,
    )
    assert evidence.status is RepositoryAiReadinessParseStatus.SUCCEEDED
    assert evidence.schema_version == REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION
    assert any(
        item.kind is AiReadinessApiBoundaryKind.OPENAPI for item in evidence.api_boundary_facts
    )
    assert evidence.documentation_facts
    assert any(
        item.kind is AiReadinessAiIntegrationKind.AI_FRAMEWORK
        for item in evidence.ai_integration_facts
    )
    assert any(item.kind is AiReadinessToolMcpKind.MCP_SERVER for item in evidence.tool_mcp_facts)
    assert any(
        item.kind is AiReadinessDataRetrievalKind.VECTOR_DB
        for item in evidence.data_retrieval_facts
    )
    assert any(
        item.kind is AiReadinessWorkflowAgentKind.WORKFLOW_ENGINE
        for item in evidence.workflow_agent_facts
    )
    assert evidence.observability_governance_facts
    assert AiReadinessEvidenceFamily.API_BOUNDARY.value in evidence.coverage.families_represented
    payload = repository_ai_readiness_evidence_payload(evidence)
    text = dumps_stable_json(payload)
    assert "Finding" not in text
    assert "severity" not in text.lower()
    assert "readiness_score" not in text
    assert "/Users/" not in text


def test_confirmation_requires_structural_markers() -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:openapi",
        relative_paths=("openapi.yaml",),
        file_texts={"openapi.yaml": "openapi: 3.0.0\npaths:\n  /x:\n    get: {}\n"},
    )
    assert evidence.api_boundary_facts
    assert (
        evidence.api_boundary_facts[0].confirmation_level
        is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    )
    assert evidence.api_boundary_facts[0].line_hints


def test_deterministic_byte_identical(tmp_path: Path) -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=True)
    )
    paths = [
        "openapi.yaml",
        "README.md",
        "mcp.json",
        "prompts/template.txt",
    ]
    texts = {
        "openapi.yaml": "openapi: 3.0.0\npaths: {}\n",
        "README.md": "# Demo\n",
        "mcp.json": '{"mcpServers": {}}\n',
        "prompts/template.txt": "You are helpful.\n",
    }
    shuffled = paths[:]
    random.Random(7).shuffle(shuffled)
    left = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(shuffled),
        file_texts=texts,
    )
    right = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(reversed(paths)),
        file_texts=texts,
    )
    left_text = dumps_stable_json(repository_ai_readiness_evidence_payload(left))
    right_text = dumps_stable_json(repository_ai_readiness_evidence_payload(right))
    assert left_text == right_text
    assert left.evidence_fingerprint == right.evidence_fingerprint

    written = write_repository_ai_readiness_evidence_artifact(left, tmp_path)
    assert written.path.name == REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_FILENAME
    assert written.path.read_text(encoding="utf-8") == left_text
    again = write_repository_ai_readiness_evidence_artifact(right, tmp_path / "b")
    assert again.path.read_text(encoding="utf-8") == left_text


def test_dedupe_technologies() -> None:
    service = RepositoryAiReadinessEvidenceService(
        RepositoryAiReadinessEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:dedupe",
        relative_paths=("a/openapi.yaml", "b/openapi.json"),
        file_texts={
            "a/openapi.yaml": "openapi: 3.0.0\npaths: {}\n",
            "b/openapi.json": '{"openapi":"3.0.0","paths":{}}\n',
        },
    )
    assert len(evidence.api_boundary_facts) == 2
    assert evidence.coverage.technologies_represented.count("openapi") == 1
