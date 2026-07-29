"""Standard limitations for repository-cloud evidence."""

from __future__ import annotations

from codestrata.domain.evidence.repository_cloud.enums import (
    RepositoryCloudLimitationCategory,
)
from codestrata.domain.evidence.repository_cloud.identifiers import make_limitation_id
from codestrata.domain.evidence.repository_cloud.models import RepositoryCloudLimitation

_STANDARD: tuple[tuple[RepositoryCloudLimitationCategory, str], ...] = (
    (
        RepositoryCloudLimitationCategory.REPOSITORY_SNAPSHOT_ONLY,
        "Repository snapshot only.",
    ),
    (
        RepositoryCloudLimitationCategory.NO_CLOUD_RUNTIME,
        "Cloud provider APIs and live environments are not queried.",
    ),
    (
        RepositoryCloudLimitationCategory.NO_PROVIDER_API,
        "Cloud account configuration and permissions are not inspected.",
    ),
    (
        RepositoryCloudLimitationCategory.NO_DEPLOYMENT_EXECUTION,
        "CI/CD and GitOps workflows are not executed.",
    ),
    (
        RepositoryCloudLimitationCategory.DETECTION_BOUNDED,
        "Technology detection is limited to supported filename conventions and "
        "bounded content markers.",
    ),
    (
        RepositoryCloudLimitationCategory.NO_READINESS_SCORE,
        "No cloud readiness score or grade is produced.",
    ),
    (
        RepositoryCloudLimitationCategory.NO_COST_OR_SECURITY_JUDGMENT,
        "Cost, security posture, and architectural fitness are not judged.",
    ),
    (
        RepositoryCloudLimitationCategory.GENERATED_VENDOR_EXCLUSIONS,
        "Generated, vendored, binary, unsupported, or oversized files may be excluded.",
    ),
    (
        RepositoryCloudLimitationCategory.MANAGED_SERVICE_CONTENT_BOUNDED,
        "Managed-service detection relies on IaC/config content markers and may "
        "miss SDK-only usage.",
    ),
)


def standard_limitations() -> tuple[RepositoryCloudLimitation, ...]:
    return tuple(
        RepositoryCloudLimitation(
            limitation_id=make_limitation_id(category=category.value, summary=summary),
            category=category,
            summary=summary,
        )
        for category, summary in _STANDARD
    )
