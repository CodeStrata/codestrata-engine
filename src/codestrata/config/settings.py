"""Application configuration loaded from a TOML file."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from codestrata.config.dotenv import load_dotenv
from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError
from codestrata.repository_auth.github_urls import parse_github_repository_url
from codestrata.repository_auth.models import RepositoryAuthenticationConfig
from codestrata.scan_boundary import default_ignore_path_markers


def _default_ignore_path_markers_list() -> list[str]:
    return list(default_ignore_path_markers())

if TYPE_CHECKING:
    from codestrata.config.profiles import ConfigurationIssue


class RepositorySettings(BaseModel):
    """Configuration for the repository being analyzed.

    Provide at least one of:

    * ``url`` — GitHub HTTPS/SSH URL (required for ``codestrata scan``)
    * ``path`` — local filesystem path (supported by ``codestrata assess``)
    """

    url: str | None = None
    path: str | None = None
    branch: str | None = None
    authentication: RepositoryAuthenticationConfig | None = None

    @field_validator("url")
    @classmethod
    def validate_repository_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        if not compact:
            raise ValueError("repository.url must be a nonempty GitHub URL")
        # Validate shape at configuration load time; do not resolve credentials.
        parse_github_repository_url(compact)
        return compact

    @field_validator("path")
    @classmethod
    def validate_repository_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        if not compact:
            raise ValueError("repository.path must be a nonempty local path")
        if "://" in compact:
            raise ValueError(
                "repository.path must be a local filesystem path, not a URL. "
                "Use repository.url for GitHub repositories."
            )
        return compact

    @model_validator(mode="after")
    def require_url_or_path(self) -> RepositorySettings:
        if self.url is None and self.path is None:
            raise ValueError(
                "Configure repository.url (GitHub) or repository.path (local). "
                'Example: path = "test-fixtures/sample-js-app" or '
                'url = "https://github.com/org/repo"'
            )
        return self


class WorkspaceSettings(BaseModel):
    """Configuration for the local analysis workspace."""

    directory: Path = Path(".codestrata-workspace")
    clean_before_clone: bool = True


class ScanBoundarySettings(BaseModel):
    """Shared repository scan-boundary overrides (Phase 13.6.3).

    Precedence when deciding path inclusion:

    1. ``include_paths``
    2. ``exclude_paths``
    3. ``source_role_overrides`` / role roots (classification only for retained paths)
    4. default excluded directory names
    5. heuristic source-role classification
    """

    excluded_directories: list[str] = Field(default_factory=list)
    include_default_directories: list[str] = Field(
        default_factory=list,
        description=(
            "Directory names to keep despite defaults (e.g. vendor when it is "
            "first-party source)."
        ),
    )
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    production_roots: list[str] = Field(default_factory=list)
    test_roots: list[str] = Field(default_factory=list)
    fixture_roots: list[str] = Field(default_factory=list)
    example_roots: list[str] = Field(default_factory=list)
    generated_roots: list[str] = Field(default_factory=list)
    vendor_roots: list[str] = Field(default_factory=list)
    documentation_roots: list[str] = Field(default_factory=list)
    source_role_overrides: dict[str, str] = Field(default_factory=dict)
    ignore_path_markers: list[str] = Field(default_factory=list)


class PmdSettings(BaseModel):
    """Configuration for the PMD static-analysis provider."""

    enabled: bool = True
    executable: str = "pmd"
    profile: str = "standard"
    rulesets: list[str] = Field(
        default_factory=lambda: [
            "category/java/bestpractices.xml",
            "category/java/errorprone.xml",
            "category/java/design.xml",
        ]
    )
    minimum_priority: int = 5
    timeout_seconds: int = 120

    @field_validator("executable")
    @classmethod
    def validate_executable(cls, value: str) -> str:
        compact = value.strip()
        if not compact:
            raise ValueError("PMD executable must be a nonempty string")
        if any(character in compact for character in [";", "|", "&", "`", "$", "\n"]):
            raise ValueError("PMD executable must not contain shell metacharacters")
        return compact

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, value: str) -> str:
        from codestrata.static_analysis.providers.pmd_profiles import parse_pmd_profile

        return parse_pmd_profile(value).value

    @field_validator("rulesets")
    @classmethod
    def validate_rulesets(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("PMD rulesets must not be empty")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("PMD rulesets must be nonempty strings")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("minimum_priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("PMD minimum_priority must be between 1 and 5")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("PMD timeout_seconds must be a positive integer")
        return value


class StaticAnalysisProviderSettings(BaseModel):
    """Provider-specific static-analysis settings."""

    pmd: PmdSettings = Field(default_factory=PmdSettings)


class StaticAnalysisSettings(BaseModel):
    """Top-level static-analysis subsystem settings."""

    enabled: bool = False
    fail_on_provider_error: bool = False
    pmd: PmdSettings = Field(default_factory=PmdSettings)

    @model_validator(mode="before")
    @classmethod
    def coerce_nested_pmd(cls, value: object) -> object:
        """Allow both [static_analysis.pmd] nesting styles from TOML."""

        if not isinstance(value, dict):
            return value
        # tomllib may provide pmd as nested table already.
        return value


class AwsSettings(BaseModel):
    """Optional AWS session settings for Bedrock and related services.

    Community Edition uses the standard AWS credential provider chain.
    Prefer ``AWS_PROFILE`` / ``AWS_REGION`` (or default credentials) on each
    machine. ``[aws].profile`` is an optional override only — do not commit
    developer-specific profile names in shared repositories.
    """

    profile: str | None = None
    region: str | None = None

    @field_validator("profile", "region")
    @classmethod
    def validate_optional_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        return compact or None


class BedrockSettings(BaseModel):
    """AWS Bedrock settings for assessment, embeddings, and grounded answers."""

    model_id: str | None = None
    region: str | None = None
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    # Blank / omitted means unset — do not coerce to None (breaks str typing).
    answer_model: str = ""
    timeout_seconds: int = 60
    max_retries: int = 3

    @field_validator("model_id", "region")
    @classmethod
    def validate_optional_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        return compact or None

    @field_validator("answer_model", mode="before")
    @classmethod
    def normalize_answer_model(cls, value: object) -> str:
        """Treat blank values as unset (empty string), never None."""

        if value is None:
            return ""
        return str(value).strip()

    @field_validator("embedding_model", mode="before")
    @classmethod
    def normalize_embedding_model(cls, value: object) -> str:
        compact = str(value or "").strip()
        return compact or "amazon.titan-embed-text-v2:0"

    @field_validator("timeout_seconds", "max_retries")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value


class OpenAISettings(BaseModel):
    """OpenAI API settings for embeddings and grounded answers (Phase 5.8)."""

    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    answer_model: str = "gpt-4o-mini"
    embedding_dimensions: int = 0
    timeout_seconds: int = 60
    max_retries: int = 3

    @field_validator("api_key_env", "embedding_model", "answer_model", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        compact = str(value or "").strip()
        if not compact:
            raise ValueError("must be a nonempty string")
        return compact

    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_dimensions(cls, value: int) -> int:
        if value < 0:
            raise ValueError("embedding_dimensions must be >= 0")
        return value

    @field_validator("timeout_seconds", "max_retries")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value


DEFAULT_BEDROCK_MODEL_ID = "amazon.nova-lite-v1:0"
DEFAULT_BEDROCK_PROVIDER = "bedrock"


class AiSettings(BaseModel):
    """AI subsystem settings (assessment + knowledge providers).

    ``embedding_provider`` and ``answer_provider`` are independently
    configurable (Phase 5.8). ``provider`` selects the Modernization Advisor
    model backend for ``codestrata assess --with-ai`` (Bedrock or OpenAI).
    """

    provider: str = "bedrock"
    embedding_provider: str = "deterministic"
    answer_provider: str = "deterministic_extractive"
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)

    @field_validator("provider", "embedding_provider", "answer_provider")
    @classmethod
    def validate_provider_tokens(cls, value: str) -> str:
        compact = value.strip().lower()
        if not compact:
            raise ValueError("must be a nonempty string")
        return compact

    @field_validator("provider")
    @classmethod
    def validate_assess_provider(cls, value: str) -> str:
        # Built-ins: bedrock, openai. Additional names resolve via
        # AssessAIProviderRegistry at assess time (Phase 6.5).
        if not value:
            raise ValueError("ai.provider must be a nonempty string")
        return value

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        allowed = {"deterministic", "bedrock", "openai"}
        if value not in allowed:
            raise ValueError(
                f"ai.embedding_provider must be one of {sorted(allowed)}"
            )
        return value

    @field_validator("answer_provider")
    @classmethod
    def validate_answer_provider(cls, value: str) -> str:
        # deterministic aliases both accepted
        allowed = {
            "deterministic",
            "deterministic_extractive",
            "bedrock",
            "openai",
        }
        if value not in allowed:
            raise ValueError(
                f"ai.answer_provider must be one of {sorted(allowed)}"
            )
        return value


class KnowledgeVectorStoreSettings(BaseModel):
    """Vector-store provider settings for the Repository Knowledge Layer.

    ``memory`` is the default (zero setup, non-persistent). ``pgvector`` is the
    Phase 5.4+ production provider. Prefer ``CODESTRATA_DATABASE_URL`` for the
    database URL — do not put real credentials in codestrata.toml.
    """

    model_config = ConfigDict(populate_by_name=True)

    provider: str = "memory"
    # Deprecated: prefer CODESTRATA_DATABASE_URL. Kept for test/programmatic compat.
    connection_string: str = ""
    connection_string_env: str = "CODESTRATA_DATABASE_URL"
    # TOML key remains ``schema``; Python attribute avoids BaseModel.schema clash.
    schema_name: str = Field(default="codestrata", alias="schema")
    hnsw: bool = True
    connect_timeout_seconds: int = 10

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        compact = value.strip().lower()
        allowed = {"memory", "pgvector"}
        if compact not in allowed:
            raise ValueError(
                f"knowledge.vector_store.provider must be one of {sorted(allowed)}"
            )
        return compact

    @field_validator("schema_name")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        compact = value.strip().lower()
        if not compact or not compact.replace("_", "").isalnum():
            raise ValueError(
                "knowledge.vector_store.schema must be a nonempty alphanumeric "
                "identifier (underscores allowed)"
            )
        return compact

    @field_validator("connection_string", "connection_string_env")
    @classmethod
    def normalize_optional_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("connect_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("connect_timeout_seconds must be a positive integer")
        return value


class KnowledgeProjectionSettings(BaseModel):
    """In-memory knowledge document projection settings (Phase 5.2)."""

    enabled: bool = False
    include_repository_files: bool = True
    include_findings: bool = True
    include_recommendations: bool = True
    include_evidence: bool = True
    include_assessments: bool = True
    include_report_sections: bool = True
    write_corpus_artifact: bool = False


class KnowledgeChunkingSettings(BaseModel):
    """Deterministic knowledge chunking settings (Phase 5.2)."""

    enabled: bool = False
    strategy: str = "deterministic"
    max_characters: int = 4000
    overlap_characters: int = 400
    preserve_logical_units: bool = True

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, value: str) -> str:
        compact = value.strip().lower()
        if compact != "deterministic":
            raise ValueError("knowledge.chunking.strategy currently supports only 'deterministic'")
        return compact

    @field_validator("max_characters")
    @classmethod
    def validate_max_characters(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("knowledge.chunking.max_characters must be positive")
        return value

    @field_validator("overlap_characters")
    @classmethod
    def validate_overlap(cls, value: int) -> int:
        if value < 0:
            raise ValueError("knowledge.chunking.overlap_characters must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_overlap_bound(self) -> KnowledgeChunkingSettings:
        if self.overlap_characters >= self.max_characters:
            raise ValueError(
                "knowledge.chunking.overlap_characters must be less than max_characters"
            )
        return self


class KnowledgeEmbeddingSettings(BaseModel):
    """Embedding provider settings (Phase 5.3 / 5.8).

    ``provider`` selects the embedding backend. Prefer aligning with
    ``[ai].embedding_provider``. Production providers: ``bedrock``, ``openai``.
    """

    enabled: bool = False
    provider: str = "deterministic"
    model: str = "deterministic-test-embedding"
    model_version: str = "1.0.0"
    dimension: int = 384
    batch_size: int = 32
    max_input_characters: int = 12_000

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        compact = value.strip().lower()
        allowed = {
            "deterministic",
            "bedrock",
            "openai",
            "local_sentence_transformer",
        }
        if compact not in allowed:
            raise ValueError(
                f"knowledge.embedding.provider must be one of {sorted(allowed)}"
            )
        return compact

    @field_validator("model", "model_version")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        compact = value.strip()
        if not compact:
            raise ValueError("must be a nonempty string")
        return compact

    @field_validator("dimension", "batch_size", "max_input_characters")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value


class KnowledgeIndexingSettings(BaseModel):
    """Knowledge vector indexing settings (Phase 5.3)."""

    enabled: bool = False
    delete_stale_records: bool = True
    write_manifest: bool = False
    manifest_filename: str = "repository-knowledge-index.json"

    @field_validator("manifest_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        compact = value.strip()
        if not compact or "/" in compact or "\\" in compact:
            raise ValueError("manifest_filename must be a basename without path separators")
        return compact


class KnowledgeRetrievalSettings(BaseModel):
    """Repository knowledge retrieval settings (Phase 5.5 / 5.9)."""

    enabled: bool = False
    mode: str = "vector"  # vector | lexical | hybrid
    vector_weight: float = 1.0
    lexical_weight: float = 1.0
    top_k: int = 10
    # Prefer ``result_limit`` in new configs; falls back to ``top_k`` when unset.
    result_limit: int | None = None
    candidate_limit: int = 30
    minimum_score: float = 0.0
    rrf_k: int = 60
    max_query_characters: int = 4000
    max_context_characters: int = 30_000
    max_chunks_per_document: int = 3
    max_chunks_per_file: int = 3
    max_chunks_per_source_type: int = 5
    include_content: bool = True
    include_metadata: bool = True
    include_traceability: bool = True
    write_result_artifact: bool = False
    result_filename: str = "repository-retrieval-result.json"

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: object) -> str:
        compact = str(value or "vector").strip().lower()
        allowed = {"vector", "lexical", "hybrid"}
        if compact not in allowed:
            raise ValueError(
                f"knowledge.retrieval.mode must be one of {sorted(allowed)}"
            )
        return compact

    @field_validator("vector_weight", "lexical_weight")
    @classmethod
    def validate_weights(cls, value: float) -> float:
        if value < 0:
            raise ValueError("retrieval weights must be >= 0")
        return float(value)

    @field_validator(
        "top_k",
        "candidate_limit",
        "rrf_k",
        "max_query_characters",
        "max_context_characters",
        "max_chunks_per_document",
        "max_chunks_per_file",
        "max_chunks_per_source_type",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("result_limit")
    @classmethod
    def validate_result_limit(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("result_limit must be a positive integer")
        return value

    @field_validator("result_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        compact = value.strip()
        if not compact or "/" in compact or "\\" in compact:
            raise ValueError("result_filename must be a basename without path separators")
        return compact

    def resolve_result_limit(self) -> int:
        """Final hit count: ``result_limit`` when set, otherwise ``top_k``."""

        return self.result_limit if self.result_limit is not None else self.top_k


class KnowledgeAnsweringDeterministicExtractiveSettings(BaseModel):
    """Deterministic extractive answer-provider settings (Phase 5.6)."""

    max_excerpt_characters: int = 800
    max_statements_per_source: int = 2
    preserve_source_sentences: bool = True

    @field_validator("max_excerpt_characters", "max_statements_per_source")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value


class KnowledgeAnsweringSettings(BaseModel):
    """Grounded repository answering settings (Phase 5.6)."""

    enabled: bool = False
    provider: str = "deterministic_extractive"
    style: str = "concise"
    max_answer_characters: int = 12_000
    max_statements: int = 20
    minimum_supporting_sources: int = 1
    require_citations: bool = True
    fail_on_insufficient_evidence: bool = False
    include_evidence: bool = True
    include_retrieval_context: bool = False
    include_diagnostics: bool = True
    write_answer_artifact: bool = False
    answer_filename: str = "repository-grounded-answer.json"
    deterministic_extractive: KnowledgeAnsweringDeterministicExtractiveSettings = Field(
        default_factory=KnowledgeAnsweringDeterministicExtractiveSettings
    )

    @field_validator("provider", "style", mode="before")
    @classmethod
    def normalize_tokens(cls, value: object) -> str:
        return str(value).strip().lower()

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {
            "deterministic",
            "deterministic_extractive",
            "bedrock",
            "openai",
            "anthropic",
            "local_model",
        }
        if value not in allowed:
            raise ValueError(
                "knowledge.answering.provider must be one of "
                f"{sorted(allowed)}"
            )
        return value

    @field_validator("style")
    @classmethod
    def validate_style(cls, value: str) -> str:
        allowed = {
            "concise",
            "detailed",
            "findings_summary",
            "recommendation_summary",
            "architecture_explanation",
            "evidence_only",
        }
        if value not in allowed:
            raise ValueError(
                "knowledge.answering.style must be one of "
                f"{sorted(allowed)}"
            )
        return value

    @field_validator(
        "max_answer_characters",
        "max_statements",
        "minimum_supporting_sources",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("answer_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        compact = value.strip()
        if not compact or "/" in compact or "\\" in compact:
            raise ValueError("answer_filename must be a basename without path separators")
        return compact


class KnowledgeSettings(BaseModel):
    """Knowledge subsystem settings.

    ``directory`` configures the Phase 2 engineering knowledge store (SQLite +
    blobs). Phase 5 Repository Knowledge Layer settings:

    * ``enabled`` — reserved overall gate (Phase 5.1)
    * ``projection`` / ``chunking`` — Phase 5.2 document projection and chunking
    * ``embedding`` / ``indexing`` — Phase 5.3 embed + vector upsert
    * ``vector_store`` — memory or pgvector (Phase 5.4+)
    * ``retrieval`` — grounded context retrieval (Phase 5.5; default off)
    * ``answering`` — grounded answer engine (Phase 5.6; default off)

    Independent of report retention under ``reports/``.
    """

    directory: Path = Path(".codestrata/knowledge")
    enabled: bool = False
    projection: KnowledgeProjectionSettings = Field(
        default_factory=KnowledgeProjectionSettings
    )
    chunking: KnowledgeChunkingSettings = Field(default_factory=KnowledgeChunkingSettings)
    embedding: KnowledgeEmbeddingSettings = Field(
        default_factory=KnowledgeEmbeddingSettings
    )
    indexing: KnowledgeIndexingSettings = Field(default_factory=KnowledgeIndexingSettings)
    vector_store: KnowledgeVectorStoreSettings = Field(
        default_factory=KnowledgeVectorStoreSettings
    )
    retrieval: KnowledgeRetrievalSettings = Field(
        default_factory=KnowledgeRetrievalSettings
    )
    answering: KnowledgeAnsweringSettings = Field(
        default_factory=KnowledgeAnsweringSettings
    )


class McpToolsSettings(BaseModel):
    """Per-tool enablement for repository-intelligence MCP tools (Phase 5.7)."""

    repository_search: bool = True
    repository_answer: bool = True
    repository_findings: bool = True
    repository_recommendations: bool = True
    repository_assessments: bool = True
    repository_files: bool = True
    repository_architecture: bool = True
    repository_security: bool = True
    repository_dependencies: bool = True
    repository_tests: bool = True
    repository_cloud: bool = True
    repository_ai_readiness: bool = True
    repository_performance: bool = True
    repository_health: bool = True


class McpSettings(BaseModel):
    """FastMCP server settings (Phase 2C + Phase 5.7).

    Defaults keep the server disabled and bound to localhost. Not intended for
    untrusted public exposure or multi-user remote hosting in this phase.
    """

    enabled: bool = False
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    server_name: str = "codestrata"
    server_version: str | None = None
    max_result_characters: int = 50_000
    include_diagnostics: bool = True
    include_traceability: bool = True
    allow_artifact_paths: bool = False
    log_level: str = "INFO"
    tools: McpToolsSettings = Field(default_factory=McpToolsSettings)

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, value: str) -> str:
        compact = value.strip().lower()
        # Accept "http" as an alias for streamable-http.
        if compact == "http":
            return "streamable-http"
        allowed = {"stdio", "sse", "streamable-http"}
        if compact not in allowed:
            raise ValueError(
                "mcp.transport must be one of: stdio, streamable-http (http), sse"
            )
        return compact

    @field_validator("host", "server_name", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        compact = str(value).strip()
        if not compact:
            raise ValueError("must be a nonempty string")
        return compact

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("mcp.port must be between 1 and 65535")
        return value

    @field_validator("max_result_characters")
    @classmethod
    def validate_max_chars(cls, value: int) -> int:
        if value < 1:
            raise ValueError("mcp.max_result_characters must be positive")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        compact = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if compact not in allowed:
            raise ValueError(f"mcp.log_level must be one of {sorted(allowed)}")
        return compact


class PlatformArtifactPublishingSettings(BaseModel):
    """Opt-in assessment artifact publishing (Engine → Platform).

    Disabled by default. Each artifact type requires explicit enablement.
    Independent from anonymous telemetry settings.
    """

    enabled: bool = False
    publish_summary: bool = True
    publish_report_json: bool = False
    publish_report_html: bool = False
    publish_findings: bool = False
    publish_evidence_manifest: bool = False
    publish_knowledge_export: bool = False
    process_intelligence: bool = False
    max_artifact_bytes: int = 10_485_760

    @field_validator("max_artifact_bytes")
    @classmethod
    def validate_max_bytes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("platform.artifacts.max_artifact_bytes must be >= 1")
        return value


class PlatformIntegrationSettings(BaseModel):
    """Optional Commercial Platform ingestion (Engine → Platform).

    Disabled by default. When enabled, the Engine publishes repository and
    assessment metadata through the Platform REST ingestion contract after a
    successful local assessment. Failures never block report generation.
    """

    enabled: bool = False
    base_url: str = "http://127.0.0.1:8000"
    organization_id: str = ""
    workspace_id: str = ""
    auth_token: str | None = None
    auth_token_env: str | None = "CODESTRATA_PLATFORM_TOKEN"
    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    artifacts: PlatformArtifactPublishingSettings = Field(
        default_factory=PlatformArtifactPublishingSettings
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: object) -> str:
        compact = str(value).strip().rstrip("/")
        if not compact:
            raise ValueError("platform.base_url must be a nonempty string")
        return compact

    @field_validator("timeout_seconds", "retry_backoff_seconds")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("max_retries")
    @classmethod
    def validate_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("platform.max_retries must be >= 0")
        return value


class AgentsSettings(BaseModel):
    """Optional Agent Framework bounds.

    Omitted ``[agents]`` sections use conservative defaults. Model-provider
    settings remain under ``[ai]`` / ``[aws]``.
    """

    enabled: bool = True
    max_steps: int = 10
    max_findings: int = 100
    max_recommendations: int = 100
    max_components: int = 100
    dependency_depth: int = 2
    stop_on_blocking_validation: bool = True
    include_ai_context: bool = True
    fail_on_missing_required_artifact: bool = True

    @field_validator("max_steps")
    @classmethod
    def validate_max_steps(cls, value: int) -> int:
        if value < 1 or value > 20:
            raise ValueError("agents.max_steps must be between 1 and 20")
        return value

    @field_validator("max_findings", "max_recommendations", "max_components")
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("agent collection limits must be positive")
        return value

    @field_validator("dependency_depth")
    @classmethod
    def validate_dependency_depth(cls, value: int) -> int:
        if value < 1 or value > 3:
            raise ValueError("agents.dependency_depth must be between 1 and 3")
        return value


class IncrementalSettings(BaseModel):
    """Optional incremental assessment planning and execution bounds.

    ``rollout_mode`` defaults to ``off``. Neither legacy booleans nor rollout
    activate incremental execution for ``codestrata assess``. Hard safety fallbacks
    cannot be disabled. ``allow_ai_reuse`` must remain false in Phase 2F.3.
    """

    rollout_mode: str = "off"
    enabled: bool = False
    execution_enabled: bool = False
    max_changed_files: int = 100
    max_change_ratio: float = 0.30
    dependency_depth: int = 2
    max_impacted_components: int = 500
    max_impacted_findings: int = 500
    max_impacted_recommendations: int = 500
    allow_metadata_only_noop: bool = True
    require_complete_fingerprints: bool = True
    fallback_on_unknown_impact: bool = True
    fallback_on_unsupported_language: bool = True
    fallback_on_engine_change: bool = True
    allow_selective_scan: bool = True
    allow_graph_merge: bool = True
    allow_rule_reuse: bool = True
    allow_recommendation_reuse: bool = True
    allow_ai_reuse: bool = False
    fallback_on_step_failure: bool = True
    fallback_on_merge_conflict: bool = True
    fallback_on_validation_failure: bool = True
    validate_after_execution: bool = True
    persist_execution_records: bool = True
    enable_equivalence_check: bool = False
    max_explanations: int = 500
    max_equivalence_differences: int = 100
    fallback_on_metric_inconsistency: bool = True

    @field_validator(
        "max_changed_files",
        "max_impacted_components",
        "max_impacted_findings",
        "max_impacted_recommendations",
        "max_explanations",
        "max_equivalence_differences",
    )
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("incremental bounds must be positive")
        return value

    @field_validator("max_change_ratio")
    @classmethod
    def validate_change_ratio(cls, value: float) -> float:
        if value <= 0.0 or value > 1.0:
            raise ValueError("incremental.max_change_ratio must be in (0.0, 1.0]")
        return value

    @field_validator("dependency_depth")
    @classmethod
    def validate_dependency_depth(cls, value: int) -> int:
        if value < 1 or value > 3:
            raise ValueError("incremental.dependency_depth must be between 1 and 3")
        return value

    @field_validator("rollout_mode")
    @classmethod
    def validate_rollout_mode(cls, value: str) -> str:
        compact = value.strip().lower()
        allowed = {"off", "plan_only", "opt_in", "default_with_fallback"}
        if compact not in allowed:
            raise ValueError(f"incremental.rollout_mode must be one of {sorted(allowed)}")
        return compact

    @model_validator(mode="before")
    @classmethod
    def map_legacy_booleans(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        mode = data.get("rollout_mode")
        if mode is None or (isinstance(mode, str) and not mode.strip()):
            if data.get("execution_enabled"):
                return {**data, "rollout_mode": "opt_in"}
            if data.get("enabled"):
                return {**data, "rollout_mode": "plan_only"}
        return data

    @field_validator("require_complete_fingerprints", "fallback_on_unknown_impact")
    @classmethod
    def validate_hard_safety(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "incremental.require_complete_fingerprints and "
                "fallback_on_unknown_impact are hard safety conditions and must be true"
            )
        return value

    @field_validator(
        "fallback_on_step_failure",
        "fallback_on_merge_conflict",
        "fallback_on_validation_failure",
        "fallback_on_metric_inconsistency",
    )
    @classmethod
    def validate_execution_hard_safety(cls, value: bool) -> bool:
        if not value:
            raise ValueError("incremental execution fallback hard-safety flags must remain true")
        return value

    @field_validator("allow_ai_reuse")
    @classmethod
    def validate_ai_reuse_disabled(cls, value: bool) -> bool:
        if value:
            raise ValueError("incremental.allow_ai_reuse must be false in Phase 2F.3")
        return value

    @model_validator(mode="after")
    def validate_rollout_consistency(self) -> IncrementalSettings:
        mode = self.rollout_mode
        if mode == "off" and (self.enabled or self.execution_enabled):
            raise ValueError(
                "Conflicting incremental settings: rollout_mode=off with "
                "enabled/execution_enabled true"
            )
        if mode == "plan_only" and self.execution_enabled:
            raise ValueError("Conflicting incremental settings: plan_only with execution_enabled")
        return self


class EnterpriseSettings(BaseModel):
    """Optional Enterprise Knowledge Graph settings (disabled by default)."""

    enabled: bool = False
    workspace: str = "enterprise"
    schema_version: str = "codestrata.io/v1alpha1"
    persist_graph: bool = True
    link_repository_assessments: bool = True
    require_registered_repositories: bool = True
    allow_unresolved_repositories: bool = False
    unknown_fields: str = "error"
    max_manifest_files: int = 5000
    max_manifest_size_bytes: int = 1_048_576
    max_yaml_depth: int = 50
    max_graph_entities: int = 100_000
    max_graph_relationships: int = 500_000
    max_query_results: int = 500
    max_traversal_depth: int = 5
    max_dependency_paths: int = 100
    persist_manifest_snapshot: bool = True

    @field_validator(
        "max_manifest_files",
        "max_manifest_size_bytes",
        "max_yaml_depth",
        "max_graph_entities",
        "max_graph_relationships",
        "max_query_results",
        "max_traversal_depth",
        "max_dependency_paths",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("enterprise bounds must be positive")
        return value

    @field_validator("max_traversal_depth")
    @classmethod
    def validate_depth(cls, value: int) -> int:
        if value > 10:
            raise ValueError("enterprise.max_traversal_depth cannot exceed 10")
        return value

    @field_validator("unknown_fields")
    @classmethod
    def validate_unknown_fields(cls, value: str) -> str:
        compact = value.strip().lower()
        if compact not in {"error", "warn", "ignore"}:
            raise ValueError("enterprise.unknown_fields must be error|warn|ignore")
        return compact

    @model_validator(mode="after")
    def validate_resolution_policy(self) -> EnterpriseSettings:
        if self.require_registered_repositories and self.allow_unresolved_repositories:
            # Allowed combination: require attempt but permit unresolved as warning
            # when allow_unresolved_repositories is true — keep as-is.
            pass
        return self


class ArchitectureRuleToggle(BaseModel):
    """Per-rule enablement toggle (enabled when parent pack is active)."""

    enabled: bool = True


_DEFAULT_COMPOSITION_ROOT_MARKERS = (
    "cli",
    "main",
    "bootstrap",
    "boot",
    "entrypoint",
    "entrypoints",
    "__main__",
    "wiring",
    "assemble",
    "assembly",
)
_DEFAULT_REGISTRATION_MARKERS = (
    "registry",
    "registration",
    "di",
    "inject",
    "injector",
    "plugin",
    "plugins",
    "factory",
)


class ExcessiveCouplingRuleSettings(BaseModel):
    """Thresholds for architecture.excessive-cross-module-coupling."""

    enabled: bool = True
    outgoing_module_threshold: int = 8
    minimum_module_count: int = 5
    relative_multiplier: float = 2.0
    exclude_composition_roots: bool = True

    @field_validator("outgoing_module_threshold", "minimum_module_count")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("coupling thresholds must be positive integers")
        return value

    @field_validator("outgoing_module_threshold")
    @classmethod
    def validate_outgoing_cap(cls, value: int) -> int:
        if value > 10_000:
            raise ValueError("outgoing_module_threshold cannot exceed 10000")
        return value

    @field_validator("relative_multiplier")
    @classmethod
    def validate_relative(cls, value: float) -> float:
        if value < 1.0 or value > 20.0:
            raise ValueError("relative_multiplier must be in [1.0, 20.0]")
        return value


class ArchitectureUnitSelectionSettings(BaseModel):
    """Architectural-unit selection policy for Architecture Intelligence."""

    module_depth: int = 2
    composition_root_markers: list[str] = Field(
        default_factory=lambda: sorted(_DEFAULT_COMPOSITION_ROOT_MARKERS)
    )
    registration_markers: list[str] = Field(
        default_factory=lambda: sorted(_DEFAULT_REGISTRATION_MARKERS)
    )
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("module_depth")
    @classmethod
    def validate_depth(cls, value: int) -> int:
        if value < 1 or value > 8:
            raise ValueError("module_depth must be between 1 and 8")
        return value


class ComponentConcentrationRuleSettings(BaseModel):
    """Thresholds for architecture.component-concentration."""

    enabled: bool = True
    incident_edge_share_threshold: float = 0.30
    minimum_component_count: int = 5

    @field_validator("incident_edge_share_threshold")
    @classmethod
    def validate_share(cls, value: float) -> float:
        if value <= 0.0 or value > 1.0:
            raise ValueError("incident_edge_share_threshold must be in (0, 1]")
        return value

    @field_validator("minimum_component_count")
    @classmethod
    def validate_minimum(cls, value: int) -> int:
        if value < 1:
            raise ValueError("minimum_component_count must be a positive integer")
        return value


class ArchitectureRulesSettings(BaseModel):
    """Architecture Intelligence pack settings (disabled by default; Phase 4.2)."""

    enabled: bool = False
    unit_selection: ArchitectureUnitSelectionSettings = Field(
        default_factory=ArchitectureUnitSelectionSettings
    )
    dependency_cycle: ArchitectureRuleToggle = Field(default_factory=ArchitectureRuleToggle)
    invalid_dependency_direction: ArchitectureRuleToggle = Field(
        default_factory=ArchitectureRuleToggle
    )
    layer_boundary_violation: ArchitectureRuleToggle = Field(
        default_factory=ArchitectureRuleToggle
    )
    excessive_cross_module_coupling: ExcessiveCouplingRuleSettings = Field(
        default_factory=ExcessiveCouplingRuleSettings
    )
    component_concentration: ComponentConcentrationRuleSettings = Field(
        default_factory=ComponentConcentrationRuleSettings
    )
    framework_leakage: ArchitectureRuleToggle = Field(default_factory=ArchitectureRuleToggle)
    service_dependency_cycle: ArchitectureRuleToggle = Field(
        default_factory=ArchitectureRuleToggle
    )
    enterprise_standard_mismatch: ArchitectureRuleToggle = Field(
        default_factory=ArchitectureRuleToggle
    )


class TechnicalDebtComplexityLargeCallableSettings(BaseModel):
    """Thresholds for technical_debt.large-callable."""

    enabled: bool = True
    max_physical_lines: int = 50

    @field_validator("max_physical_lines")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1 or value > 100_000:
            raise ValueError("max_physical_lines must be in [1, 100000]")
        return value


class TechnicalDebtComplexityBranchingSettings(BaseModel):
    """Thresholds for technical_debt.excessive-branching."""

    enabled: bool = True
    max_branch_points: int = 10

    @field_validator("max_branch_points")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1 or value > 10_000:
            raise ValueError("max_branch_points must be in [1, 10000]")
        return value


class TechnicalDebtComplexityNestingSettings(BaseModel):
    """Thresholds for technical_debt.deep-nesting."""

    enabled: bool = True
    max_nesting_depth: int = 4

    @field_validator("max_nesting_depth")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("max_nesting_depth must be in [1, 100]")
        return value


class TechnicalDebtComplexityParametersSettings(BaseModel):
    """Thresholds for technical_debt.excessive-parameters."""

    enabled: bool = True
    max_parameters: int = 5

    @field_validator("max_parameters")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1 or value > 1000:
            raise ValueError("max_parameters must be in [1, 1000]")
        return value


class TechnicalDebtComplexityOversizedTypeSettings(BaseModel):
    """Thresholds for technical_debt.oversized-type."""

    enabled: bool = True
    max_physical_lines: int = 300

    @field_validator("max_physical_lines")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1 or value > 100_000:
            raise ValueError("max_physical_lines must be in [1, 100000]")
        return value


class TechnicalDebtComplexitySettings(BaseModel):
    """Complexity rule group under [rules.technical_debt.complexity]."""

    enabled: bool = True
    large_callable: TechnicalDebtComplexityLargeCallableSettings = Field(
        default_factory=TechnicalDebtComplexityLargeCallableSettings
    )
    excessive_branching: TechnicalDebtComplexityBranchingSettings = Field(
        default_factory=TechnicalDebtComplexityBranchingSettings
    )
    deep_nesting: TechnicalDebtComplexityNestingSettings = Field(
        default_factory=TechnicalDebtComplexityNestingSettings
    )
    excessive_parameters: TechnicalDebtComplexityParametersSettings = Field(
        default_factory=TechnicalDebtComplexityParametersSettings
    )
    oversized_type: TechnicalDebtComplexityOversizedTypeSettings = Field(
        default_factory=TechnicalDebtComplexityOversizedTypeSettings
    )


class TechnicalDebtRulesSettings(BaseModel):
    """Technical Debt Intelligence pack settings (disabled by default; Phase 4.3)."""

    enabled: bool = False
    complexity: TechnicalDebtComplexitySettings = Field(
        default_factory=TechnicalDebtComplexitySettings
    )


class DependencyRuleToggle(BaseModel):
    """Per-rule enablement under [rules.dependency]."""

    enabled: bool = True


class DependencyRulesSettings(BaseModel):
    """Dependency Intelligence pack settings (disabled by default; Phase 4.4.3)."""

    enabled: bool = False
    unresolved_version: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    mutable_version: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    unbounded_requirement: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    conflicting_exact_versions: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    duplicate_declaration: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )


class SecurityRulesSettings(BaseModel):
    """Security Intelligence pack settings (disabled by default; Phase 4.5.3)."""

    enabled: bool = False
    private_key_material: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    credential_literal: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    placeholder_credential: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    tls_verification_disabled: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    hostname_verification_disabled: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    authentication_disabled: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    permissive_cors_origin: DependencyRuleToggle = Field(
        default_factory=DependencyRuleToggle
    )
    debug_enabled: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)


class TestingRulesSettings(BaseModel):
    """Test Intelligence pack settings (disabled by default; Phase 4.6.3)."""

    enabled: bool = False
    test_001: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    test_002: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    test_003: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    test_005: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)


class CloudRulesSettings(BaseModel):
    """Cloud Intelligence pack settings (disabled by default; Phase 4.7.3)."""

    enabled: bool = False
    cloud_001: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_002: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_010: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_011: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_020: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_021: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_030: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_040: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_050: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_060: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    cloud_061: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)


class AiReadinessRulesSettings(BaseModel):
    """AI Readiness Intelligence pack settings (disabled by default; Phase 4.8.3)."""

    enabled: bool = False
    ai_001: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_002: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_003: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_010: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_011: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_020: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_021: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_022: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_030: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_031: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_032: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_040: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_041: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_050: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_051: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_060: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    ai_061: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)


class PerformanceRulesSettings(BaseModel):
    """Performance Intelligence pack settings (disabled by default; Phase 4.9.3)."""

    enabled: bool = False
    perf_001: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_002: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_003: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_010: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_011: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_020: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_021: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_030: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_031: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_032: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_040: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_041: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_050: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_051: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_052: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_060: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_061: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_070: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_071: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)
    perf_072: DependencyRuleToggle = Field(default_factory=DependencyRuleToggle)


class RulesSettings(BaseModel):
    """Shared Rule Platform settings (disabled by default; Phase 4.1)."""

    enabled: bool = False
    fail_on_rule_error: bool = False
    max_rules_per_run: int = 1000
    max_matches_per_rule: int = 1000
    max_total_matches: int = 10_000
    max_evidence_per_match: int = 100
    default_categories: list[str] = Field(default_factory=list)
    architecture: ArchitectureRulesSettings = Field(default_factory=ArchitectureRulesSettings)
    technical_debt: TechnicalDebtRulesSettings = Field(
        default_factory=TechnicalDebtRulesSettings
    )
    dependency: DependencyRulesSettings = Field(default_factory=DependencyRulesSettings)
    security: SecurityRulesSettings = Field(default_factory=SecurityRulesSettings)
    testing: TestingRulesSettings = Field(default_factory=TestingRulesSettings)
    cloud: CloudRulesSettings = Field(default_factory=CloudRulesSettings)
    ai_readiness: AiReadinessRulesSettings = Field(
        default_factory=AiReadinessRulesSettings
    )
    performance: PerformanceRulesSettings = Field(
        default_factory=PerformanceRulesSettings
    )

    @field_validator(
        "max_rules_per_run",
        "max_matches_per_rule",
        "max_total_matches",
        "max_evidence_per_match",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("rules bounds must be positive")
        return value

    @field_validator("max_rules_per_run")
    @classmethod
    def validate_max_rules(cls, value: int) -> int:
        if value > 100_000:
            raise ValueError("rules.max_rules_per_run cannot exceed 100000")
        return value

    @field_validator("max_total_matches")
    @classmethod
    def validate_max_matches(cls, value: int) -> int:
        if value > 1_000_000:
            raise ValueError("rules.max_total_matches cannot exceed 1000000")
        return value

    @model_validator(mode="after")
    def validate_architecture_requires_platform(self) -> RulesSettings:
        # Packs may be configured while platform disabled; assess ignores them.
        _ = self.architecture
        _ = self.technical_debt
        _ = self.dependency
        _ = self.security
        _ = self.testing
        _ = self.cloud
        _ = self.ai_readiness
        _ = self.performance
        return self


_DEFAULT_LANGUAGE_PROVIDER_PRECEDENCE = (
    "language.python.core",
    "language.java.core",
    "language.javascript.core",
    "language.php.core",
    "language.csharp.core",
)


class LanguageProviderToggle(BaseModel):
    """Enable/disable a single language evidence provider."""

    enabled: bool = True


class LanguageEvidenceProvidersSettings(BaseModel):
    """Provider selection and execution policy."""

    auto_detect: bool = True
    fail_fast: bool = False
    precedence: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_LANGUAGE_PROVIDER_PRECEDENCE)
    )

    @field_validator("precedence")
    @classmethod
    def validate_precedence(cls, value: list[str]) -> list[str]:
        known = set(_DEFAULT_LANGUAGE_PROVIDER_PRECEDENCE)
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            compact = item.strip().lower()
            if not compact:
                continue
            if compact not in known:
                raise ValueError(f"Unknown language evidence provider in precedence: {item}")
            if compact in seen:
                raise ValueError(f"Duplicate provider in precedence: {compact}")
            seen.add(compact)
            cleaned.append(compact)
        return cleaned or list(_DEFAULT_LANGUAGE_PROVIDER_PRECEDENCE)


class LanguageEvidenceSettings(BaseModel):
    """Language Evidence Provider pipeline (disabled by default; Phase 4.2.2)."""

    enabled: bool = False
    providers: LanguageEvidenceProvidersSettings = Field(
        default_factory=LanguageEvidenceProvidersSettings
    )
    python: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    java: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    javascript: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    php: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    csharp: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)


class ComplexityEvidenceSettings(BaseModel):
    """Structural complexity evidence collectors (Phase 4.3.2).

    Owned by the Language Evidence Platform. Default-enabled for explicit collect
    calls; not wired into Architecture Intelligence assessment.
    """

    enabled: bool = True
    python: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    java: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    php: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    csharp: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    max_files: int = 2000
    max_file_chars: int = 100_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("complexity evidence bounds must be positive")
        return value


class DependencyEvidenceSettings(BaseModel):
    """Declared-dependency manifest collectors (Phase 4.4.2).

    Owned by the Dependency Evidence Platform. Disabled by default.
    """

    enabled: bool = False
    maven: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    gradle: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    python: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    composer: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    nuget: LanguageProviderToggle = Field(default_factory=LanguageProviderToggle)
    max_files: int = 500
    max_file_chars: int = 500_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("dependency evidence bounds must be positive")
        return value


class RepositorySensitiveEvidenceSettings(BaseModel):
    """Repository-visible security-relevant evidence (Phase 4.5.2).

    Platform evidence — not owned by Security Intelligence. Disabled by default.
    Collects artifact and configuration literals only; no Findings or severity.
    """

    enabled: bool = False
    max_files: int = 500
    max_file_chars: int = 500_000
    max_file_bytes: int = 2_000_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars", "max_file_bytes")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repository-sensitive evidence bounds must be positive")
        return value


class RepositoryTestingEvidenceSettings(BaseModel):
    """Repository-observable testing structure evidence (Phase 4.6.2).

    Platform evidence — not owned by Test Intelligence. Disabled by default.
    Collects structure and configuration facts only; no Findings or execution.
    """

    enabled: bool = False
    max_files: int = 500
    max_file_chars: int = 500_000
    max_file_bytes: int = 2_000_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars", "max_file_bytes")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repository-testing evidence bounds must be positive")
        return value


class RepositoryCloudEvidenceSettings(BaseModel):
    """Repository-observable cloud technology evidence (Phase 4.7.2).

    Platform evidence — not owned by Cloud Intelligence. Disabled by default.
    Collects technology and deployment signals only; no Findings or readiness.
    """

    enabled: bool = False
    max_files: int = 500
    max_file_chars: int = 500_000
    max_file_bytes: int = 2_000_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars", "max_file_bytes")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repository-cloud evidence bounds must be positive")
        return value


class RepositoryAiReadinessEvidenceSettings(BaseModel):
    """Repository-observable AI-readiness evidence (Phase 4.8.2).

    Platform evidence — not owned by AI Readiness Intelligence. Disabled by
    default. Collects readiness signals only; no Findings or readiness scores.
    """

    enabled: bool = False
    max_files: int = 500
    max_file_chars: int = 500_000
    max_file_bytes: int = 2_000_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars", "max_file_bytes")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repository-ai-readiness evidence bounds must be positive")
        return value


class RepositoryPerformanceEvidenceSettings(BaseModel):
    """Repository-observable performance evidence (Phase 4.9.2).

    Platform evidence — not owned by Performance Intelligence. Disabled by
    default. Collects performance signals only; no Findings or performance scores.
    """

    enabled: bool = False
    max_files: int = 500
    max_file_chars: int = 500_000
    max_file_bytes: int = 2_000_000
    ignore_path_markers: list[str] = Field(
        default_factory=_default_ignore_path_markers_list
    )

    @field_validator("max_files", "max_file_chars", "max_file_bytes")
    @classmethod
    def validate_positive_bounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repository-performance evidence bounds must be positive")
        return value


class EvidenceSettings(BaseModel):
    """Evidence collection settings."""

    language: LanguageEvidenceSettings = Field(default_factory=LanguageEvidenceSettings)
    complexity: ComplexityEvidenceSettings = Field(
        default_factory=ComplexityEvidenceSettings
    )
    dependency: DependencyEvidenceSettings = Field(
        default_factory=DependencyEvidenceSettings
    )
    repository_sensitive: RepositorySensitiveEvidenceSettings = Field(
        default_factory=RepositorySensitiveEvidenceSettings
    )
    repository_testing: RepositoryTestingEvidenceSettings = Field(
        default_factory=RepositoryTestingEvidenceSettings
    )
    repository_cloud: RepositoryCloudEvidenceSettings = Field(
        default_factory=RepositoryCloudEvidenceSettings
    )
    repository_ai_readiness: RepositoryAiReadinessEvidenceSettings = Field(
        default_factory=RepositoryAiReadinessEvidenceSettings
    )
    repository_performance: RepositoryPerformanceEvidenceSettings = Field(
        default_factory=RepositoryPerformanceEvidenceSettings
    )


class ArchitectureConclusionPolicyToggles(BaseModel):
    """Per-policy enablement for Architecture Conclusions (Phase 4.2.3)."""

    boundary_integrity: bool = True
    cyclic_dependency_structure: bool = True
    broad_dependency_surface: bool = True
    framework_boundary_erosion: bool = True
    enterprise_nonconformance: bool = True
    positive_boundary_conformance: bool = False
    insufficient_evidence: bool = True


class ArchitectureConclusionAggregationSettings(BaseModel):
    group_by_scope: bool = True
    group_related_rules: bool = True
    preserve_standalone_findings: bool = True


class ArchitectureConclusionsSettings(BaseModel):
    """Architecture Conclusions layer (disabled by default; Phase 4.2.3)."""

    enabled: bool = False
    policies: ArchitectureConclusionPolicyToggles = Field(
        default_factory=ArchitectureConclusionPolicyToggles
    )
    aggregation: ArchitectureConclusionAggregationSettings = Field(
        default_factory=ArchitectureConclusionAggregationSettings
    )


class CloudAnalysisSettings(BaseModel):
    """Cloud Intelligence analysis gate (disabled by default; Phase 4.7.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class AiReadinessAnalysisSettings(BaseModel):
    """AI Readiness Intelligence analysis gate (disabled by default; Phase 4.8.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class PerformanceAnalysisSettings(BaseModel):
    """Performance Intelligence analysis gate (disabled by default; Phase 4.9.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class AnalysisRuntimeSettings(BaseModel):
    """Platform runtime performance controls (Phase 5.19)."""

    max_read_workers: int = Field(default=4, ge=1, le=32)
    shared_source_text_cache: bool = True
    max_source_files: int = Field(default=2000, ge=1, le=100_000)
    max_source_chars: int = Field(default=100_000, ge=1_024, le=5_000_000)
    capture_peak_rss: bool = True
    benchmark_collection: bool = Field(
        default=False,
        description=(
            "When true, write performance-benchmark.json for the run. "
            "Observational only — does not change assessment outputs."
        ),
    )


class AnalysisSettings(BaseModel):
    """Analysis enrichment settings (optional layers)."""

    architecture_conclusions: ArchitectureConclusionsSettings = Field(
        default_factory=ArchitectureConclusionsSettings
    )
    cloud: CloudAnalysisSettings = Field(default_factory=CloudAnalysisSettings)
    ai_readiness: AiReadinessAnalysisSettings = Field(
        default_factory=AiReadinessAnalysisSettings
    )
    performance: PerformanceAnalysisSettings = Field(
        default_factory=PerformanceAnalysisSettings
    )
    runtime: AnalysisRuntimeSettings = Field(default_factory=AnalysisRuntimeSettings)


class ArchitectureAssessmentSectionSettings(BaseModel):
    """Architecture assessment section integration (disabled by default; Phase 4.2.4)."""

    enabled: bool = False
    include_findings: bool = True
    include_conclusions: bool = True
    include_recommendation_groups: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True


class TechnicalDebtAssessmentSectionSettings(BaseModel):
    """Technical debt assessment section (disabled by default; Phase 4.3.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class DependencyAssessmentSectionSettings(BaseModel):
    """Dependency assessment section (disabled by default; Phase 4.4.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class SecurityAssessmentSectionSettings(BaseModel):
    """Security assessment section (disabled by default; Phase 4.5.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class TestingAssessmentSectionSettings(BaseModel):
    """Test assessment section (disabled by default; Phase 4.6.1)."""

    enabled: bool = False
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_execution_summary: bool = True
    include_synthesis: bool = True


class AssessmentSectionsSettings(BaseModel):
    architecture: ArchitectureAssessmentSectionSettings = Field(
        default_factory=ArchitectureAssessmentSectionSettings
    )
    technical_debt: TechnicalDebtAssessmentSectionSettings = Field(
        default_factory=TechnicalDebtAssessmentSectionSettings
    )
    dependency: DependencyAssessmentSectionSettings = Field(
        default_factory=DependencyAssessmentSectionSettings
    )
    security: SecurityAssessmentSectionSettings = Field(
        default_factory=SecurityAssessmentSectionSettings
    )
    testing: TestingAssessmentSectionSettings = Field(
        default_factory=TestingAssessmentSectionSettings
    )


class AssessmentSettings(BaseModel):
    """Formal assessment composition settings."""

    activation: str = "default"
    sections: AssessmentSectionsSettings = Field(
        default_factory=AssessmentSectionsSettings
    )

    @field_validator("activation")
    @classmethod
    def validate_activation(cls, value: str) -> str:
        compact = str(value or "").strip().lower()
        allowed = {"default", "minimal", "full", "custom"}
        if compact not in allowed:
            raise ValueError(
                f"assessment.activation must be one of {sorted(allowed)}, got {value!r}"
            )
        return compact


class ArchitectureReportSectionSettings(BaseModel):
    """Architecture section in HTML/JSON reports (disabled by default; Phase 4.2.5)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_metrics: bool = True
    include_conclusions: bool = True
    include_recommendation_groups: bool = True
    include_findings: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True
    include_strengths: bool = True


class TechnicalDebtReportSectionSettings(BaseModel):
    """Technical debt section in HTML/JSON reports (disabled by default; Phase 4.3.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_metrics: bool = True
    include_themes: bool = True
    include_hotspots: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_test_observation: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class DependencyReportSectionSettings(BaseModel):
    """Dependency section in HTML/JSON reports (disabled by default; Phase 4.4.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_landscape: bool = True
    include_production_health: bool = True
    include_test_observations: bool = True
    include_hotspots: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_coverage: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class SecurityReportSectionSettings(BaseModel):
    """Security section in HTML/JSON reports (disabled by default; Phase 4.5.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_coverage: bool = True
    include_findings: bool = True
    include_themes: bool = True
    include_hotspots: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_diagnostics: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class TestingReportSectionSettings(BaseModel):
    """Test section in HTML/JSON reports (disabled by default; Phase 4.6.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_coverage: bool = True
    include_inventory: bool = True
    include_execution_summary: bool = True
    include_themes: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_diagnostics: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class CloudReportSectionSettings(BaseModel):
    """Cloud section in HTML/JSON reports (disabled by default; Phase 4.7.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_coverage: bool = True
    include_inventory: bool = True
    include_execution_summary: bool = True
    include_themes: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_findings: bool = True
    include_diagnostics: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class AiReadinessReportSectionSettings(BaseModel):
    """AI Readiness section in HTML/JSON reports (disabled by default; Phase 4.8.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_coverage: bool = True
    include_inventory: bool = True
    include_execution_summary: bool = True
    include_themes: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_findings: bool = True
    include_diagnostics: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class PerformanceReportSectionSettings(BaseModel):
    """Performance section in HTML/JSON reports (disabled by default; Phase 4.9.6)."""

    enabled: bool = False
    include_executive_summary: bool = True
    include_coverage: bool = True
    include_inventory: bool = True
    include_execution_summary: bool = True
    include_themes: bool = True
    include_conclusions: bool = True
    include_recommendations: bool = True
    include_findings: bool = True
    include_diagnostics: bool = True
    include_limitations: bool = True
    include_traceability: bool = True


class RoadmapReportSectionSettings(BaseModel):
    """Modernization roadmap section in HTML/JSON reports (disabled by default; Phase 5.10)."""

    enabled: bool = False
    include_assumptions: bool = True
    include_limitations: bool = True
    include_evidence: bool = True


class ReportSectionsSettings(BaseModel):
    architecture: ArchitectureReportSectionSettings = Field(
        default_factory=ArchitectureReportSectionSettings
    )
    technical_debt: TechnicalDebtReportSectionSettings = Field(
        default_factory=TechnicalDebtReportSectionSettings
    )
    dependency: DependencyReportSectionSettings = Field(
        default_factory=DependencyReportSectionSettings
    )
    security: SecurityReportSectionSettings = Field(
        default_factory=SecurityReportSectionSettings
    )
    testing: TestingReportSectionSettings = Field(
        default_factory=TestingReportSectionSettings
    )
    cloud: CloudReportSectionSettings = Field(default_factory=CloudReportSectionSettings)
    ai_readiness: AiReadinessReportSectionSettings = Field(
        default_factory=AiReadinessReportSectionSettings
    )
    performance: PerformanceReportSectionSettings = Field(
        default_factory=PerformanceReportSectionSettings
    )
    roadmap: RoadmapReportSectionSettings = Field(
        default_factory=RoadmapReportSectionSettings
    )


class ReportSettings(BaseModel):
    """Customer report presentation settings."""

    sections: ReportSectionsSettings = Field(default_factory=ReportSectionsSettings)


class AnalyzerExtensionsSettings(BaseModel):
    """Opt-in third-party Phase 1 analyzers (empty = built-ins only)."""

    enabled: list[str] = Field(default_factory=list)


class RendererExtensionsSettings(BaseModel):
    """Opt-in report renderers beyond built-in HTML (empty = HTML default)."""

    enabled: list[str] = Field(default_factory=list)


class CliExtensionsSettings(BaseModel):
    """Optional deny list for discovered CLI extension entry points."""

    disabled: list[str] = Field(default_factory=list)


class McpExtensionsSettings(BaseModel):
    """Optional deny list for discovered MCP extension entry points."""

    disabled: list[str] = Field(default_factory=list)


class ExtensionsSettings(BaseModel):
    """Community-light extension configuration (absent section = CE defaults)."""

    api_version: str = "1"
    analyzers: AnalyzerExtensionsSettings = Field(
        default_factory=AnalyzerExtensionsSettings,
    )
    renderers: RendererExtensionsSettings = Field(
        default_factory=RendererExtensionsSettings,
    )
    cli: CliExtensionsSettings = Field(default_factory=CliExtensionsSettings)
    mcp: McpExtensionsSettings = Field(default_factory=McpExtensionsSettings)


class CodestrataSettings(BaseModel):
    """Top-level CodeStrata application settings."""

    repository: RepositorySettings
    profile: str = "community"
    workspace: WorkspaceSettings = Field(
        default_factory=WorkspaceSettings,
    )
    scan: ScanBoundarySettings = Field(default_factory=ScanBoundarySettings)
    knowledge: KnowledgeSettings = Field(
        default_factory=KnowledgeSettings,
    )
    static_analysis: StaticAnalysisSettings = Field(
        default_factory=StaticAnalysisSettings,
    )
    aws: AwsSettings = Field(default_factory=AwsSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    platform: PlatformIntegrationSettings = Field(
        default_factory=PlatformIntegrationSettings,
    )
    agents: AgentsSettings = Field(default_factory=AgentsSettings)
    incremental: IncrementalSettings = Field(default_factory=IncrementalSettings)
    enterprise: EnterpriseSettings = Field(default_factory=EnterpriseSettings)
    rules: RulesSettings = Field(default_factory=RulesSettings)
    evidence: EvidenceSettings = Field(default_factory=EvidenceSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    extensions: ExtensionsSettings = Field(default_factory=ExtensionsSettings)

    @field_validator("profile")
    @classmethod
    def validate_profile_name(cls, value: str) -> str:
        from codestrata.config.profiles import normalize_profile_name

        return normalize_profile_name(value)


def _location_category(location: tuple[str | int, ...]) -> str:
    """Classify a validation location for user-facing guidance."""

    parts = [str(part).lower() for part in location if isinstance(part, str)]
    if not parts:
        return "required"
    if parts[0] in {"ai", "aws"} or "bedrock" in parts or "openai" in parts:
        return "ai-only"
    if parts[0] in {"platform", "enterprise"}:
        return "platform-only"
    if parts[0] in {
        "knowledge",
        "mcp",
        "static_analysis",
        "extensions",
        "report",
        "incremental",
    }:
        return "optional"
    return "required"


def format_configuration_validation_error(
    error: Exception,
    *,
    config_path: Path,
) -> str:
    """Build an actionable configuration error message for CLI users."""

    if isinstance(error, ValidationError):
        lines: list[str] = [f"Invalid configuration in {config_path}:"]
        for item in error.errors():
            location = tuple(item.get("loc") or ())
            path = ".".join(str(part) for part in location) or "(root)"
            category = _location_category(location)
            message = str(item.get("msg") or "invalid value")
            lines.append(f"  • [{category}] {path}: {message}")
        lines.extend(
            (
                "",
                "Categories:",
                "  required     — needed for assess / doctor",
                "  optional     — subsystem toggles (safe defaults exist)",
                "  ai-only      — used only with assess --with-ai",
                "  platform-only — CodeStrata Platform deployments",
                "",
                "Fix: run `codestrata doctor` or `codestrata config validate`, "
                "or recreate defaults with `codestrata init --force`.",
            )
        )
        return "\n".join(lines)

    return (
        f"Invalid configuration in {config_path}: {error}\n\n"
        "Fix: check [repository] url/path and profile settings, then run "
        "`codestrata doctor` or `codestrata config validate`."
    )


def load_settings(
    config_path: Path,
    *,
    profile: str | None = None,
    validate_profile: bool = True,
    environ: dict[str, str] | None = None,
) -> CodestrataSettings:
    """Load CodeStrata settings from a TOML configuration file.

    Automatically loads a nearby ``.env`` file (if present) before reading
    configuration so environment-variable references such as
    ``CODESTRATA_GITHUB_TOKEN`` resolve without requiring ``source .env``.

    Precedence (Phase 5.20):

    ``CLI profile`` > ``CODESTRATA_PROFILE`` / related env overlays >
    ``codestrata.toml`` > execution-profile defaults.
    """

    from codestrata.config.profiles import (
        ConfigurationProfileError,
        merge_profile_configuration,
        raise_on_errors,
        validate_profile_settings,
    )

    resolved_config = config_path.expanduser()
    load_dotenv(start_directory=resolved_config.parent)
    load_dotenv(start_directory=Path.cwd())

    if not resolved_config.exists():
        raise FileNotFoundError(
            f"Configuration file does not exist: {resolved_config}\n\n"
            "Fix: create codestrata.toml in the project root (see README), or pass "
            "--config /path/to/codestrata.toml"
        )

    if not resolved_config.is_file():
        raise ValueError(f"Configuration path is not a file: {resolved_config}")

    with resolved_config.open("rb") as config_file:
        config_data = tomllib.load(config_file)

    try:
        merged, active_profile, _source = merge_profile_configuration(
            config_data,
            cli_profile=profile,
            environ=environ,
        )
        settings = CodestrataSettings.model_validate(merged)
    except ConfigurationProfileError:
        raise
    except Exception as error:
        raise ValueError(
            format_configuration_validation_error(error, config_path=resolved_config)
        ) from error

    if validate_profile:
        issues = validate_profile_settings(
            settings,
            profile=active_profile,
            environ=environ,
        )
        raise_on_errors(issues)
    return settings


def load_settings_resolution(
    config_path: Path,
    *,
    profile: str | None = None,
    validate_profile: bool = True,
    strict: bool = False,
    environ: dict[str, str] | None = None,
) -> tuple[CodestrataSettings, str, str, list[ConfigurationIssue]]:
    """Load settings and return profile metadata plus validation issues.

    Returns ``(settings, profile_name, profile_source, issues)``.
    """

    from codestrata.config.profiles import (
        ConfigurationProfileError,
        merge_profile_configuration,
        raise_on_errors,
        validate_profile_settings,
    )

    resolved_config = config_path.expanduser()
    load_dotenv(start_directory=resolved_config.parent)
    load_dotenv(start_directory=Path.cwd())

    if not resolved_config.exists():
        raise FileNotFoundError(
            f"Configuration file does not exist: {resolved_config}\n\n"
            "Fix: create codestrata.toml in the project root (see README), or pass "
            "--config /path/to/codestrata.toml"
        )
    if not resolved_config.is_file():
        raise ValueError(f"Configuration path is not a file: {resolved_config}")

    with resolved_config.open("rb") as config_file:
        config_data = tomllib.load(config_file)

    try:
        merged, active_profile, source = merge_profile_configuration(
            config_data,
            cli_profile=profile,
            environ=environ,
        )
        settings = CodestrataSettings.model_validate(merged)
    except ConfigurationProfileError:
        raise
    except Exception as error:
        raise ValueError(
            format_configuration_validation_error(error, config_path=resolved_config)
        ) from error

    issues = validate_profile_settings(
        settings,
        profile=active_profile,
        profile_source=source,
        strict=strict,
        environ=environ,
    )
    if validate_profile:
        raise_on_errors(issues)
    return settings, active_profile, source, issues


def configured_repository_source(settings: CodestrataSettings) -> str | None:
    """Return the configured assess/scan repository source, if any.

    Preference for configuration-only resolution: local ``path``, then ``url``.
    """

    if settings.repository.path:
        return settings.repository.path
    if settings.repository.url:
        return settings.repository.url
    return None


def is_github_repository_source(source: str) -> bool:
    """Return whether ``source`` is a GitHub repository URL."""

    try:
        parse_github_repository_url(source)
    except UnsupportedRepositoryUrlError:
        return False
    return True
