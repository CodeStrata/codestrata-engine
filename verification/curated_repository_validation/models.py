"""Models for SV.10 curated repository validation records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RepositoryValidationResult:
    repository_id: str
    project_name: str
    github_repository: str
    language_group: str | None
    ecosystem: str | None
    tier: str
    qualified_revision: str | None
    final_checkout_sha: str | None
    clone_result: str
    initialization_result: str
    doctor_result: str
    assessment_result: str
    exit_code: int | None
    duration_bucket: str | None
    required_artifacts: dict[str, bool] = field(default_factory=dict)
    optional_artifacts: dict[str, bool] = field(default_factory=dict)
    report_schema: str | None = None
    artifact_validation: str = "not_run"
    traceability_validation: str = "not_run"
    source_integrity_verdict: str = "not_run"
    deterministic_mode: bool = True
    ai_executed: bool = False
    telemetry_transmitted: bool = False
    limitations: list[str] = field(default_factory=list)
    failure_classification: str | None = None
    cause_scope: str | None = None
    retries: list[dict[str, str]] = field(default_factory=list)
    verdict: str = "error"
    defects: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TierSummary:
    tier: str
    target_repositories: list[str]
    attempted: int = 0
    passed: int = 0
    failed: int = 0
    timed_out: int = 0
    skipped: int = 0
    duration_buckets: dict[str, int] = field(default_factory=dict)
    artifact_results: dict[str, int] = field(default_factory=dict)
    product_defect_candidates: list[str] = field(default_factory=list)
    repository_limitations: list[str] = field(default_factory=list)
    disk_cleanup_ok: bool = True
    available_disk_gb_before: float | None = None
    available_disk_gb_after: float | None = None
    verdict: str = "FAIL"
    repository_ids_passed: list[str] = field(default_factory=list)
    repository_ids_failed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CuratedValidationReport:
    schema_name: str
    schema_version: str
    verification_id: str
    catalog_id: str | None
    catalog_schema_version: str | None
    target_repository_count: int
    executed_repository_count: int
    passed_count: int
    failed_count: int
    skipped_count: int
    error_count: int
    tier_results: list[dict[str, Any]] = field(default_factory=list)
    repository_records: list[dict[str, Any]] = field(default_factory=list)
    determinism_samples: list[dict[str, Any]] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    overall_verdict: str = "FAIL"
    ai_execution_status: str = "disabled"
    telemetry_transmission_status: str = "not_transmitted"
    dataset_disclaimer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
