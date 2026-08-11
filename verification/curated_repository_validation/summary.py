"""Tier and final summary builders for SV.10."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from verification.curated_repository_validation.contract import DATASET_DISCLAIMER, SCHEMA_NAME, SCHEMA_VERSION
from verification.curated_repository_validation.models import (
    CuratedValidationReport,
    RepositoryValidationResult,
    TierSummary,
)
from verification.curated_repository_validation import (
    CURATED_REPOSITORY_VALIDATION_ID,
)


def build_tier_summary(
    tier: str,
    target_ids: list[str],
    results: list[RepositoryValidationResult],
    *,
    disk_before: float | None,
    disk_after: float | None,
    cleanup_ok: bool,
) -> TierSummary:
    summary = TierSummary(
        tier=tier,
        target_repositories=list(target_ids),
        available_disk_gb_before=disk_before,
        available_disk_gb_after=disk_after,
        disk_cleanup_ok=cleanup_ok,
    )
    buckets: Counter[str] = Counter()
    artifacts: Counter[str] = Counter()
    for row in results:
        summary.attempted += 1
        if row.verdict in {"PASS", "PASS_WITH_LIMITATIONS"}:
            summary.passed += 1
            summary.repository_ids_passed.append(row.repository_id)
        elif row.failure_classification == "timeout":
            summary.timed_out += 1
            summary.failed += 1
            summary.repository_ids_failed.append(row.repository_id)
        else:
            summary.failed += 1
            summary.repository_ids_failed.append(row.repository_id)
        if row.duration_bucket:
            buckets[row.duration_bucket] += 1
        artifacts[row.artifact_validation] += 1
        for lim in row.limitations:
            summary.repository_limitations.append(f"{row.repository_id}:{lim}")
        if row.cause_scope == "engine_product":
            summary.product_defect_candidates.extend(row.defects or [row.repository_id])
    summary.duration_buckets = dict(sorted(buckets.items()))
    summary.artifact_results = dict(sorted(artifacts.items()))
    hard_failures = [
        r
        for r in results
        if r.verdict not in {"PASS", "PASS_WITH_LIMITATIONS"}
        and r.cause_scope
        in {
            "engine_product",
            "verification_harness",
            "infrastructure_or_harness_failure",
            "catalog_metadata",
        }
    ]
    if summary.attempted != len(target_ids):
        summary.verdict = "FAIL"
    elif hard_failures:
        summary.verdict = "FAIL"
    elif summary.failed == 0:
        summary.verdict = "PASS"
    else:
        summary.verdict = "PASS_WITH_LIMITATIONS"
    return summary


def write_tier_summary(summary: TierSummary, output_dir: Path) -> Path:
    path = output_dir / f"{summary.tier}-summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_final_report(
    *,
    catalog_id: str | None,
    catalog_schema_version: str | None,
    target_count: int,
    tier_summaries: list[TierSummary],
    records: list[RepositoryValidationResult],
    determinism_samples: list[dict],
    defects: list[str],
    blockers: list[str],
    warnings: list[str],
    limitations: list[str],
) -> CuratedValidationReport:
    passed = sum(1 for r in records if r.verdict in {"PASS", "PASS_WITH_LIMITATIONS"})
    failed = sum(1 for r in records if r.verdict not in {"PASS", "PASS_WITH_LIMITATIONS", "skipped"})
    skipped = sum(1 for r in records if r.verdict == "skipped")
    errors = sum(1 for r in records if r.verdict == "error")

    overall = "PASS"
    if blockers or len(records) < target_count:
        overall = "FAIL"
    elif any(r.cause_scope == "engine_product" for r in records if r.verdict not in {"PASS", "PASS_WITH_LIMITATIONS"}):
        overall = "FAIL"
    elif failed:
        # Repository-specific documented limitations may yield PASS_WITH_LIMITATIONS.
        if all(
            r.verdict in {"PASS", "PASS_WITH_LIMITATIONS"}
            or r.cause_scope in {"repository_specific", "environment_limitation"}
            for r in records
        ) and all(r.verdict != "error" for r in records):
            overall = "PASS_WITH_LIMITATIONS"
        else:
            overall = "FAIL"
    elif any(r.verdict == "PASS_WITH_LIMITATIONS" for r in records):
        overall = "PASS_WITH_LIMITATIONS"

    return CuratedValidationReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=CURATED_REPOSITORY_VALIDATION_ID,
        catalog_id=catalog_id,
        catalog_schema_version=catalog_schema_version,
        target_repository_count=target_count,
        executed_repository_count=len(records),
        passed_count=passed,
        failed_count=failed,
        skipped_count=skipped,
        error_count=errors,
        tier_results=[s.to_dict() for s in tier_summaries],
        repository_records=[r.to_dict() for r in records],
        determinism_samples=determinism_samples,
        defects=defects,
        blockers=blockers,
        warnings=warnings,
        limitations=[DATASET_DISCLAIMER, *limitations],
        overall_verdict=overall,
        dataset_disclaimer=DATASET_DISCLAIMER,
    )
