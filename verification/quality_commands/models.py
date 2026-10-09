"""Models for the Engine quality-command manifest."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommandStatus(StrEnum):
    """How a quality command is recorded. FAIL variants are never stored as PASS.

    PASS — exit 0 on this run
    BASELINE_FAIL — nonzero, and G00 already recorded this command as failing
    NEW_FAIL — nonzero, not on the G00 list (a regression or new check)
    BLOCKED — tool/feed missing; cannot claim clean
    NOT_RUN — dry-run or skipped execution
    FAIL — generic failure (timeouts)
    """

    PASS = "PASS"
    FAIL = "FAIL"
    BASELINE_FAIL = "BASELINE_FAIL"
    NEW_FAIL = "NEW_FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True, slots=True)
class QualityCommand:
    id: str
    argv: tuple[str, ...]
    required: bool
    timeout_seconds: int
    missing_tool_status: CommandStatus = CommandStatus.BLOCKED


@dataclass(frozen=True, slots=True)
class CoveragePolicy:
    source: str
    branch: bool
    fail_under: int


@dataclass(frozen=True, slots=True)
class EngineTestsJob:
    """What root CI actually runs. A green job is not lint/type/coverage proof."""

    name: str
    workflow: str
    proves: tuple[str, ...]
    does_not_prove: tuple[str, ...]
    reviewer_checkpoint: str
    automatic_branch_protection: bool


@dataclass(frozen=True, slots=True)
class SecurityScanner:
    id: str
    module: str
    argv: tuple[str, ...]
    extra: str
    version_constraint: str
    inputs: str
    severity_policy: str
    feed_required: bool


@dataclass(frozen=True, slots=True)
class QualityManifest:
    schema_version: int
    id: str
    version: str
    working_directory: str
    coverage: CoveragePolicy
    engine_tests_job: EngineTestsJob
    security_scanner: SecurityScanner
    commands: tuple[QualityCommand, ...]
    baseline_notes: str


@dataclass(frozen=True, slots=True)
class CommandResult:
    id: str
    argv: tuple[str, ...]
    exit_code: int | None
    status: CommandStatus
    duration_seconds: float
    stdout_digest: str
    stderr_digest: str
    skip_reason: str = ""


@dataclass(frozen=True, slots=True)
class QualityRunReport:
    ok: bool
    merge_ready: bool
    results: tuple[CommandResult, ...]
    baseline_failure_ids: tuple[str, ...]
    notes: tuple[str, ...]

    def passing_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.results if item.status is CommandStatus.PASS)
