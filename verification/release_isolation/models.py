"""Typed records for integration, hotfix and prerelease isolation (E00.3)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


class LaneKind(StrEnum):
    INTEGRATION = "integration"
    STORY = "story"
    MAINTENANCE = "maintenance"
    HOTFIX = "hotfix"
    UNKNOWN = "unknown"


class NamespaceKind(StrEnum):
    CANDIDATE = "candidate"
    VERSIONED_CANDIDATE = "versioned_candidate"
    LIVE = "live"
    ROLLBACK_ONLY = "rollback_only"
    SNAPSHOT = "snapshot"
    FORBIDDEN = "forbidden"
    UNSUPPORTED = "unsupported"


class HotfixAction(StrEnum):
    LAND_ON_MAINTENANCE = "land_on_maintenance"
    BACKPORT_TO_NEXT = "backport_to_next"
    AUTO_PROMOTE_NEXT_TO_MAINTENANCE = "auto_promote_next_to_maintenance"
    MOVE_STABLE_TAG = "move_stable_tag"
    REWRITE_ROLLBACK_ARTIFACT = "rewrite_rollback_artifact"


@dataclass(frozen=True, slots=True)
class IsolationLanes:
    integration: str
    maintenance: str
    story_prefix: str
    hotfix_prefix: str


@dataclass(frozen=True, slots=True)
class CandidateNamespaces:
    venv: str
    output: str
    versioned_output_template: str
    quality_logs: str
    rollback_venv: str
    live_output_forbidden: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RollbackArtifact:
    name: str
    version: str
    sha256: str
    notes: str


@dataclass(frozen=True, slots=True)
class IsolationPolicy:
    lanes: IsolationLanes
    namespaces: CandidateNamespaces
    rollback: RollbackArtifact
    required_push_glob: str
    ordinary_ci_workflow: str


@dataclass(frozen=True, slots=True)
class PushPatternEvidence:
    workflow_path: str
    patterns: tuple[str, ...]
    covers_required_glob: bool
    integration_ref_matches: bool
    story_ref_matches: bool
    status: CheckStatus
    reason: str


@dataclass(frozen=True, slots=True)
class OrdinaryMergeEvidence:
    status: CheckStatus
    workflows_considered: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidatePlan:
    venv_kind: NamespaceKind
    output_kind: NamespaceKind
    status: CheckStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HotfixPlan:
    action: HotfixAction
    source_lane: str
    dest_lane: str
    recorded: bool
    status: CheckStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IsolationInspection:
    policy: IsolationPolicy
    push: PushPatternEvidence
    ordinary_merge: OrdinaryMergeEvidence
    status: CheckStatus
    notes: tuple[str, ...]
