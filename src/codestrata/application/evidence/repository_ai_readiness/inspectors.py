"""Content inspection for repository AI-readiness evidence candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDiscoveryBasis,
    AiReadinessDocumentationKind,
    AiReadinessObservabilityGovernanceKind,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
    EvidenceConfirmationLevel,
)

_OPENAPI_RE = re.compile(r"(?im)^\s*(openapi|swagger)\s*:")
_OPENAPI_JSON_RE = re.compile(r'(?im)"(openapi|swagger)"\s*:')
_PATHS_RE = re.compile(r"(?im)^\s*paths\s*:")
_PATHS_JSON_RE = re.compile(r'(?im)"paths"\s*:')
_PROTO_SERVICE_RE = re.compile(r"(?im)^\s*service\s+\w+")
_CONTROLLER_RE = re.compile(
    r"(?im)@(RestController|Controller|RequestMapping)\b|"
    r"\b(APIRouter|FastAPI|flask\.Blueprint|@app\.(route|get|post))\b"
)
_GRAPHQL_RE = re.compile(r"(?im)\b(GraphQL|gql`|type\s+Query\b|type\s+Mutation\b)\b")
_README_HEADING_RE = re.compile(r"(?im)^#{1,3}\s+\S+")
_ADR_RE = re.compile(r"(?im)\b(Status|Context|Decision|Consequences)\b")
_VECTOR_RE = re.compile(
    r"(?im)\b(chromadb|Chroma|pinecone|weaviate|qdrant|milvus|faiss|"
    r"VectorStore|embedding_function)\b"
)
_SEARCH_RE = re.compile(r"(?im)\b(elasticsearch|opensearch|OpenSearch|solr)\b")
_DB_RE = re.compile(r"(?im)\b(sqlalchemy|prisma|redis|Repository|EntityManager|jdbc)\b")
_EMBEDDING_RE = re.compile(r"(?im)\b(embed_documents|embeddings?|OpenAIEmbeddings)\b")
_LANGCHAIN_RE = re.compile(r"(?im)\b(langchain|llama_index|LlamaIndex|haystack)\b")
_LLM_SDK_RE = re.compile(
    r"(?im)\b(openai|anthropic|boto3\.client\([\"']bedrock|"
    r"ChatOpenAI|ChatAnthropic|ollama)\b"
)
_PROMPT_RE = re.compile(r"(?im)\b(PromptTemplate|ChatPromptTemplate|system_prompt|You are)\b")
_RAG_RE = re.compile(r"(?im)\b(RetrievalQA|rag_chain|retrieve_and_generate|vectorstore)\b")
_MCP_RE = re.compile(r'(?im)("mcpServers"|mcpServers|@modelcontextprotocol)\b')
_TOOL_SCHEMA_RE = re.compile(
    r'(?im)("function"\s*:\s*\{|"parameters"\s*:\s*\{|"type"\s*:\s*"function")'
)
_TEMPORAL_RE = re.compile(r"(?im)\b(temporalio|@workflow\.defn|WorkflowClient)\b")
_CELERY_RE = re.compile(r"(?im)\b(celery|@shared_task|Celery\()\b")
_AIRFLOW_RE = re.compile(r"(?im)\b(airflow|DAG\(|@dag)\b")
_LANGGRAPH_RE = re.compile(r"(?im)\b(langgraph|StateGraph|create_react_agent)\b")
_OTEL_RE = re.compile(r"(?im)\b(opentelemetry|OTEL_|prometheus|TracerProvider|MeterProvider)\b")
_GUARDRAIL_RE = re.compile(r"(?im)\b(guardrail|Guardrails|content_filter|moderation)\b")
_EVAL_RE = re.compile(r"(?im)\b(eval_dataset|EvaluationResult|deepeval|ragas)\b")
_AUDIT_RE = re.compile(r"(?im)\b(audit_log|AuditEvent|audit_trail)\b")


@dataclass(frozen=True, slots=True)
class ContentHit:
    confirmation_level: EvidenceConfirmationLevel
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...]
    detail: str | None
    line_hints: tuple[int, ...]
    technologies: tuple[str, ...] = ()
    api_kind: AiReadinessApiBoundaryKind | None = None
    documentation_kind: AiReadinessDocumentationKind | None = None
    data_kind: AiReadinessDataRetrievalKind | None = None
    ai_kind: AiReadinessAiIntegrationKind | None = None
    tool_kind: AiReadinessToolMcpKind | None = None
    workflow_kind: AiReadinessWorkflowAgentKind | None = None
    obs_kind: AiReadinessObservabilityGovernanceKind | None = None


def _line_numbers(text: str, pattern: re.Pattern[str], *, limit: int = 5) -> tuple[int, ...]:
    lines: list[int] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            lines.append(index)
            if len(lines) >= limit:
                break
    return tuple(lines)


def _hit(
    *,
    confirmed: bool,
    detail: str,
    bases: tuple[AiReadinessDiscoveryBasis, ...],
    line_hints: tuple[int, ...],
    technologies: tuple[str, ...] = (),
    **kinds: object,
) -> ContentHit:
    level = (
        EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        if confirmed
        else EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    )
    return ContentHit(
        confirmation_level=level,
        discovery_bases=bases if confirmed else (),
        detail=detail,
        line_hints=line_hints,
        technologies=technologies,
        **kinds,  # type: ignore[arg-type]
    )


def inspect_api_text(text: str, *, kind: AiReadinessApiBoundaryKind | None) -> ContentHit | None:
    openapi_hit = bool(_OPENAPI_RE.search(text) or _OPENAPI_JSON_RE.search(text))
    if kind is AiReadinessApiBoundaryKind.OPENAPI or openapi_hit:
        confirmed = bool(openapi_hit or _PATHS_RE.search(text) or _PATHS_JSON_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="openapi_spec" if confirmed else "openapi_candidate",
            bases=(AiReadinessDiscoveryBasis.STRUCTURED_CONTENT,),
            line_hints=(
                _line_numbers(text, _OPENAPI_RE)
                or _line_numbers(text, _OPENAPI_JSON_RE)
                or _line_numbers(text, _PATHS_RE)
                or _line_numbers(text, _PATHS_JSON_RE)
            ),
            technologies=("openapi",),
            api_kind=AiReadinessApiBoundaryKind.OPENAPI,
        )
    if kind is AiReadinessApiBoundaryKind.GRPC or _PROTO_SERVICE_RE.search(text):
        confirmed = bool(_PROTO_SERVICE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="grpc_proto_service" if confirmed else "proto_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _PROTO_SERVICE_RE),
            technologies=("grpc",),
            api_kind=AiReadinessApiBoundaryKind.GRPC,
        )
    if kind is AiReadinessApiBoundaryKind.GRAPHQL or _GRAPHQL_RE.search(text):
        confirmed = bool(_GRAPHQL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="graphql_schema" if confirmed else "graphql_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _GRAPHQL_RE),
            technologies=("graphql",),
            api_kind=AiReadinessApiBoundaryKind.GRAPHQL,
        )
    if kind in {
        AiReadinessApiBoundaryKind.CONTROLLER,
        AiReadinessApiBoundaryKind.ROUTER,
        AiReadinessApiBoundaryKind.HANDLER,
        AiReadinessApiBoundaryKind.REST,
    } or _CONTROLLER_RE.search(text):
        confirmed = bool(_CONTROLLER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="api_controller_or_router" if confirmed else "api_handler_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _CONTROLLER_RE),
            technologies=("rest",),
            api_kind=kind or AiReadinessApiBoundaryKind.ROUTER,
        )
    return ContentHit(
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
        discovery_bases=(),
        detail="api_candidate_inspected",
        line_hints=(),
        api_kind=kind,
    )


def inspect_documentation_text(
    text: str, *, kind: AiReadinessDocumentationKind | None
) -> ContentHit | None:
    if kind is AiReadinessDocumentationKind.ADR or _ADR_RE.search(text):
        confirmed = len(_ADR_RE.findall(text)) >= 2
        return _hit(
            confirmed=confirmed,
            detail="adr_structure" if confirmed else "adr_candidate",
            bases=(AiReadinessDiscoveryBasis.STRUCTURED_CONTENT,),
            line_hints=_line_numbers(text, _ADR_RE),
            technologies=("adr",),
            documentation_kind=AiReadinessDocumentationKind.ADR,
        )
    confirmed = bool(_README_HEADING_RE.search(text)) or len(text.strip()) > 0
    return _hit(
        confirmed=confirmed,
        detail="documentation_content" if confirmed else "empty_documentation",
        bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
        line_hints=_line_numbers(text, _README_HEADING_RE),
        technologies=((kind.value if kind else "docs"),),
        documentation_kind=kind or AiReadinessDocumentationKind.README,
    )


def inspect_data_text(text: str, *, kind: AiReadinessDataRetrievalKind | None) -> ContentHit | None:
    if kind is AiReadinessDataRetrievalKind.VECTOR_DB or _VECTOR_RE.search(text):
        confirmed = bool(_VECTOR_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="vector_db_marker" if confirmed else "vector_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _VECTOR_RE),
            technologies=("vector_db",),
            data_kind=AiReadinessDataRetrievalKind.VECTOR_DB,
        )
    if kind is AiReadinessDataRetrievalKind.SEARCH_ENGINE or _SEARCH_RE.search(text):
        confirmed = bool(_SEARCH_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="search_engine_marker" if confirmed else "search_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _SEARCH_RE),
            technologies=("search_engine",),
            data_kind=AiReadinessDataRetrievalKind.SEARCH_ENGINE,
        )
    if kind is AiReadinessDataRetrievalKind.EMBEDDINGS or _EMBEDDING_RE.search(text):
        confirmed = bool(_EMBEDDING_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="embeddings_marker" if confirmed else "embeddings_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _EMBEDDING_RE),
            technologies=("embeddings",),
            data_kind=AiReadinessDataRetrievalKind.EMBEDDINGS,
        )
    confirmed = bool(_DB_RE.search(text))
    return _hit(
        confirmed=confirmed,
        detail="data_access_marker" if confirmed else "data_candidate",
        bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
        line_hints=_line_numbers(text, _DB_RE),
        technologies=("database_repository",),
        data_kind=kind or AiReadinessDataRetrievalKind.DATABASE_REPOSITORY,
    )


def inspect_ai_text(text: str, *, kind: AiReadinessAiIntegrationKind | None) -> ContentHit | None:
    if kind is AiReadinessAiIntegrationKind.AI_FRAMEWORK or _LANGCHAIN_RE.search(text):
        confirmed = bool(_LANGCHAIN_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="ai_framework_marker" if confirmed else "ai_framework_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _LANGCHAIN_RE),
            technologies=("langchain",),
            ai_kind=AiReadinessAiIntegrationKind.AI_FRAMEWORK,
        )
    if kind is AiReadinessAiIntegrationKind.LLM_SDK or _LLM_SDK_RE.search(text):
        confirmed = bool(_LLM_SDK_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="llm_sdk_marker" if confirmed else "llm_sdk_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _LLM_SDK_RE),
            technologies=("llm_sdk",),
            ai_kind=AiReadinessAiIntegrationKind.LLM_SDK,
        )
    if kind is AiReadinessAiIntegrationKind.RAG_PIPELINE or _RAG_RE.search(text):
        confirmed = bool(_RAG_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="rag_pipeline_marker" if confirmed else "rag_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _RAG_RE),
            technologies=("rag",),
            ai_kind=AiReadinessAiIntegrationKind.RAG_PIPELINE,
        )
    if kind is AiReadinessAiIntegrationKind.PROMPT or _PROMPT_RE.search(text):
        confirmed = bool(_PROMPT_RE.search(text)) or len(text.strip()) > 0
        return _hit(
            confirmed=confirmed,
            detail="prompt_asset" if confirmed else "prompt_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _PROMPT_RE),
            technologies=("prompt",),
            ai_kind=AiReadinessAiIntegrationKind.PROMPT,
        )
    return ContentHit(
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
        discovery_bases=(),
        detail="ai_candidate_inspected",
        line_hints=(),
        ai_kind=kind,
    )


def inspect_tool_text(text: str, *, kind: AiReadinessToolMcpKind | None) -> ContentHit | None:
    mcp_kinds = {AiReadinessToolMcpKind.MCP_SERVER, AiReadinessToolMcpKind.MCP_CLIENT}
    if kind in mcp_kinds or _MCP_RE.search(text):
        confirmed = bool(_MCP_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="mcp_config" if confirmed else "mcp_candidate",
            bases=(AiReadinessDiscoveryBasis.STRUCTURED_CONTENT,),
            line_hints=_line_numbers(text, _MCP_RE),
            technologies=("mcp",),
            tool_kind=kind or AiReadinessToolMcpKind.MCP_SERVER,
        )
    confirmed = bool(_TOOL_SCHEMA_RE.search(text))
    return _hit(
        confirmed=confirmed,
        detail="tool_schema_marker" if confirmed else "tool_candidate",
        bases=(AiReadinessDiscoveryBasis.STRUCTURED_CONTENT,),
        line_hints=_line_numbers(text, _TOOL_SCHEMA_RE),
        technologies=("tool_schema",),
        tool_kind=kind or AiReadinessToolMcpKind.TOOL_DEFINITION,
    )


def inspect_workflow_text(
    text: str, *, kind: AiReadinessWorkflowAgentKind | None
) -> ContentHit | None:
    if kind is AiReadinessWorkflowAgentKind.AGENT_FRAMEWORK or _LANGGRAPH_RE.search(text):
        confirmed = bool(_LANGGRAPH_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="agent_framework_marker" if confirmed else "agent_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _LANGGRAPH_RE),
            technologies=("langgraph",),
            workflow_kind=AiReadinessWorkflowAgentKind.AGENT_FRAMEWORK,
        )
    if _TEMPORAL_RE.search(text) or (kind is AiReadinessWorkflowAgentKind.WORKFLOW_ENGINE):
        confirmed = bool(
            _TEMPORAL_RE.search(text) or _AIRFLOW_RE.search(text) or _CELERY_RE.search(text)
        )
        tech = "temporal" if _TEMPORAL_RE.search(text) else "workflow_engine"
        return _hit(
            confirmed=confirmed,
            detail="workflow_engine_marker" if confirmed else "workflow_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=(
                _line_numbers(text, _TEMPORAL_RE)
                or _line_numbers(text, _AIRFLOW_RE)
                or _line_numbers(text, _CELERY_RE)
            ),
            technologies=(tech,),
            workflow_kind=kind or AiReadinessWorkflowAgentKind.WORKFLOW_ENGINE,
        )
    if kind is AiReadinessWorkflowAgentKind.BACKGROUND_JOB or _CELERY_RE.search(text):
        confirmed = bool(_CELERY_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="background_job_marker" if confirmed else "job_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _CELERY_RE),
            technologies=("celery",),
            workflow_kind=AiReadinessWorkflowAgentKind.BACKGROUND_JOB,
        )
    return ContentHit(
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
        discovery_bases=(),
        detail="workflow_candidate_inspected",
        line_hints=(),
        workflow_kind=kind,
    )


def inspect_observability_text(
    text: str, *, kind: AiReadinessObservabilityGovernanceKind | None
) -> ContentHit | None:
    if kind is AiReadinessObservabilityGovernanceKind.LOGGING_TRACING_METRICS or _OTEL_RE.search(
        text
    ):
        confirmed = bool(_OTEL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="otel_or_metrics_marker" if confirmed else "observability_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _OTEL_RE),
            technologies=("opentelemetry",),
            obs_kind=AiReadinessObservabilityGovernanceKind.LOGGING_TRACING_METRICS,
        )
    if kind is AiReadinessObservabilityGovernanceKind.GUARDRAIL_POLICY or _GUARDRAIL_RE.search(
        text
    ):
        confirmed = bool(_GUARDRAIL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="guardrail_marker" if confirmed else "guardrail_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _GUARDRAIL_RE),
            technologies=("guardrail",),
            obs_kind=AiReadinessObservabilityGovernanceKind.GUARDRAIL_POLICY,
        )
    if kind is AiReadinessObservabilityGovernanceKind.EVAL_ASSET or _EVAL_RE.search(text):
        confirmed = bool(_EVAL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="eval_asset_marker" if confirmed else "eval_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _EVAL_RE),
            technologies=("eval",),
            obs_kind=AiReadinessObservabilityGovernanceKind.EVAL_ASSET,
        )
    if kind is AiReadinessObservabilityGovernanceKind.AUDIT or _AUDIT_RE.search(text):
        confirmed = bool(_AUDIT_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="audit_marker" if confirmed else "audit_candidate",
            bases=(AiReadinessDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _AUDIT_RE),
            technologies=("audit",),
            obs_kind=AiReadinessObservabilityGovernanceKind.AUDIT,
        )
    return ContentHit(
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
        discovery_bases=(),
        detail="observability_candidate_inspected",
        line_hints=(),
        obs_kind=kind,
    )
