"""Standard limitations for repository AI-readiness evidence."""

from __future__ import annotations

from codestrata.domain.evidence.repository_ai_readiness.enums import (
    RepositoryAiReadinessLimitationCategory,
)
from codestrata.domain.evidence.repository_ai_readiness.identifiers import make_limitation_id
from codestrata.domain.evidence.repository_ai_readiness.models import (
    RepositoryAiReadinessLimitation,
)

_STANDARD: tuple[tuple[RepositoryAiReadinessLimitationCategory, str], ...] = (
    (
        RepositoryAiReadinessLimitationCategory.REPOSITORY_SNAPSHOT_ONLY,
        "Repository snapshot only.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.NO_AI_EXECUTION,
        "AI models, agents, and prompts are not executed.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.NO_MODEL_RUNTIME,
        "Live model endpoints and hosted AI services are not queried.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.NO_AGENT_EXECUTION,
        "Workflows, agents, and MCP tools are not invoked.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.DETECTION_BOUNDED,
        "Technology detection is limited to supported filename conventions and "
        "bounded content markers.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.NO_READINESS_SCORE,
        "No AI readiness score or grade is produced.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.NO_RAG_QUALITY_JUDGMENT,
        "RAG quality, retrieval effectiveness, and governance fitness are not judged.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.GENERATED_VENDOR_EXCLUSIONS,
        "Generated, vendored, binary, unsupported, or oversized files may be excluded.",
    ),
    (
        RepositoryAiReadinessLimitationCategory.CONTENT_MARKER_BOUNDED,
        "Content confirmation relies on bounded markers and may miss SDK-only usage.",
    ),
)


def standard_limitations() -> tuple[RepositoryAiReadinessLimitation, ...]:
    return tuple(
        RepositoryAiReadinessLimitation(
            limitation_id=make_limitation_id(category=category.value, summary=summary),
            category=category,
            summary=summary,
        )
        for category, summary in _STANDARD
    )
