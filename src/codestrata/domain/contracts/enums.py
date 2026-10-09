"""Enumerations for the E01.1 launch measurement contract."""

from __future__ import annotations

from enum import StrEnum


class MetricStatus(StrEnum):
    """Shared metric/result status used by formula fixtures."""

    VALUE = "value"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    ERROR = "error"


class ConfidenceContractLevel(StrEnum):
    """Launch confidence taxonomy from the Measurement contract."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNSUPPORTED = "unsupported"


class ContributorRole(StrEnum):
    RANKING = "ranking"
    CONTEXT_ONLY = "context_only"


class OutcomeFamily(StrEnum):
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    QUALITY = "quality"
    MAINTAINABILITY = "maintainability"


class DriverKind(StrEnum):
    RULE = "rule"
    METRIC = "metric"


class DepthTier(StrEnum):
    """Launch language depth. Detection is not structural support."""

    DEEPEST_TARGET = "deepest_target"
    VERIFIED_RETAINED = "verified_retained"
    DETECTION_ONLY = "detection_only"
    UNSUPPORTED = "unsupported"


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class OutcomeMovement(StrEnum):
    INSUFFICIENT = "insufficient"
    MIXED = "mixed"
    DETERIORATED = "deteriorated"
    IMPROVED = "improved"
    STABLE = "stable"
    NOT_APPLICABLE = "not_applicable"


class ResultStatus(StrEnum):
    """Shared evaluation status from the Measurement contract."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class ExtractionStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class NetworkMode(StrEnum):
    OFFLINE = "offline"
    FORBIDDEN = "forbidden"


class SubjectKind(StrEnum):
    REPOSITORY = "repository"
    FILE = "file"
    SYMBOL = "symbol"
    COMPONENT = "component"
    DEPENDENCY = "dependency"
    FINDING = "finding"
    EVIDENCE = "evidence"
    BOUNDARY = "boundary"
    TEST = "test"


class OwnershipScope(StrEnum):
    REPOSITORY = "repository"
    COMPONENT = "component"
    FILE = "file"


class CoverageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    DISABLED = "disabled"
    SUPPRESSED = "suppressed"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class HotspotListKind(StrEnum):
    COMPLETE_COMPARABLE = "complete_comparable"
    PARTIAL_OR_UNKNOWN = "partial_or_unknown"


class SeverityOverrideSource(StrEnum):
    NONE = "none"
    APPROVED_CONFIG = "approved_config"
    CONTEXT_DEFAULT = "context_default"


class ExecutionPurpose(StrEnum):
    PRODUCTION = "production"
    PREVIEW = "preview"
    CANDIDATE_VALIDATION = "candidate_validation"


class InvocationKind(StrEnum):
    ASSESS = "assess"
    COMPARE = "compare"
    CANDIDATE_VALIDATE = "candidate_validate"
    PREVIEW = "preview"


class AdoptionLabel(StrEnum):
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ExportMode(StrEnum):
    FULL = "full"
    RESTRICTED = "restricted"
    NONE = "none"


class CauseAttribution(StrEnum):
    SOURCE_ONLY = "source_only"
    FEED_ONLY = "feed_only"
    CONFIGURATION_ONLY = "configuration_only"
    MIXED = "mixed"
    UNDETERMINED = "undetermined"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    NO_BASELINE = "no_baseline"
    UNKNOWN = "unknown"


class SuppliedContextProvenance(StrEnum):
    LOCAL_CLI = "local_cli"
    LOCAL_FILE = "local_file"
    LOCAL_FIXTURE = "local_fixture"


class RevisionAgreement(StrEnum):
    AGREES = "agrees"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class JobProgressState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    TERMINAL = "terminal"


class JobTerminalState(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    KILLED = "killed"


class ChangedInputDimension(StrEnum):
    SOURCE = "source"
    FEED = "feed"
    CONFIGURATION = "configuration"
    RULESET = "ruleset"
    ENGINE = "engine"
