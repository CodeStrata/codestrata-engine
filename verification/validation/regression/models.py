"""Typed records for the E15.2 deterministic and adversarial harness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HarnessStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"
    NOT_YET_DUE = "NOT_YET_DUE"
    CANCELLED = "CANCELLED"
    TAMPERED = "TAMPERED"


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    id: str
    status: HarnessStatus
    detail: str

    @property
    def ok(self) -> bool:
        return self.status is HarnessStatus.PASS


@dataclass(frozen=True, slots=True)
class DisclosedSkip:
    id: str
    reason_substring: str
    platforms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusConfiguration:
    id: str
    notes: str


@dataclass(frozen=True, slots=True)
class CoverageFloor:
    source: str
    branch: bool
    fail_under: int
    separate_branch_threshold: bool


@dataclass(frozen=True, slots=True)
class ScanSafety:
    public_scan_readonly: bool
    may_modify_assessed_repository: bool
    may_run_assessed_builds_or_tests: bool
    silent_fetch_in_default_tests: bool
    no_egress_default: bool


@dataclass(frozen=True, slots=True)
class InvocationPolicy:
    argv_prefix: tuple[str, ...]
    forbidden_substrings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HarnessPolicy:
    package_revision: str
    story: str
    measurement_id: str
    repeats: int
    coverage: CoverageFloor
    scan: ScanSafety
    operational_fields: frozenset[str]
    exclude_only_declared: bool
    invocation: InvocationPolicy
    disclosed_skips: tuple[DisclosedSkip, ...]
    not_yet_due: tuple[str, ...]
    corpus_configurations: tuple[CorpusConfiguration, ...]


@dataclass(frozen=True, slots=True)
class RepeatComparison:
    configuration_id: str
    digests: tuple[str, ...]
    equal: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HarnessReport:
    ok: bool
    status: HarnessStatus
    outcomes: tuple[CheckOutcome, ...]
    notes: tuple[str, ...]
    not_yet_due: tuple[str, ...]
