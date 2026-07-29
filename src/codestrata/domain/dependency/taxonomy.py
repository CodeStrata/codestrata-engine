"""Dependency engineering-role taxonomy (Phase 4.4.1).

Technology-neutral roles for Dependency Intelligence. Package-manager concepts
(Maven scopes, npm ``devDependencies``, Python extras, etc.) must not appear
here — those belong to Dependency Evidence normalization later.

These values are methodology identifiers for future rules and assessment
metadata. This phase does not classify packages.
"""

from __future__ import annotations

from enum import StrEnum


class DependencyRole(StrEnum):
    """Bounded engineering dependency roles.

    Serialized values use the ``dependency.<role>`` namespace so artifacts remain
    extensible without colliding with package-manager vocabularies.
    """

    RUNTIME_FRAMEWORK = "dependency.runtime_framework"
    RUNTIME_LIBRARY = "dependency.runtime_library"
    BUILD_TOOL = "dependency.build_tool"
    BUILD_PLUGIN = "dependency.build_plugin"
    TEST_FRAMEWORK = "dependency.test_framework"
    TEST_LIBRARY = "dependency.test_library"
    PERSISTENCE = "dependency.persistence"
    DATABASE_DRIVER = "dependency.database_driver"
    MESSAGING = "dependency.messaging"
    SERIALIZATION = "dependency.serialization"
    LOGGING = "dependency.logging"
    OBSERVABILITY = "dependency.observability"
    NETWORKING = "dependency.networking"
    CLOUD_SDK = "dependency.cloud_sdk"
    SECURITY_LIBRARY = "dependency.security_library"
    INTERNAL_LIBRARY = "dependency.internal_library"
    DEVELOPMENT_TOOL = "dependency.development_tool"
    THIRD_PARTY_LIBRARY = "dependency.third_party_library"
    UNKNOWN = "dependency.unknown"


# Stable ordered tuple for deterministic iteration / serialization helpers.
DEPENDENCY_ROLES: tuple[DependencyRole, ...] = tuple(DependencyRole)


def coerce_dependency_role(value: object) -> DependencyRole:
    """Map a raw taxonomy value to a role, defaulting unknown inputs safely."""

    if isinstance(value, DependencyRole):
        return value
    text = str(value or "").strip()
    if not text:
        return DependencyRole.UNKNOWN
    try:
        return DependencyRole(text)
    except ValueError:
        pass
    # Accept bare role tokens without the namespace prefix.
    bare = text if text.startswith("dependency.") else f"dependency.{text}"
    try:
        return DependencyRole(bare)
    except ValueError:
        return DependencyRole.UNKNOWN
