"""Enumerations shared by the CodeStrata application models."""

from enum import StrEnum


class TechnologyCategory(StrEnum):
    """Categories used to classify detected technologies."""

    LANGUAGE = "language"
    FRAMEWORK = "framework"
    BUILD_TOOL = "build_tool"
    DATABASE = "database"
    CLOUD = "cloud"
    LIBRARY = "library"
    RUNTIME = "runtime"
    CONTAINER = "container"
    TESTING = "testing"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class FindingCategory(StrEnum):
    """Categories used to classify repository findings."""

    TECHNOLOGY = "technology"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"
    CLOUD_READINESS = "cloud_readiness"
    AI_READINESS = "ai_readiness"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"
    OPERATIONAL_READINESS = "operational_readiness"
    RELIABILITY = "reliability"
    OTHER = "other"


class Severity(StrEnum):
    """Severity assigned to a finding."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingSource(StrEnum):
    """Indicates how a finding was produced."""

    DETERMINISTIC = "deterministic"
    STATIC_ANALYSIS = "static_analysis"
    EXTERNAL_STATIC_ANALYSIS = "external_static_analysis"
    AI = "ai"
    MANUAL = "manual"
    EXTERNAL_TOOL = "external_tool"


class Priority(StrEnum):
    """Priority assigned to a recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Effort(StrEnum):
    """Estimated implementation effort for a recommendation."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"
    UNKNOWN = "unknown"


class Risk(StrEnum):
    """Risk associated with deferring a recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationCategory(StrEnum):
    """Categories used to classify modernization recommendations."""

    SECURITY = "security"
    ARCHITECTURE = "architecture"
    CLOUD = "cloud"
    TESTING = "testing"
    BUILD = "build"
    DEPENDENCIES = "dependencies"
    CI_CD = "ci_cd"
