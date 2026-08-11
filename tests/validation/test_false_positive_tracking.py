"""Slice 5.9 — FP candidate, adjudication, history, summary, CLI integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.domain.quality_metrics.false_positives import (
    FalsePositiveClassification,
    FalsePositiveStatus,
)
from validation.false_positives.adjudication import (
    FalsePositiveAdjudication,
    apply_adjudication,
    adjudication_path,
)
from validation.false_positives.candidates import candidates_from_pack_result
from validation.false_positives.cli import main as fp_cli_main
from validation.false_positives.tracking import apply_run_history
from validation.inventory import FactClassification
from validation.models import ValidationVerdict
from validation.recording import (
    RECORD_SCHEMA_VERSION,
    RepositoryValidationRecord,
    build_repository_validation_record,
    write_repository_validation_record,
)
from validation.summary_artifact import DISCLAIMER, SUMMARY_SCHEMA_VERSION
from validation.summary_from_records import (
    aggregate_false_positive_tracking,
    build_summary_artifact,
    render_summary_markdown,
)
from validation.summary_artifact import SourceRecordRef, SummaryScope


class _Fact:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _Result:
    def __init__(self, repository_id: str, classifications: tuple) -> None:
        self.repository_id = repository_id
        self.classifications = classifications


def test_controlled_fixture_fp_auto_confirmed() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_POSITIVE,
                expectation="forbidden",
                actual="present",
                diagnostic="forbidden present",
                path="src/app.py",
            ),
        ),
    )
    fps = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert len(fps) == 1
    assert fps[0].classification is FalsePositiveClassification.CONFIRMED
    assert fps[0].status is FalsePositiveStatus.OPEN


def test_ambiguous_not_confirmed() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="maybe",
                rule_id="security.x",
                classification=FactClassification.AMBIGUOUS,
                expectation="allowed ambiguous",
                actual="present",
                diagnostic="ambiguous",
                path=None,
            ),
        ),
    )
    fps = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert len(fps) == 1
    assert fps[0].classification is FalsePositiveClassification.AMBIGUOUS
    assert fps[0].classification is not FalsePositiveClassification.CONFIRMED


def test_real_world_remains_suspected() -> None:
    result = _Result(
        "remote-python-fastapi",
        (
            _Fact(
                name="hit",
                rule_id="security.x",
                classification=FactClassification.FALSE_POSITIVE,
                expectation="forbidden",
                actual="present",
                diagnostic="forbidden present",
                path="app.py",
            ),
        ),
    )
    fps = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert fps[0].classification is FalsePositiveClassification.SUSPECTED


def test_adjudication_confirmed_to_fixed(tmp_path: Path) -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_POSITIVE,
                expectation="forbidden",
                actual="present",
                diagnostic="forbidden present",
                path="src/app.py",
            ),
        ),
    )
    fps = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    adj = FalsePositiveAdjudication(
        false_positive_id=fps[0].false_positive_id,
        classification=FalsePositiveClassification.CONFIRMED,
        status=FalsePositiveStatus.FIXED,
        root_cause="rule_predicate",
        resolution="product_fix",
        rationale="predicate tightened",
        regression_test_refs=("tests/validation/test_security_precision.py",),
    )
    path = adjudication_path(adj.false_positive_id, adjudications_dir=tmp_path)
    path.write_text(json.dumps(adj.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    updated = apply_adjudication(fps[0], adj, resolved_run_id="20260801T140000Z")
    assert updated.status is FalsePositiveStatus.FIXED
    assert updated.resolved_run_id == "20260801T140000Z"
    assert updated.regression_test_refs


def test_skip_error_do_not_resolve() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_POSITIVE,
                expectation="forbidden",
                actual="present",
                diagnostic="forbidden present",
                path="src/app.py",
            ),
        ),
    )
    historical = candidates_from_pack_result(
        "security", result, run_id="20260801T120000Z"
    )
    merged = apply_run_history(
        (),
        historical,
        current_run_id="20260801T130000Z",
        verdict=ValidationVerdict.SKIPPED,
    )
    assert len(merged) == 1
    assert merged[0].status is not FalsePositiveStatus.FIXED or merged[0].resolution is None


def test_record_additive_fields(tmp_path: Path) -> None:
    from validation.models import ComparisonOutcome, PackPrecisionRecord

    outcome = ComparisonOutcome(
        pack_precision=(
            PackPrecisionRecord(pack="security", true_positives=0, false_positives=1),
        ),
        false_positives=tuple(
            item.canonical_dict()
            for item in candidates_from_pack_result(
                "security",
                _Result(
                    "local-security-hygiene",
                    (
                        _Fact(
                            name="credential",
                            rule_id="security.credential-literal",
                            classification=FactClassification.FALSE_POSITIVE,
                            expectation="forbidden",
                            actual="present",
                            diagnostic="forbidden present",
                            path="src/app.py",
                        ),
                    ),
                ),
                run_id="20260801T120000Z",
            )
        ),
    )
    record = build_repository_validation_record(
        repository_id="local-security-hygiene",
        run_id="20260801T120000Z",
        verdict=ValidationVerdict.FAIL,
        expected=None,
        actual=None,
        outcome=outcome,
        records_root=tmp_path,
    )
    assert record.record_schema_version == RECORD_SCHEMA_VERSION
    assert record.false_positives
    assert record.false_positive_summary.get("total", 0) >= 1
    written = write_repository_validation_record(record, records_root=tmp_path)
    assert (written / "record.json").is_file()


def test_summary_markdown_includes_fp_section() -> None:
    from validation.models import ComparisonOutcome

    outcome = ComparisonOutcome(
        false_positives=tuple(
            item.canonical_dict()
            for item in candidates_from_pack_result(
                "security",
                _Result(
                    "local-security-hygiene",
                    (
                        _Fact(
                            name="credential",
                            rule_id="security.credential-literal",
                            classification=FactClassification.FALSE_POSITIVE,
                            expectation="forbidden",
                            actual="present",
                            diagnostic="forbidden present",
                            path="src/app.py",
                        ),
                    ),
                ),
                run_id="20260801T120000Z",
            )
        ),
    )
    record = build_repository_validation_record(
        repository_id="local-security-hygiene",
        run_id="20260801T120000Z",
        verdict=ValidationVerdict.PASS,
        expected=None,
        actual=None,
        outcome=outcome,
        records_root=Path("/tmp/unused-fp-summary"),
    )
    # Avoid history load against missing dir by using empty historical via non-existing root.
    artifact = build_summary_artifact(
        (
            (
                record,
                SourceRecordRef(
                    repository_id=record.repository_id,
                    run_id=record.run_id,
                    relative_path="local-security-hygiene/latest/record.json",
                ),
            ),
        ),
        scope=SummaryScope.LATEST_PER_REPOSITORY,
        scope_label="test",
    )
    assert artifact.summary_schema_version == SUMMARY_SCHEMA_VERSION
    assert artifact.false_positive_tracking is not None
    md = render_summary_markdown(artifact)
    assert "## False-Positive Tracking" in md
    assert DISCLAIMER in md


def test_cli_summarize_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = fp_cli_main(["--records-dir", str(tmp_path), "--json", "summarize"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "total" in payload


def test_customer_report_boundary_no_fp_tracking_field() -> None:
    from codestrata.reporting.contract import identifiers

    names = {name.lower() for name in dir(identifiers)}
    assert "false_positive" not in names
    assert "falsepositiverecord" not in names


def test_aggregate_tracking_counts() -> None:
    fps = candidates_from_pack_result(
        "security",
        _Result(
            "local-security-hygiene",
            (
                _Fact(
                    name="credential",
                    rule_id="security.credential-literal",
                    classification=FactClassification.FALSE_POSITIVE,
                    expectation="forbidden",
                    actual="present",
                    diagnostic="forbidden present",
                    path="src/app.py",
                ),
            ),
        ),
        run_id="20260801T120000Z",
    )
    record = RepositoryValidationRecord(
        repository_id="local-security-hygiene",
        run_id="20260801T120000Z",
        recorded_at="2026-08-01T12:00:00Z",
        verdict=ValidationVerdict.PASS,
        expectations_evaluated=1,
        expectations_matched=1,
        false_positives=tuple(item.canonical_dict() for item in fps),
        false_positive_summary={"total": 1, "confirmed": 1},
    )
    tracking = aggregate_false_positive_tracking((record,))
    assert tracking.total == 1
    assert tracking.confirmed == 1
    assert "security" in tracking.by_pack
