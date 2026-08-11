"""Additional SV.10 offline tests."""

from __future__ import annotations

import json
from pathlib import Path

from verification.curated_repository_validation.models import RepositoryValidationResult
from verification.curated_repository_validation.records import write_repository_record
from verification.curated_repository_validation.source_integrity import verify_source_integrity
from verification.curated_repository_validation.summary import build_final_report, build_tier_summary
from verification.repository_assessment.workspace import capture_inventory


def test_records_roundtrip(tmp_path: Path) -> None:
    record = RepositoryValidationResult(
        repository_id="express",
        project_name="express",
        github_repository="expressjs/express",
        language_group="JS/TS",
        ecosystem="npm",
        tier="tier1",
        qualified_revision="a" * 40,
        final_checkout_sha="a" * 40,
        clone_result="pass",
        initialization_result="pass",
        doctor_result="pass",
        assessment_result="pass",
        exit_code=0,
        duration_bucket="30s_to_2m",
        verdict="PASS",
    )
    path = write_repository_record(record, tmp_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["repository_id"] == "express"
    assert "/Users/" not in path.read_text(encoding="utf-8")


def test_source_integrity_allows_codestrata_outputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("print(1)\n", encoding="utf-8")
    before = capture_inventory(repo)
    (repo / "codestrata.toml").write_text("[repository]\npath='.'\n", encoding="utf-8")
    (repo / "reports").mkdir()
    (repo / "reports" / "out.txt").write_text("ok\n", encoding="utf-8")
    after = capture_inventory(repo)
    ok, failures = verify_source_integrity(before, after)
    assert ok, failures


def test_summary_pass_when_all_pass() -> None:
    records = [
        RepositoryValidationResult(
            repository_id=f"r{i}",
            project_name=f"r{i}",
            github_repository=f"org/r{i}",
            language_group="Python",
            ecosystem="pip",
            tier="tier1",
            qualified_revision="b" * 40,
            final_checkout_sha="b" * 40,
            clone_result="pass",
            initialization_result="pass",
            doctor_result="pass",
            assessment_result="pass",
            exit_code=0,
            duration_bucket="under_10s",
            verdict="PASS",
        )
        for i in range(2)
    ]
    summary = build_tier_summary(
        "tier1",
        ["r0", "r1"],
        records,
        disk_before=10.0,
        disk_after=9.5,
        cleanup_ok=True,
    )
    assert summary.verdict == "PASS"
    report = build_final_report(
        catalog_id="x",
        catalog_schema_version="1.0.0",
        target_count=2,
        tier_summaries=[summary],
        records=records,
        determinism_samples=[],
        defects=[],
        blockers=[],
        warnings=[],
        limitations=[],
    )
    assert report.overall_verdict == "PASS"
    assert report.schema_name == "curated-repository-validation"
