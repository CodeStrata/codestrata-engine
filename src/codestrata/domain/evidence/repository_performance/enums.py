"""Repository performance evidence enums (Phase 4.9.2).

Technology-neutral taxonomy for repository-observable performance
artifacts. Not a Performance Intelligence capability enum and not Findings.
"""

from __future__ import annotations

from enum import StrEnum


class PerformanceEvidenceFamily(StrEnum):
    DATA_ACCESS = "data_access"
    BLOCKING_OPERATIONS = "blocking_operations"
    CACHING = "caching"
    CONCURRENCY_ASYNC = "concurrency_async"
    RESOURCE_MANAGEMENT = "resource_management"
    FRONTEND_PERFORMANCE = "frontend_performance"
    OBSERVABILITY_PROFILING = "observability_profiling"
    CONFIGURATION_CONTROLS = "configuration_controls"
    UNKNOWN = "unknown"


class PerformanceDataAccessKind(StrEnum):
    JPA = "jpa"
    HIBERNATE = "hibernate"
    SPRING_DATA = "spring_data"
    JDBC = "jdbc"
    ENTITY_FRAMEWORK = "entity_framework"
    DAPPER = "dapper"
    PRISMA = "prisma"
    SEQUELIZE = "sequelize"
    UNKNOWN = "unknown"


class PerformanceBlockingKind(StrEnum):
    THREAD_SLEEP = "thread_sleep"
    SYNC_HTTP_CLIENT = "sync_http_client"
    BLOCKING_DB_CALL = "blocking_db_call"
    BLOCKING_FILE_IO = "blocking_file_io"
    UNKNOWN = "unknown"


class PerformanceCachingKind(StrEnum):
    SPRING_CACHE = "spring_cache"
    CAFFEINE = "caffeine"
    REDIS = "redis"
    EHCACHE = "ehcache"
    CACHE_MANAGER = "cache_manager"
    UNKNOWN = "unknown"


class PerformanceConcurrencyKind(StrEnum):
    COMPLETABLE_FUTURE = "completable_future"
    EXECUTOR_SERVICE = "executor_service"
    VIRTUAL_THREADS = "virtual_threads"
    REACTOR = "reactor"
    RXJAVA = "rxjava"
    ASYNC_AWAIT = "async_await"
    TPL = "tpl"
    UNKNOWN = "unknown"


class PerformanceResourceKind(StrEnum):
    CONNECTION_POOL = "connection_pool"
    HIKARICP = "hikaricp"
    APACHE_DBCP = "apache_dbcp"
    TRY_WITH_RESOURCES = "try_with_resources"
    IDISPOSABLE = "idisposable"
    UNKNOWN = "unknown"


class PerformanceFrontendKind(StrEnum):
    LAZY_LOADING = "lazy_loading"
    CODE_SPLITTING = "code_splitting"
    WEBPACK = "webpack"
    VITE = "vite"
    BUNDLE_CONFIG = "bundle_config"
    UNKNOWN = "unknown"


class PerformanceObservabilityKind(StrEnum):
    MICROMETER = "micrometer"
    OPENTELEMETRY = "opentelemetry"
    PROMETHEUS = "prometheus"
    PROFILING = "profiling"
    TRACING = "tracing"
    UNKNOWN = "unknown"


class PerformanceConfigurationKind(StrEnum):
    THREAD_POOL = "thread_pool"
    EXECUTOR_CONFIG = "executor_config"
    CACHE_CONFIG = "cache_config"
    DATASOURCE_CONFIG = "datasource_config"
    TIMEOUT_CONFIG = "timeout_config"
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


class PerformanceDiscoveryBasis(StrEnum):
    EXACT_FILENAME = "exact_filename"
    FILENAME_PATTERN = "filename_pattern"
    EXTENSION = "extension"
    DIRECTORY_CONVENTION = "directory_convention"
    CONTENT_MARKER = "content_marker"
    STRUCTURED_CONTENT = "structured_content"
    DEPENDENCY_DECLARATION = "dependency_declaration"
    CONFIG_MARKER = "config_marker"


class RepositoryPerformanceParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RepositoryPerformanceLimitationCategory(StrEnum):
    REPOSITORY_SNAPSHOT_ONLY = "repository-snapshot-only"
    NO_RUNTIME_PROFILING = "no-runtime-profiling"
    NO_LOAD_TESTING = "no-load-testing"
    NO_PERFORMANCE_SCORE = "no-performance-score"
    DETECTION_BOUNDED = "detection-bounded"
    GENERATED_VENDOR_EXCLUSIONS = "generated-vendor-exclusions"
    CONTENT_MARKER_BOUNDED = "content-marker-bounded"
    NO_LIVE_METRICS = "no-live-metrics"
    OTHER = "other"
