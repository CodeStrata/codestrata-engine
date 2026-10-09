"""Typed records for E15.1 corpus manifests and independent labels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"
    NOT_YET_DUE = "NOT_YET_DUE"


class CorpusTier(StrEnum):
    DOGFOOD = "dogfood"
    EXTERNAL_LARGE = "external_large"
    FLAGSHIP_LABELED = "flagship_labeled"


class DepthRole(StrEnum):
    SUPPORTED_JAVA = "supported_java"
    SUPPORTED_JS_TS = "supported_js_ts"
    MIXED_BUILD_MONOREPO = "mixed_build_monorepo"
    RETAINED_LOWER_DEPTH = "retained_lower_depth"
    PARTIAL_UNSUPPORTED = "partial_unsupported"


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    history_days: int
    history_commit_cap: int
    proposed_budget_le_10k: str
    proposed_budget_le_100k: str
    budgets_published: bool
    measured_budget_le_10k: str = ""
    measured_budget_le_100k: str = ""
    budget_evidence: str = ""


@dataclass(frozen=True, slots=True)
class ScanPolicy:
    public_scan_readonly: bool
    may_modify_assessed_repository: bool
    may_run_assessed_builds_or_tests: bool
    silent_fetch_in_default_tests: bool
    private_or_customer_content_allowed: bool


@dataclass(frozen=True, slots=True)
class SelectionCriteria:
    min_github_size_kib: int
    require_unique_canonical_clones: bool
    discovery_22_counts_as_fifty: bool
    convenience_replacement_to_hide_failures: bool
    axes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusInputs:
    git_state: str
    config: str
    feed: str
    invocation: str


@dataclass(frozen=True, slots=True)
class CorpusExpectations:
    crash_free_or_explicit_error: bool
    unsupported_is_not_success: bool
    budget_exceeded_never_silent_truncate: bool
    survival_is_not_analytical_correctness: bool
    coverage_unknown_if_denominator_unknown: bool
    failed_or_unrun_never_pass: bool


@dataclass(frozen=True, slots=True)
class RepositoryPin:
    id: str
    github_repository: str
    github_url: str
    sha: str
    license: str
    size_kib: int
    language: str
    language_group: str
    project_shape: str
    tier: CorpusTier
    depth_class: str
    clone_aliases: tuple[str, ...]
    window: AnalysisWindow
    inputs: CorpusInputs
    expectations: CorpusExpectations
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Representative:
    role: DepthRole
    repository_id: str


@dataclass(frozen=True, slots=True)
class FixtureLabel:
    id: str
    kind: str
    source: str
    independent_of_engine_output: bool
    precedes_tuning: bool
    expected_status: str
    expected_finding_classes: tuple[str, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class DiscoveryLead:
    source: str
    repository_count: int
    meets_fifty_large_bar: bool
    ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusBundle:
    package_revision: str
    measurement_id: str
    story: str
    policy: ScanPolicy
    criteria: SelectionCriteria
    window: AnalysisWindow
    inputs: CorpusInputs
    expectations: CorpusExpectations
    dogfood: tuple[RepositoryPin, ...]
    external_large: tuple[RepositoryPin, ...]
    representatives: tuple[Representative, ...]
    flagship_labels: tuple[FixtureLabel, ...]
    adversarial_labels: tuple[FixtureLabel, ...]
    discovery_lead: DiscoveryLead
    template_paths: tuple[str, ...]
