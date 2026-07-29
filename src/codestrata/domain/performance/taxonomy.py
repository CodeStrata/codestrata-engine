"""Performance Intelligence taxonomy (Phase 4.9.1).

Repository-observable performance categories reserved for future rules and
assessment metadata. These values are methodology identifiers only.

This phase does not collect evidence, evaluate performance, score latency, or
emit findings for any category.
"""

from __future__ import annotations

from enum import StrEnum


class PerformanceCategory(StrEnum):
    """Bounded Performance Intelligence categories.

    Serialized values use the ``performance.<category>`` namespace (snake_case).
    Methodology aliases (for example ``query_patterns``) coerce via
    :func:`coerce_performance_category`.
    """

    INEFFICIENT_DATA_ACCESS = "performance.inefficient_data_access"
    BLOCKING_OPERATIONS = "performance.blocking_operations"
    UNBOUNDED_COLLECTION_PROCESSING = "performance.unbounded_collection_processing"
    EXCESSIVE_RESOURCE_CREATION = "performance.excessive_resource_creation"
    CACHING = "performance.caching"
    BATCHING_PAGINATION = "performance.batching_pagination"
    CONCURRENCY = "performance.concurrency"
    RESOURCE_MANAGEMENT = "performance.resource_management"
    FRONTEND_RENDERING_BUNDLE = "performance.frontend_rendering_bundle"
    OBSERVABILITY_PROFILING = "performance.observability_profiling"
    CONFIGURATION_CONTROLS = "performance.configuration_controls"
    SERIALIZATION = "performance.serialization"
    HOT_PATH_COUPLING = "performance.hot_path_coupling"
    MISCELLANEOUS = "performance.miscellaneous"
    UNKNOWN = "performance.unknown"


PERFORMANCE_CATEGORIES: tuple[PerformanceCategory, ...] = tuple(PerformanceCategory)

_ALIASES: dict[str, PerformanceCategory] = {
    "query_patterns": PerformanceCategory.INEFFICIENT_DATA_ACCESS,
    "performance.query_patterns": PerformanceCategory.INEFFICIENT_DATA_ACCESS,
    "blocking_synchronous_execution": PerformanceCategory.BLOCKING_OPERATIONS,
    "performance.blocking_synchronous_execution": (PerformanceCategory.BLOCKING_OPERATIONS),
    "excessive_object_resource_creation": (PerformanceCategory.EXCESSIVE_RESOURCE_CREATION),
    "performance.excessive_object_resource_creation": (
        PerformanceCategory.EXCESSIVE_RESOURCE_CREATION
    ),
    "concurrency_async": PerformanceCategory.CONCURRENCY,
    "performance.concurrency_async": PerformanceCategory.CONCURRENCY,
    "connection_resource_management": PerformanceCategory.RESOURCE_MANAGEMENT,
    "performance.connection_resource_management": (PerformanceCategory.RESOURCE_MANAGEMENT),
    "caching_foundations": PerformanceCategory.CACHING,
    "performance.caching_foundations": PerformanceCategory.CACHING,
}


def coerce_performance_category(value: object) -> PerformanceCategory:
    """Map a raw taxonomy value to a category, defaulting unknown inputs safely."""

    if isinstance(value, PerformanceCategory):
        return value
    text = str(value or "").strip()
    if not text:
        return PerformanceCategory.UNKNOWN
    try:
        return PerformanceCategory(text)
    except ValueError:
        pass
    normalized = text.replace("-", "_")
    alias = _ALIASES.get(normalized) or _ALIASES.get(normalized.removeprefix("performance."))
    if alias is not None:
        return alias
    bare = (
        normalized
        if normalized.startswith("performance.")
        else f"performance.{normalized.removeprefix('performance.')}"
    )
    alias = _ALIASES.get(bare)
    if alias is not None:
        return alias
    try:
        return PerformanceCategory(bare)
    except ValueError:
        return PerformanceCategory.UNKNOWN
