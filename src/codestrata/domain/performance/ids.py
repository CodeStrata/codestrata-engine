"""Performance Intelligence pack identifiers (Phase 4.9.3).

``performance.core`` hygiene rules consume AggregatedRepositoryPerformanceEvidence
only. Human aliases: PERF-001 … PERF-072 map to ``performance.perf-00N`` rule IDs
(Shared Rule Platform namespace.kebab form).
"""

from __future__ import annotations

PACK_ID = "performance.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Performance Intelligence Core"
PACK_DESCRIPTION = (
    "Performance Intelligence SharedRule pack for repository-observable "
    "performance signals. Rules consume AggregatedRepositoryPerformanceEvidence "
    "only and never re-read repository files, invent performance scores, or "
    "claim bottlenecks or modernization outcomes."
)

RULE_ID_PREFIX = "performance."
RULE_VERSION = "1.0.0"

TAXONOMY_NAMESPACE = "performance"

# Machine IDs (platform-valid). Documented aliases: PERF-001 … PERF-072.
RULE_DATA_ACCESS = "performance.perf-001"
RULE_MULTIPLE_DATA_ACCESS = "performance.perf-002"
RULE_DATA_ACCESS_WITHOUT_BATCHING = "performance.perf-003"
RULE_BLOCKING_SLEEP = "performance.perf-010"
RULE_SYNC_IO = "performance.perf-011"
RULE_CACHING = "performance.perf-020"
RULE_DATA_WITHOUT_CACHING = "performance.perf-021"
RULE_CONCURRENCY = "performance.perf-030"
RULE_EXECUTOR_CONFIG = "performance.perf-031"
RULE_CONCURRENCY_WITHOUT_CONFIG = "performance.perf-032"
RULE_RESOURCE_MGMT = "performance.perf-040"
RULE_RESOURCES_WITHOUT_MGMT = "performance.perf-041"
RULE_FRONTEND_BUNDLE = "performance.perf-050"
RULE_FRONTEND_LAZY = "performance.perf-051"
RULE_FRONTEND_LIMITED = "performance.perf-052"
RULE_OBSERVABILITY = "performance.perf-060"
RULE_WITHOUT_OBSERVABILITY = "performance.perf-061"
RULE_CONFIG_CONTROLS = "performance.perf-070"
RULE_BROAD_FOUNDATIONS = "performance.perf-071"
RULE_LIMITED_CONTROLS = "performance.perf-072"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_DATA_ACCESS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_BLOCKING_SLEEP,
    RULE_SYNC_IO,
    RULE_CACHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_CONCURRENCY,
    RULE_EXECUTOR_CONFIG,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_OBSERVABILITY,
    RULE_WITHOUT_OBSERVABILITY,
    RULE_CONFIG_CONTROLS,
    RULE_BROAD_FOUNDATIONS,
    RULE_LIMITED_CONTROLS,
)

PERFORMANCE_RULE_IDS: tuple[str, ...] = HYGIENE_RULE_IDS

DEFERRED_RULE_IDS: tuple[str, ...] = ()

RULE_ALIAS_TO_ID: dict[str, str] = {
    "PERF-001": RULE_DATA_ACCESS,
    "PERF-002": RULE_MULTIPLE_DATA_ACCESS,
    "PERF-003": RULE_DATA_ACCESS_WITHOUT_BATCHING,
    "PERF-010": RULE_BLOCKING_SLEEP,
    "PERF-011": RULE_SYNC_IO,
    "PERF-020": RULE_CACHING,
    "PERF-021": RULE_DATA_WITHOUT_CACHING,
    "PERF-030": RULE_CONCURRENCY,
    "PERF-031": RULE_EXECUTOR_CONFIG,
    "PERF-032": RULE_CONCURRENCY_WITHOUT_CONFIG,
    "PERF-040": RULE_RESOURCE_MGMT,
    "PERF-041": RULE_RESOURCES_WITHOUT_MGMT,
    "PERF-050": RULE_FRONTEND_BUNDLE,
    "PERF-051": RULE_FRONTEND_LAZY,
    "PERF-052": RULE_FRONTEND_LIMITED,
    "PERF-060": RULE_OBSERVABILITY,
    "PERF-061": RULE_WITHOUT_OBSERVABILITY,
    "PERF-070": RULE_CONFIG_CONTROLS,
    "PERF-071": RULE_BROAD_FOUNDATIONS,
    "PERF-072": RULE_LIMITED_CONTROLS,
}
