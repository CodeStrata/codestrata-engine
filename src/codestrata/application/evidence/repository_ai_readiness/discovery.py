"""Candidate path discovery for repository AI-readiness evidence."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDiscoveryBasis,
    AiReadinessDocumentationKind,
    AiReadinessEvidenceFamily,
    AiReadinessObservabilityGovernanceKind,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
)
from codestrata.scan_boundary import default_ignore_path_markers

DEFAULT_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_DOCS_DIR_MARKERS = frozenset({"docs", "documentation", "adr", "adrs"})
_PROMPTS_DIR_MARKERS = frozenset({"prompts", "prompt"})
_TOOLS_DIR_MARKERS = frozenset({"tools", "mcp"})
_ROUTERS_DIR_MARKERS = frozenset({"routers", "routes", "controllers", "handlers"})


@dataclass(frozen=True, slots=True)
class PathClassification:
    path: str
    family: AiReadinessEvidenceFamily
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...]
    technology_hints: tuple[str, ...]
    api_kind: AiReadinessApiBoundaryKind | None = None
    documentation_kind: AiReadinessDocumentationKind | None = None
    data_kind: AiReadinessDataRetrievalKind | None = None
    ai_kind: AiReadinessAiIntegrationKind | None = None
    tool_kind: AiReadinessToolMcpKind | None = None
    workflow_kind: AiReadinessWorkflowAgentKind | None = None
    obs_kind: AiReadinessObservabilityGovernanceKind | None = None


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def is_ignored_path(path: str, *, ignore_markers: Sequence[str]) -> bool:
    normalized = f"/{normalize_relative_path(path).lower()}/"
    return any(marker.lower() in normalized for marker in ignore_markers)


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(normalize_relative_path(path)).parts)


def _classify_api(name: str, parts: Sequence[str]) -> PathClassification | None:
    lower = name.lower()
    if lower in {
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "swagger.yaml",
        "swagger.yml",
        "swagger.json",
    } or fnmatch.fnmatch(lower, "swagger.*"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.API_BOUNDARY,
            discovery_bases=(AiReadinessDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("openapi",),
            api_kind=AiReadinessApiBoundaryKind.OPENAPI,
        )
    if lower.endswith(".proto"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.API_BOUNDARY,
            discovery_bases=(AiReadinessDiscoveryBasis.EXTENSION,),
            technology_hints=("grpc",),
            api_kind=AiReadinessApiBoundaryKind.GRPC,
        )
    if lower.endswith("controller.java") or lower.endswith("controller.py"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.API_BOUNDARY,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("controller",),
            api_kind=AiReadinessApiBoundaryKind.CONTROLLER,
        )
    if (
        fnmatch.fnmatch(lower, "routes.*")
        or fnmatch.fnmatch(lower, "graphql*")
        or "routers" in parts
    ):
        hint = "graphql" if "graphql" in lower else "router"
        kind = (
            AiReadinessApiBoundaryKind.GRAPHQL
            if "graphql" in lower
            else AiReadinessApiBoundaryKind.ROUTER
        )
        basis = (
            AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION
            if "routers" in parts
            else AiReadinessDiscoveryBasis.FILENAME_PATTERN
        )
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.API_BOUNDARY,
            discovery_bases=(basis,),
            technology_hints=(hint,),
            api_kind=kind,
        )
    if any(part in _ROUTERS_DIR_MARKERS for part in parts) and (
        lower.endswith(".py") or lower.endswith(".ts") or lower.endswith(".js")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.API_BOUNDARY,
            discovery_bases=(AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("router",),
            api_kind=AiReadinessApiBoundaryKind.ROUTER,
        )
    return None


def _classify_documentation(name: str, parts: Sequence[str]) -> PathClassification | None:
    lower = name.lower()
    if lower.startswith("readme"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("readme",),
            documentation_kind=AiReadinessDocumentationKind.README,
        )
    if lower.startswith("contributing"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("contributing",),
            documentation_kind=AiReadinessDocumentationKind.CONTRIBUTING,
        )
    if lower.startswith("adr") or (
        "adr" in parts and (lower.endswith(".md") or lower.endswith(".markdown"))
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("adr",),
            documentation_kind=AiReadinessDocumentationKind.ADR,
        )
    if lower in {"architecture.md", "architecture.markdown"}:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("architecture",),
            documentation_kind=AiReadinessDocumentationKind.ARCHITECTURE,
        )
    if "docs" in parts and (
        lower.endswith(".md")
        or lower.endswith(".markdown")
        or lower.endswith(".rst")
        or "schema" in lower
        or "dictionary" in lower
        or "openapi" in lower
        or "api" in lower
    ):
        if "schema" in lower or "dictionary" in lower:
            kind = AiReadinessDocumentationKind.SCHEMA_DICTIONARY
            hint = "schema_dictionary"
        elif "api" in lower or "openapi" in lower:
            kind = AiReadinessDocumentationKind.API_DOCS
            hint = "api_docs"
        elif "architecture" in lower:
            kind = AiReadinessDocumentationKind.ARCHITECTURE
            hint = "architecture"
        else:
            kind = AiReadinessDocumentationKind.UNKNOWN
            hint = "docs"
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=(hint,),
            documentation_kind=kind,
        )
    if any(part in _DOCS_DIR_MARKERS for part in parts) and lower.endswith(".md"):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DOCUMENTATION,
            discovery_bases=(AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("docs",),
            documentation_kind=AiReadinessDocumentationKind.UNKNOWN,
        )
    return None


def _classify_data(name: str, parts: Sequence[str], path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if lower.endswith("repository.java") or lower == "prisma.schema":
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("database_repository",),
            data_kind=AiReadinessDataRetrievalKind.DATABASE_REPOSITORY,
        )
    if any(
        token in lower or token in path_lower
        for token in ("chroma", "pinecone", "weaviate", "qdrant", "milvus", "faiss")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("vector_db",),
            data_kind=AiReadinessDataRetrievalKind.VECTOR_DB,
        )
    if any(
        token in lower or token in path_lower for token in ("elasticsearch", "opensearch", "solr")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("search_engine",),
            data_kind=AiReadinessDataRetrievalKind.SEARCH_ENGINE,
        )
    if "redis" in lower or "sqlalchemy" in lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("database_repository",),
            data_kind=AiReadinessDataRetrievalKind.DATABASE_REPOSITORY,
        )
    if "embedding" in lower or "embeddings" in path_lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("embeddings",),
            data_kind=AiReadinessDataRetrievalKind.EMBEDDINGS,
        )
    if any(token in lower for token in ("chunk", "ingest", "indexer", "indexing")):
        kind = (
            AiReadinessDataRetrievalKind.INGESTION
            if "ingest" in lower or "chunk" in lower
            else AiReadinessDataRetrievalKind.RETRIEVAL_INDEX
        )
        hint = "ingestion" if kind is AiReadinessDataRetrievalKind.INGESTION else "retrieval_index"
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.DATA_RETRIEVAL,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=(hint,),
            data_kind=kind,
        )
    return None


def _classify_ai(name: str, parts: Sequence[str], path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if any(part in _PROMPTS_DIR_MARKERS for part in parts) or "prompt" in lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.AI_INTEGRATION,
            discovery_bases=(
                (
                    AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION
                    if any(part in _PROMPTS_DIR_MARKERS for part in parts)
                    else AiReadinessDiscoveryBasis.FILENAME_PATTERN
                ),
            ),
            technology_hints=("prompt",),
            ai_kind=AiReadinessAiIntegrationKind.PROMPT,
        )
    if any(
        token in lower or token in path_lower
        for token in ("langchain", "llama_index", "llamaindex", "haystack", "semantic_kernel")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.AI_INTEGRATION,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("ai_framework",),
            ai_kind=AiReadinessAiIntegrationKind.AI_FRAMEWORK,
        )
    if any(
        token in lower or token in path_lower
        for token in ("openai", "anthropic", "bedrock", "ollama", "gemini", "mistral")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.AI_INTEGRATION,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("llm_sdk",),
            ai_kind=AiReadinessAiIntegrationKind.LLM_SDK,
        )
    rag_path = "/rag/" in f"/{path_lower}/"
    rag_name = (
        lower.startswith("rag_")
        or lower.startswith("rag.")
        or "_rag." in lower
        or lower in {"rag.py", "rag.ts", "rag.js"}
        or "rag_pipeline" in lower
        or "rag_retriev" in lower
    )
    if rag_path or rag_name:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.AI_INTEGRATION,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("rag",),
            ai_kind=AiReadinessAiIntegrationKind.RAG_PIPELINE,
        )
    if any(token in lower for token in ("model_config", "llm_config", "ai_config")):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.AI_INTEGRATION,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("model_config",),
            ai_kind=AiReadinessAiIntegrationKind.MODEL_CONFIG,
        )
    return None


def _classify_tool(name: str, parts: Sequence[str], path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if (
        lower == "mcp.json"
        or (".cursor" in parts and lower.startswith("mcp"))
        or fnmatch.fnmatch(path_lower, ".cursor/mcp*")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.TOOL_MCP,
            discovery_bases=(AiReadinessDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("mcp",),
            tool_kind=AiReadinessToolMcpKind.MCP_SERVER,
        )
    if any(part in _TOOLS_DIR_MARKERS for part in parts) and (
        lower.endswith(".py")
        or lower.endswith(".ts")
        or lower.endswith(".js")
        or lower.endswith(".json")
        or lower.endswith(".yaml")
        or lower.endswith(".yml")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.TOOL_MCP,
            discovery_bases=(AiReadinessDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("tool_definition",),
            tool_kind=AiReadinessToolMcpKind.TOOL_DEFINITION,
        )
    if "function" in lower and "schema" in lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.TOOL_MCP,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("tool_schema",),
            tool_kind=AiReadinessToolMcpKind.TOOL_SCHEMA,
        )
    if "plugin" in lower and ("registry" in lower or "manifest" in lower):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.TOOL_MCP,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("plugin_registry",),
            tool_kind=AiReadinessToolMcpKind.PLUGIN_REGISTRY,
        )
    return None


def _classify_workflow(
    name: str, parts: Sequence[str], path_lower: str
) -> PathClassification | None:
    lower = name.lower()
    if any(
        token in lower or token in path_lower
        for token in ("airflow", "temporal", "prefect", "dagster", "langgraph")
    ):
        hint = (
            "langgraph" if "langgraph" in lower or "langgraph" in path_lower else "workflow_engine"
        )
        kind = (
            AiReadinessWorkflowAgentKind.AGENT_FRAMEWORK
            if "langgraph" in hint
            else AiReadinessWorkflowAgentKind.WORKFLOW_ENGINE
        )
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.WORKFLOW_AGENT,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=(hint,),
            workflow_kind=kind,
        )
    if "celery" in lower or "celery" in path_lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.WORKFLOW_AGENT,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("celery",),
            workflow_kind=AiReadinessWorkflowAgentKind.BACKGROUND_JOB,
        )
    if "workflow" in lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.WORKFLOW_AGENT,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("workflow",),
            workflow_kind=AiReadinessWorkflowAgentKind.ORCHESTRATION,
        )
    if any(token in lower for token in ("consumer", "subscriber", "listener")) and (
        lower.endswith(".py") or lower.endswith(".java") or lower.endswith(".ts")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.WORKFLOW_AGENT,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("event_consumer",),
            workflow_kind=AiReadinessWorkflowAgentKind.EVENT_CONSUMER,
        )
    return None


def _classify_observability(
    name: str, parts: Sequence[str], path_lower: str
) -> PathClassification | None:
    lower = name.lower()
    if any(
        token in lower or token in path_lower
        for token in ("otel", "opentelemetry", "prometheus", "grafana", "jaeger", "zipkin")
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.OBSERVABILITY_GOVERNANCE,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("logging_tracing_metrics",),
            obs_kind=AiReadinessObservabilityGovernanceKind.LOGGING_TRACING_METRICS,
        )
    if "guardrail" in lower or "guardrails" in path_lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.OBSERVABILITY_GOVERNANCE,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("guardrail",),
            obs_kind=AiReadinessObservabilityGovernanceKind.GUARDRAIL_POLICY,
        )
    if (
        "/evals/" in f"/{path_lower}/"
        or "/eval/" in f"/{path_lower}/"
        or lower.startswith("eval_")
        or lower.startswith("evals.")
        or "_eval." in lower
        or "evaluation" in lower
    ):
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.OBSERVABILITY_GOVERNANCE,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("eval",),
            obs_kind=AiReadinessObservabilityGovernanceKind.EVAL_ASSET,
        )
    if lower.startswith("audit") or "_audit." in lower or "audit_" in lower:
        return PathClassification(
            path="",
            family=AiReadinessEvidenceFamily.OBSERVABILITY_GOVERNANCE,
            discovery_bases=(AiReadinessDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("audit",),
            obs_kind=AiReadinessObservabilityGovernanceKind.AUDIT,
        )
    return None


def classify_ai_readiness_candidate(path: str) -> PathClassification | None:
    """Classify a relative path as an AI-readiness evidence candidate, or None."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return None
    parts = _path_parts(normalized)
    name = PurePosixPath(normalized).name
    path_lower = normalized.lower()

    for classified in (
        _classify_api(name, parts),
        _classify_documentation(name, parts),
        _classify_data(name, parts, path_lower),
        _classify_ai(name, parts, path_lower),
        _classify_tool(name, parts, path_lower),
        _classify_workflow(name, parts, path_lower),
        _classify_observability(name, parts, path_lower),
    ):
        if classified is not None:
            return PathClassification(
                path=normalized,
                family=classified.family,
                discovery_bases=classified.discovery_bases,
                technology_hints=classified.technology_hints,
                api_kind=classified.api_kind,
                documentation_kind=classified.documentation_kind,
                data_kind=classified.data_kind,
                ai_kind=classified.ai_kind,
                tool_kind=classified.tool_kind,
                workflow_kind=classified.workflow_kind,
                obs_kind=classified.obs_kind,
            )
    return None


def discover_ai_readiness_candidates(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> list[PathClassification]:
    found: list[PathClassification] = []
    for raw in relative_paths:
        normalized = normalize_relative_path(raw)
        if not normalized or is_ignored_path(normalized, ignore_markers=ignore_markers):
            continue
        classified = classify_ai_readiness_candidate(normalized)
        if classified is not None:
            found.append(classified)
    found.sort(key=lambda item: item.path)
    return found[:max_files]
