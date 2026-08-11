"""Slice 5.10 — FN candidate, adjudication, history, summary, CLI integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.domain.quality_metrics.false_negatives import (
    FalseNegativeClassification,
    FalseNegativeStatus,
)
from validation.false_negatives.adjudication import (
    FalseNegativeAdjudication,
    apply_adjudication,
    adjudication_path,
)
from validation.false_negatives.candidates import candidates_from_pack_result
from validation.false_negatives.cli import main as fn_cli_main
from validation.false_negatives.tracking import apply_run_history
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
    aggregate_false_negative_tracking,
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


def test_controlled_fixture_fn_auto_confirmed() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="required credential finding",
                actual="absent",
                diagnostic="required missing",
                path="src/app.py",
            ),
        ),
    )
    fns = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert len(fns) == 1
    assert fns[0].classification is FalseNegativeClassification.CONFIRMED
    assert fns[0].status is FalseNegativeStatus.OPEN


def test_ambiguous_not_confirmed() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="maybe",
                rule_id="security.x",
                classification=FactClassification.AMBIGUOUS,
                expectation="allowed ambiguous",
                actual="absent",
                diagnostic="ambiguous expected positive",
                path=None,
            ),
        ),
    )
    fns = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert len(fns) == 1
    assert fns[0].classification is FalseNegativeClassification.AMBIGUOUS
    assert fns[0].classification is not FalseNegativeClassification.CONFIRMED


def test_unsupported_and_insufficient_separated() -> None:
    unsupported = candidates_from_pack_result(
        "security",
        _Result(
            "remote-python-fastapi",
            (
                _Fact(
                    name="npm",
                    rule_id="dependency.npm",
                    classification=FactClassification.FALSE_NEGATIVE,
                    expectation="npm hygiene",
                    actual="absent",
                    diagnostic="unsupported capability for npm",
                    path=None,
                ),
            ),
        ),
        run_id="20260801T120000Z",
    )
    assert unsupported[0].classification is FalseNegativeClassification.UNSUPPORTED_CAPABILITY

    insufficient = candidates_from_pack_result(
        "security",
        _Result(
            "remote-python-fastapi",
            (
                _Fact(
                    name="manifest",
                    rule_id="dependency.manifest",
                    classification=FactClassification.FALSE_NEGATIVE,
                    expectation="required manifest fact",
                    actual="absent",
                    diagnostic="manifest parse failed",
                    path=None,
                ),
            ),
        ),
        run_id="20260801T120000Z",
    )
    assert (
        insufficient[0].classification is FalseNegativeClassification.INSUFFICIENT_EVIDENCE
    )


def test_real_world_remains_suspected() -> None:
    result = _Result(
        "remote-python-fastapi",
        (
            _Fact(
                name="hit",
                rule_id="security.x",
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="required",
                actual="absent",
                diagnostic="required missing",
                path="app.py",
            ),
        ),
    )
    fns = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert fns[0].classification is FalseNegativeClassification.SUSPECTED


def test_generic_identity_unavailable_untracked() -> None:
    result = _Result(
        "remote-python-fastapi",
        (
            _Fact(
                name=None,
                rule_id=None,
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="",
                actual="absent",
                diagnostic="count too low",
                path=None,
            ),
        ),
    )
    fns = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    assert fns == ()


def test_adjudication_transitions(tmp_path: Path) -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="required",
                actual="absent",
                diagnostic="required missing",
                path="src/app.py",
            ),
        ),
    )
    fns = candidates_from_pack_result("security", result, run_id="20260801T120000Z")
    adj = FalseNegativeAdjudication(
        false_negative_id=fns[0].false_negative_id,
        classification=FalseNegativeClassification.CONFIRMED,
        status=FalseNegativeStatus.FIXED,
        root_cause="rule_predicate",
        resolution="product_fix",
        rationale="predicate tightened",
        regression_test_refs=("tests/validation/test_security_precision.py",),
    )
    path = adjudication_path(adj.false_negative_id, adjudications_dir=tmp_path)
    path.write_text(json.dumps(adj.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    updated = apply_adjudication(fns[0], adj, resolved_run_id="20260801T140000Z")
    assert updated.status is FalseNegativeStatus.FIXED
    assert updated.resolved_run_id == "20260801T140000Z"
    assert updated.regression_test_refs

    expectation_adj = FalseNegativeAdjudication(
        false_negative_id=fns[0].false_negative_id,
        classification=FalseNegativeClassification.EXPECTATION_ERROR,
        status=FalseNegativeStatus.FIXED,
        root_cause="expectation_error",
        resolution="expectation_fix",
        rationale="wrong path in expectation",
    )
    as_expectation = apply_adjudication(fns[0], expectation_adj)
    assert as_expectation.classification is FalseNegativeClassification.EXPECTATION_ERROR


def test_skip_error_do_not_resolve() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="required",
                actual="absent",
                diagnostic="required missing",
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
    assert merged[0].status is not FalseNegativeStatus.FIXED or merged[0].resolution is None


def test_history_updates_last_seen() -> None:
    result = _Result(
        "local-security-hygiene",
        (
            _Fact(
                name="credential",
                rule_id="security.credential-literal",
                classification=FactClassification.FALSE_NEGATIVE,
                expectation="required",
                actual="absent",
                diagnostic="required missing",
                path="src/app.py",
            ),
        ),
    )
    historical = candidates_from_pack_result(
        "security", result, run_id="20260801T120000Z"
    )
    current = candidates_from_pack_result(
        "security", result, run_id="20260801T130000Z"
    )
    merged = apply_run_history(
        current,
        historical,
        current_run_id="20260801T130000Z",
        verdict=ValidationVerdict.FAIL,
    )
    assert len(merged) == 1
    assert merged[0].first_seen_run_id == "20260801T120000Z"
    assert merged[0].last_seen_run_id == "20260801T130000Z"


def test_record_additive_fields(tmp_path: Path) -> None:
    from validation.models import ComparisonOutcome, PackPrecisionRecord

    outcome = ComparisonOutcome(
        pack_precision=(
            PackPrecisionRecord(
                pack="security",
                true_positives=0,
                false_positives=0,
                false_negatives=1,
            ),
        ),
        false_negatives=tuple(
            item.canonical_dict()
            for item in candidates_from_pack_result(
                "security",
                _Result(
                    "local-security-hygiene",
                    (
                        _Fact(
                            name="credential",
                            rule_id="security.credential-literal",
                            classification=FactClassification.FALSE_NEGATIVE,
                            expectation="required",
                            actual="absent",
                            diagnostic="required missing",
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
    assert record.false_negatives
    assert record.false_negative_summary.get("total", 0) >= 1
    # Raw pack FN count remains on pack_precision, unchanged by tracking summary.
    assert outcome.pack_precision[0].false_negatives == 1
    written = write_repository_validation_record(record, records_root=tmp_path)
    assert (written / "record.json").is_file()


def test_old_schema_record_loads_without_fn_fields() -> None:
    record = RepositoryValidationRecord(
        repository_id="legacy-repo",
        run_id="20260701T120000Z",
        recorded_at="2026-07-01T12:00:00Z",
        verdict=ValidationVerdict.PASS,
        expectations_evaluated=1,
        expectations_matched=1,
    )
    assert record.record_schema_version == RECORD_SCHEMA_VERSION
    assert record.false_negatives == ()
    assert record.false_negative_summary == {}


def test_summary_markdown_includes_fn_section() -> None:
    from validation.models import ComparisonOutcome

    outcome = ComparisonOutcome(
        false_negatives=tuple(
            item.canonical_dict()
            for item in candidates_from_pack_result(
                "security",
                _Result(
                    "local-security-hygiene",
                    (
                        _Fact(
                            name="credential",
                            rule_id="security.credential-literal",
                            classification=FactClassification.FALSE_NEGATIVE,
                            expectation="required",
                            actual="absent",
                            diagnostic="required missing",
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
        records_root=Path("/tmp/unused-fn-summary"),
    )
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
    assert artifact.false_negative_tracking is not None
    md = render_summary_markdown(artifact)
    assert "## False-Negative Tracking" in md
    assert DISCLAIMER in md
    # Recall section language / pack FN counts remain independent of tracking.
    assert "## Pack Accuracy" in md


def test_cli_summarize_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = fn_cli_main(["--records-dir", str(tmp_path), "--json", "summarize"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "total" in payload
    assert "insufficient_evidence" in payload


def test_customer_report_boundary_no_fn_tracking_field() -> None:
    from codestrata.reporting.contract import identifiers

    names = {name.lower() for name in dir(identifiers)}
    assert "false_negative" not in names
    assert "falsenegativerecord" not in names


def test_aggregate_tracking_counts() -> None:
    fns = candidates_from_pack_result(
        "security",
        _Result(
            "local-security-hygiene",
            (
                _Fact(
                    name="credential",
                    rule_id="security.credential-literal",
                    classification=FactClassification.FALSE_NEGATIVE,
                    expectation="required",
                    actual="absent",
                    diagnostic="required missing",
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
        false_negatives=tuple(item.canonical_dict() for item in fns),
        false_negative_summary={"total": 1, "confirmed": 1},
    )
    tracking = aggregate_false_negative_tracking((record,))
    assert tracking.total == 1
    assert tracking.confirmed == 1
    assert "security" in tracking.by_pack
