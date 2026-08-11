"""Slice 4.12 — cross-repository validation summary artifacts from records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.generate_summary import main as generate_summary_main
from validation.models import (
    ComparisonMismatch,
    PackPrecisionRecord,
    ValidationVerdict,
)
from validation.recording import (
    RepositoryValidationRecord,
    write_repository_validation_record,
)
from validation.summary_artifact import (
    DISCLAIMER,
    SUMMARY_SCHEMA_VERSION,
    OverallVerdict,
    SourceRecordRef,
    SummaryScope,
)
from validation.summary_from_records import (
    RecordValidationError,
    aggregate_pack_precision,
    build_summary_artifact,
    derive_overall_verdict,
    generate_summary_from_records,
    load_records_for_summary,
    render_summary_markdown,
    validate_repository_record,
)


def _pack(
    name: str,
    *,
    tp: int = 0,
    fp: int = 0,
    fn: int = 0,
    amb: int = 0,
    passed: bool | None = True,
) -> PackPrecisionRecord:
    denom_p = tp + fp
    denom_r = tp + fn
    return PackPrecisionRecord(
        pack=name,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        ambiguous=amb,
        precision=(tp / denom_p) if denom_p else None,
        recall=(tp / denom_r) if denom_r else None,
        passed=passed,
    )


def _record(
    repository_id: str,
    *,
    run_id: str = "20260801T120000Z",
    verdict: ValidationVerdict = ValidationVerdict.PASS,
    evaluated: int = 2,
    matched: int = 2,
    packs: tuple[PackPrecisionRecord, ...] = (),
    mismatches: tuple[ComparisonMismatch, ...] = (),
    error_message: str | None = None,
    skip_reason: str | None = None,
    schema_version: str = "1.2",
) -> RepositoryValidationRecord:
    return RepositoryValidationRecord(
        repository_id=repository_id,
        run_id=run_id,
        recorded_at="2026-08-01T12:00:00Z",
        verdict=verdict,
        schema_version=schema_version,
        ai_executed=False,
        expectations_evaluated=evaluated,
        expectations_matched=matched,
        expected={"schema_version": schema_version},
        actual={
            "schema_version": schema_version,
            "artifact_names": ["report.json"],
            "limitations": ["no-runtime"],
            "technologies": ["JavaScript"],
        },
        comparison={
            "verdict": verdict.value,
            "expectations_evaluated": evaluated,
            "expectations_matched": matched,
            "mismatch_count": len(mismatches),
            "mismatches": [item.model_dump(mode="json") for item in mismatches],
            "pack_precision": [item.model_dump(mode="json") for item in packs],
        },
        pack_precision=packs,
        mismatches=mismatches,
        error_message=error_message,
        skip_reason=skip_reason,
        record_dir=f"{repository_id}/latest",
    )


def test_summary_schema_and_required_fields(tmp_path: Path) -> None:
    record = _record(
        "repo-a",
        packs=(_pack("technology_inventory", tp=1),),
    )
    write_repository_validation_record(record, records_root=tmp_path)
    artifact, out_dir = generate_summary_from_records(records_root=tmp_path)
    assert artifact.summary_schema_version == SUMMARY_SCHEMA_VERSION
    assert artifact.generated_from_record_schema_version == "1.0"
    assert artifact.scope == SummaryScope.LATEST_PER_REPOSITORY
    assert artifact.repository_count == 1
    assert artifact.repositories[0].repository_id == "repo-a"
    assert artifact.disclaimer == DISCLAIMER
    assert (out_dir / "validation-summary.json").is_file()
    assert (out_dir / "validation-summary.md").is_file()
    assert (tmp_path / "summaries" / "latest" / "validation-summary.json").is_file()


def test_deterministic_ordering_and_repeat_generation(tmp_path: Path) -> None:
    for rid, run in (("b-repo", "20260801T120001Z"), ("a-repo", "20260801T120000Z")):
        write_repository_validation_record(
            _record(
                rid,
                run_id=run,
                packs=(_pack("security", tp=2, fp=1),),
            ),
            records_root=tmp_path,
        )
    first, _ = generate_summary_from_records(records_root=tmp_path)
    second, _ = generate_summary_from_records(records_root=tmp_path)
    assert first.canonical_dict() == second.canonical_dict()
    assert [row.repository_id for row in first.repositories] == ["a-repo", "b-repo"]
    assert [pack.pack for pack in first.pack_precision] == [
        "technology_inventory",
        "security",
        "architecture",
        "technical_debt",
        "dependency",
        "cloud",
        "ai_readiness",
        "modernization",
    ]


def test_invalid_verdict_and_counts_rejected() -> None:
    with pytest.raises(RecordValidationError):
        validate_repository_record(_record("x", evaluated=1, matched=2))
    corrupted = _record("y", packs=(_pack("security", tp=1, fp=0),)).model_copy(
        update={
            "pack_precision": (
                PackPrecisionRecord(
                    pack="security",
                    true_positives=1,
                    false_positives=0,
                    false_negatives=0,
                    precision=0.5,
                    recall=1.0,
                    passed=True,
                ),
            )
        }
    )
    with pytest.raises(RecordValidationError, match="precision inconsistent"):
        validate_repository_record(corrupted)


def test_absolute_source_refs_rejected() -> None:
    with pytest.raises(ValueError, match="absolute"):
        SourceRecordRef(
            repository_id="x",
            run_id="20260801T120000Z",
            relative_path="/Users/someone/record.json",
        )


def test_overall_verdict_precedence() -> None:
    assert (
        derive_overall_verdict((ValidationVerdict.PASS, ValidationVerdict.SKIPPED))
        == OverallVerdict.PASS
    )
    assert (
        derive_overall_verdict((ValidationVerdict.PASS, ValidationVerdict.FAIL))
        == OverallVerdict.FAIL
    )
    assert (
        derive_overall_verdict((ValidationVerdict.FAIL, ValidationVerdict.ERROR))
        == OverallVerdict.ERROR
    )
    assert derive_overall_verdict((ValidationVerdict.SKIPPED,)) == OverallVerdict.SKIPPED
    assert derive_overall_verdict(()) == OverallVerdict.SKIPPED


def test_remote_skip_with_local_pass(tmp_path: Path) -> None:
    write_repository_validation_record(
        _record("local-a", packs=(_pack("technology_inventory", tp=1),)),
        records_root=tmp_path,
    )
    write_repository_validation_record(
        _record(
            "remote-b",
            verdict=ValidationVerdict.SKIPPED,
            evaluated=0,
            matched=0,
            skip_reason="remote repository excluded by mode",
        ),
        records_root=tmp_path,
    )
    artifact, _ = generate_summary_from_records(records_root=tmp_path)
    assert artifact.overall_verdict == OverallVerdict.PASS
    assert artifact.verdict_totals.skipped == 1
    assert artifact.verdict_totals.passed == 1


def test_pack_aggregation_sums_not_averages() -> None:
    records = (
        _record("r1", packs=(_pack("security", tp=1, fp=1),)),
        _record("r2", packs=(_pack("security", tp=1, fp=0),)),
    )
    packs = {item.pack: item for item in aggregate_pack_precision(records)}
    security = packs["security"]
    assert security.true_positives == 2
    assert security.false_positives == 1
    assert security.precision == pytest.approx(2 / 3)
    assert security.precision != pytest.approx(0.75)
    assert security.source_repository_ids == ("r1", "r2")


def test_pack_unavailable_denominator() -> None:
    records = (_record("r1", packs=(_pack("cloud", tp=0, fp=0, fn=0, passed=None),)),)
    packs = {item.pack: item for item in aggregate_pack_precision(records)}
    cloud = packs["cloud"]
    assert cloud.precision is None
    assert cloud.recall is None
    assert cloud.repositories_unavailable == 1


def test_expectations_and_mismatches(tmp_path: Path) -> None:
    mismatch = ComparisonMismatch(
        repository_id="fail-repo",
        assessment_area="security:sec-001",
        expectation="required rule",
        actual="absent",
        diagnostic="missing rule",
        artifact_path="report.json",
    )
    write_repository_validation_record(
        _record(
            "fail-repo",
            verdict=ValidationVerdict.FAIL,
            evaluated=3,
            matched=2,
            mismatches=(mismatch,),
            packs=(_pack("security", tp=0, fp=1, passed=False),),
        ),
        records_root=tmp_path,
    )
    write_repository_validation_record(
        _record(
            "skip-repo",
            verdict=ValidationVerdict.SKIPPED,
            evaluated=0,
            matched=0,
            skip_reason="disabled",
        ),
        records_root=tmp_path,
    )
    artifact, _ = generate_summary_from_records(records_root=tmp_path)
    assert artifact.expectation_totals.evaluated == 3
    assert artifact.expectation_totals.matched == 2
    assert artifact.expectation_totals.mismatched == 1
    assert artifact.expectation_totals.repositories_without_evaluation == 1
    assert artifact.mismatches_by_area["security:sec-001"] == 1
    assert artifact.mismatches[0].source_record.repository_id == "fail-repo"
    assert artifact.overall_verdict == OverallVerdict.FAIL


def test_coverage_gaps_zero_tp_not_failure(tmp_path: Path) -> None:
    write_repository_validation_record(
        _record(
            "local-sample-js",
            packs=(_pack("cloud", tp=0, fp=0, fn=0, passed=True),),
        ),
        records_root=tmp_path,
    )
    artifact, _ = generate_summary_from_records(
        records_root=tmp_path,
        repository_ids={"local-sample-js"},
    )
    assert artifact.overall_verdict == OverallVerdict.PASS
    gap_ids = {gap.gap_id for gap in artifact.coverage_gaps}
    assert "gap.pack.cloud.zero-tp" in gap_ids


def test_markdown_disclaimer_and_no_abs_paths(tmp_path: Path) -> None:
    write_repository_validation_record(
        _record("repo-a", packs=(_pack("dependency", tp=1),)),
        records_root=tmp_path,
    )
    artifact, out_dir = generate_summary_from_records(records_root=tmp_path)
    md = (out_dir / "validation-summary.md").read_text(encoding="utf-8")
    assert DISCLAIMER in md
    assert "product-wide accuracy claim" in md
    blob = json.dumps(artifact.model_dump(mode="json"))
    assert "/Users/" not in blob
    assert "BEGIN PRIVATE KEY" not in blob
    assert render_summary_markdown(artifact) == md


def test_malformed_record_fail_closed(tmp_path: Path) -> None:
    repo = tmp_path / "bad" / "latest"
    repo.mkdir(parents=True)
    (repo / "record.json").write_text(
        json.dumps(
            {
                "record_schema_version": "9.9",
                "repository_id": "bad",
                "run_id": "20260801T120000Z",
                "recorded_at": "2026-08-01T12:00:00Z",
                "verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RecordValidationError, match="unsupported record_schema_version"):
        load_records_for_summary(records_root=tmp_path)


def test_cli_json_only_and_no_assessment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_repository_validation_record(
        _record("cli-repo", packs=(_pack("architecture", tp=1),)),
        records_root=tmp_path,
    )
    called = {"assess": False}

    def _boom(*_args, **_kwargs):  # pragma: no cover - must not run
        called["assess"] = True
        raise AssertionError("assessment must not run during summarize")

    monkeypatch.setattr("validation.runner.run_repository_validation", _boom)
    monkeypatch.setattr("validation.actual.run_real_assessment", _boom)

    code = generate_summary_main(
        [
            "--records-dir",
            str(tmp_path),
            "--repository",
            "cli-repo",
            "--json-only",
            "--print-summary",
        ]
    )
    assert code == 0
    assert called["assess"] is False
    latest = tmp_path / "summaries" / "latest"
    assert (latest / "validation-summary.json").is_file()
    assert not (latest / "validation-summary.md").exists()


def test_cli_nonzero_on_malformed(tmp_path: Path) -> None:
    repo = tmp_path / "broken" / "latest"
    repo.mkdir(parents=True)
    (repo / "record.json").write_text("{not-json", encoding="utf-8")
    code = generate_summary_main(["--records-dir", str(tmp_path)])
    assert code == 1


def test_local_only_skips_missing_records(tmp_path: Path) -> None:
    write_repository_validation_record(
        _record("local-sample-js", packs=(_pack("technology_inventory", tp=1),)),
        records_root=tmp_path,
    )
    artifact, _ = generate_summary_from_records(
        records_root=tmp_path,
        repository_ids={
            "local-sample-js",
            "local-sample-python",  # missing on disk
        },
        require_all_requested=False,
    )
    assert artifact.repository_count == 1
    assert artifact.repositories[0].repository_id == "local-sample-js"


def test_explicit_repository_requires_all(tmp_path: Path) -> None:
    write_repository_validation_record(
        _record("local-sample-js", packs=(_pack("technology_inventory", tp=1),)),
        records_root=tmp_path,
    )
    with pytest.raises(RecordValidationError, match="no validation records found"):
        generate_summary_from_records(
            records_root=tmp_path,
            repository_ids={"local-sample-js", "missing-repo"},
            require_all_requested=True,
        )


def test_build_summary_preserves_run_ids_and_limitations() -> None:
    record = _record(
        "local-sample-python",
        run_id="20260801T150000Z",
        packs=(_pack("technical_debt", tp=1),),
    )
    ref = SourceRecordRef(
        repository_id="local-sample-python",
        run_id="20260801T150000Z",
        relative_path="local-sample-python/latest/record.json",
    )
    artifact = build_summary_artifact(
        ((record, ref),),
        scope=SummaryScope.LATEST_PER_REPOSITORY,
        generated_at="2026-08-01T15:00:00Z",
    )
    row = artifact.repositories[0]
    assert row.run_id == "20260801T150000Z"
    assert row.source_identity is not None
    assert "no-runtime" in row.limitations
    assert row.assessment_artifact_names == ("report.json",)
    assert artifact.generated_at == "2026-08-01T15:00:00Z"
    assert "generated_at" not in artifact.canonical_dict()


def test_unsupported_future_schema_rejected() -> None:
    record = _record("x").model_copy(update={"record_schema_version": "2.0"})
    with pytest.raises(RecordValidationError, match="unsupported"):
        validate_repository_record(record)
