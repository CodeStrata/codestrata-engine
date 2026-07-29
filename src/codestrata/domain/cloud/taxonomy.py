"""Cloud Intelligence taxonomy (Phase 4.7.1).

Repository-observable cloud readiness categories for future rules and
assessment metadata. These values are methodology identifiers only.

This phase does not detect cloud providers, evaluate readiness, or emit
findings for any category.
"""

from __future__ import annotations

from enum import StrEnum


class CloudCategory(StrEnum):
    """Bounded Cloud Intelligence categories.

    Serialized values use the ``cloud.<category>`` namespace (snake_case).
    Methodology taxonomy rows that use kebab-case coerce via
    :func:`coerce_cloud_category`.
    """

    EXTERNALIZED_CONFIGURATION = "cloud.externalized_configuration"
    STATELESSNESS = "cloud.statelessness"
    PORTABILITY = "cloud.portability"
    CONTAINER_READINESS = "cloud.container_readiness"
    MANAGED_SERVICE_COMPATIBILITY = "cloud.managed_service_compatibility"
    DEPLOYMENT_AUTOMATION = "cloud.deployment_automation"
    CONFIGURATION = "cloud.configuration"
    RUNTIME = "cloud.runtime"
    MISCELLANEOUS = "cloud.miscellaneous"
    UNKNOWN = "cloud.unknown"


CLOUD_CATEGORIES: tuple[CloudCategory, ...] = tuple(CloudCategory)


def coerce_cloud_category(value: object) -> CloudCategory:
    """Map a raw taxonomy value to a category, defaulting unknown inputs safely."""

    if isinstance(value, CloudCategory):
        return value
    text = str(value or "").strip()
    if not text:
        return CloudCategory.UNKNOWN
    try:
        return CloudCategory(text)
    except ValueError:
        pass
    normalized = text.replace("-", "_")
    bare = (
        normalized
        if normalized.startswith("cloud.")
        else f"cloud.{normalized.removeprefix('cloud.')}"
    )
    try:
        return CloudCategory(bare)
    except ValueError:
        return CloudCategory.UNKNOWN
