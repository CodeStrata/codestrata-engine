"""Dependency Evidence enumerations (Phase 4.4.2).

Declaration kinds are evidence-layer concepts and must remain separate from
Dependency Intelligence ``DependencyRole`` taxonomy.
"""

from __future__ import annotations

from enum import StrEnum


class DependencyEcosystem(StrEnum):
    MAVEN = "maven"
    GRADLE = "gradle"
    PYTHON = "python"
    COMPOSER = "composer"
    NUGET = "nuget"
    UNKNOWN = "unknown"


class DependencyManifestType(StrEnum):
    POM_XML = "pom.xml"
    BUILD_GRADLE = "build.gradle"
    BUILD_GRADLE_KTS = "build.gradle.kts"
    PYPROJECT_TOML = "pyproject.toml"
    REQUIREMENTS_TXT = "requirements.txt"
    COMPOSER_JSON = "composer.json"
    CSPROJ = "csproj"
    PACKAGES_CONFIG = "packages.config"
    DIRECTORY_PACKAGES_PROPS = "Directory.Packages.props"
    PACKAGES_LOCK_JSON = "packages.lock.json"
    UNKNOWN = "unknown"


class DependencyDeclarationKind(StrEnum):
    """Declared dependency semantics (not engineering roles)."""

    RUNTIME = "runtime"
    DEVELOPMENT = "development"
    TEST = "test"
    BUILD = "build"
    PLUGIN = "plugin"
    PLATFORM = "platform"
    OPTIONAL = "optional"
    DEPENDENCY_MANAGEMENT = "dependency_management"
    UNKNOWN = "unknown"


class DependencyParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SKIPPED = "skipped"


class DependencyEvidenceAvailability(StrEnum):
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class DependencyVersionResolutionStatus(StrEnum):
    """Local version-expression resolution outcome for Dependency Evidence.

    Distinguishes proven absence from collector coverage gaps:

    - ``resolved`` — expression resolved from a supported local contract
    - ``proven_unresolved`` — supported local contract was inspected and the
      expression remains unresolved
    - ``unsupported_resolution`` — resolution mechanism was not inspected or is
      outside the supported contract (diagnostic only; not a proven absence)
    - ``not_applicable`` — no version expression / version not required
    """

    RESOLVED = "resolved"
    PROVEN_UNRESOLVED = "proven_unresolved"
    UNSUPPORTED_RESOLUTION = "unsupported_resolution"
    NOT_APPLICABLE = "not_applicable"
