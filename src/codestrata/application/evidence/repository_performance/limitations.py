"""Standard limitations for repository performance evidence."""

from __future__ import annotations

from codestrata.domain.evidence.repository_performance.enums import (
    RepositoryPerformanceLimitationCategory,
)
from codestrata.domain.evidence.repository_performance.identifiers import make_limitation_id
from codestrata.domain.evidence.repository_performance.models import (
    RepositoryPerformanceLimitation,
)

_STANDARD: tuple[tuple[RepositoryPerformanceLimitationCategory, str], ...] = (
    (
        RepositoryPerformanceLimitationCategory.REPOSITORY_SNAPSHOT_ONLY,
        "Repository snapshot only.",
    ),
    (
        RepositoryPerformanceLimitationCategory.NO_RUNTIME_PROFILING,
        "Runtime profiling and production metrics are not collected.",
    ),
    (
        RepositoryPerformanceLimitationCategory.NO_LOAD_TESTING,
        "Load testing and stress scenarios are not executed.",
    ),
    (
        RepositoryPerformanceLimitationCategory.NO_PERFORMANCE_SCORE,
        "No performance score or grade is produced.",
    ),
    (
        RepositoryPerformanceLimitationCategory.DETECTION_BOUNDED,
        "Technology detection is limited to supported filename conventions and "
        "bounded content markers.",
    ),
    (
        RepositoryPerformanceLimitationCategory.NO_LIVE_METRICS,
        "Live latency, throughput, and resource utilization metrics are not queried.",
    ),
    (
        RepositoryPerformanceLimitationCategory.GENERATED_VENDOR_EXCLUSIONS,
        "Generated, vendored, binary, unsupported, or oversized files may be excluded.",
    ),
    (
        RepositoryPerformanceLimitationCategory.CONTENT_MARKER_BOUNDED,
        "Content confirmation relies on bounded markers and may miss SDK-only usage.",
    ),
)


def standard_limitations() -> tuple[RepositoryPerformanceLimitation, ...]:
    return tuple(
        RepositoryPerformanceLimitation(
            limitation_id=make_limitation_id(category=category.value, summary=summary),
            category=category,
            summary=summary,
        )
        for category, summary in _STANDARD
    )
