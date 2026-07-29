"""Repository AI-readiness evidence enums (Phase 4.8.2).

Technology-neutral taxonomy for repository-observable AI/agent readiness
artifacts. Not an AI Readiness Intelligence capability enum and not Findings.
"""

from __future__ import annotations

from enum import StrEnum


class AiReadinessEvidenceFamily(StrEnum):
    API_BOUNDARY = "api_boundary"
    DOCUMENTATION = "documentation"
    DATA_RETRIEVAL = "data_retrieval"
    AI_INTEGRATION = "ai_integration"
    TOOL_MCP = "tool_mcp"
    WORKFLOW_AGENT = "workflow_agent"
    OBSERVABILITY_GOVERNANCE = "observability_governance"
    UNKNOWN = "unknown"


class AiReadinessApiBoundaryKind(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    OPENAPI = "openapi"
    CONTROLLER = "controller"
    ROUTER = "router"
    HANDLER = "handler"
    UNKNOWN = "unknown"


class AiReadinessDocumentationKind(StrEnum):
    README = "readme"
    ARCHITECTURE = "architecture"
    API_DOCS = "api_docs"
    ADR = "adr"
    SCHEMA_DICTIONARY = "schema_dictionary"
    CONTRIBUTING = "contributing"
    UNKNOWN = "unknown"


class AiReadinessDataRetrievalKind(StrEnum):
    DATABASE_REPOSITORY = "database_repository"
    SEARCH_ENGINE = "search_engine"
    VECTOR_DB = "vector_db"
    EMBEDDINGS = "embeddings"
    INGESTION = "ingestion"
    RETRIEVAL_INDEX = "retrieval_index"
    UNKNOWN = "unknown"


class AiReadinessAiIntegrationKind(StrEnum):
    LLM_SDK = "llm_sdk"
    PROMPT = "prompt"
    EMBEDDINGS_USAGE = "embeddings_usage"
    RAG_PIPELINE = "rag_pipeline"
    MODEL_CONFIG = "model_config"
    AI_FRAMEWORK = "ai_framework"
    UNKNOWN = "unknown"


class AiReadinessToolMcpKind(StrEnum):
    MCP_SERVER = "mcp_server"
    MCP_CLIENT = "mcp_client"
    TOOL_DEFINITION = "tool_definition"
    PLUGIN_REGISTRY = "plugin_registry"
    TOOL_SCHEMA = "tool_schema"
    UNKNOWN = "unknown"


class AiReadinessWorkflowAgentKind(StrEnum):
    WORKFLOW_ENGINE = "workflow_engine"
    BACKGROUND_JOB = "background_job"
    EVENT_CONSUMER = "event_consumer"
    ORCHESTRATION = "orchestration"
    AGENT_FRAMEWORK = "agent_framework"
    UNKNOWN = "unknown"


class AiReadinessObservabilityGovernanceKind(StrEnum):
    LOGGING_TRACING_METRICS = "logging_tracing_metrics"
    AUDIT = "audit"
    EVAL_ASSET = "eval_asset"
    GUARDRAIL_POLICY = "guardrail_policy"
    SECRETS_MODEL_CONFIG = "secrets_model_config"
    UNKNOWN = "unknown"


class EvidenceConfirmationLevel(StrEnum):
    DISCOVERED_CANDIDATE = "discovered_candidate"
    STRUCTURALLY_INSPECTED = "structurally_inspected"
    STRUCTURALLY_CONFIRMED = "structurally_confirmed"
    DECLARED = "declared"
    CONFIGURED = "configured"
    UNSUPPORTED = "unsupported"
    MALFORMED = "malformed"
    SKIPPED = "skipped"


class AiReadinessDiscoveryBasis(StrEnum):
    EXACT_FILENAME = "exact_filename"
    FILENAME_PATTERN = "filename_pattern"
    EXTENSION = "extension"
    DIRECTORY_CONVENTION = "directory_convention"
    CONTENT_MARKER = "content_marker"
    STRUCTURED_CONTENT = "structured_content"
    DEPENDENCY_DECLARATION = "dependency_declaration"
    CONFIG_MARKER = "config_marker"


class RepositoryAiReadinessParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RepositoryAiReadinessLimitationCategory(StrEnum):
    REPOSITORY_SNAPSHOT_ONLY = "repository-snapshot-only"
    NO_AI_EXECUTION = "no-ai-execution"
    NO_MODEL_RUNTIME = "no-model-runtime"
    NO_AGENT_EXECUTION = "no-agent-execution"
    DETECTION_BOUNDED = "detection-bounded"
    NO_READINESS_SCORE = "no-readiness-score"
    NO_RAG_QUALITY_JUDGMENT = "no-rag-quality-judgment"
    GENERATED_VENDOR_EXCLUSIONS = "generated-vendor-exclusions"
    CONTENT_MARKER_BOUNDED = "content-marker-bounded"
    OTHER = "other"
