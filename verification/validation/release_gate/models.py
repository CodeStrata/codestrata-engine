"""Typed records for E15.3 release-gate review."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from verification.validation.models import CheckStatus, CorpusTier


class ReviewDecision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    NOT_YET_DUE = "NOT_YET_DUE"


@dataclass(frozen=True, slots=True)
class CheckpointGate:
    id: str
    ledger: str


@dataclass(frozen=True, slots=True)
class OutOfScopeException:
    id: str
    scope: str
    rationale: str
    requires_independent_review: bool


@dataclass(frozen=True, slots=True)
class ReviewedException:
    id: str
    gate_or_story: str
    scope: str
    rationale: str
    reviewed: bool
    reviewer: str
    review_date: str


@dataclass(frozen=True, slots=True)
class ReleaseGatePolicy:
    package_revision: str
    story: str
    measurement_id: str
    required_checkpoint_gates: tuple[CheckpointGate, ...]
    required_story_ledgers: tuple[str, ...]
    integrated_status_markers: tuple[str, ...]
    blocked_status_markers: tuple[str, ...]
    out_of_scope_exceptions: tuple[OutOfScopeException, ...]
    remote_tier_env: str
    minimum_external_pins: int
    five_repos_do_not_replace_fifty: bool
    m33_proposed_budgets: dict[str, str | bool]


@dataclass(frozen=True, slots=True)
class GateLedgerEntry:
    gate_id: str
    ledger_path: str
    present: bool
    decision: ReviewDecision
    detail: str


@dataclass(frozen=True, slots=True)
class StoryPrerequisite:
    story_id: str
    ledger_path: str
    present: bool
    status: ReviewDecision
    detail: str


@dataclass(frozen=True, slots=True)
class RepositoryResult:
    tier: CorpusTier
    repository_id: str
    pin_sha: str
    status: CheckStatus
    detail: str
    wall_seconds: float | None = None
    peak_rss_bytes: int | None = None
    semantic_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ConfusionMatrixRow:
    group: str
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    unknown: int
    unexplained_unknown: int
    precision: str | None
    recall: str | None
    promotion_blocked: bool


@dataclass(frozen=True, slots=True)
class ResourceEnvelope:
    host_cpu_count: int
    proposed_le_10k: str
    proposed_le_100k: str
    host_note: str
    budgets_published: bool
    corpus_pin_digest: str


@dataclass(frozen=True, slots=True)
class ReleaseGateReport:
    ok: bool
    decision: ReviewDecision
    candidate_sha: str
    dirty_inventory: str
    corpus_manifest_ok: bool
    regression_harness_ok: bool
    checkpoint_gates: tuple[GateLedgerEntry, ...]
    story_prerequisites: tuple[StoryPrerequisite, ...]
    repository_results: tuple[RepositoryResult, ...]
    confusion_matrices: tuple[ConfusionMatrixRow, ...]
    m15_promotion_blocked: bool
    m15_block_reasons: tuple[str, ...]
    resource_envelope: ResourceEnvelope
    reviewed_exceptions: tuple[ReviewedException, ...]
    remote_tiers_enabled: bool
    tiers_executed: bool
    external_pin_count: int
    notes: tuple[str, ...] = field(default_factory=tuple)
    source_tree_digest: str = ""
