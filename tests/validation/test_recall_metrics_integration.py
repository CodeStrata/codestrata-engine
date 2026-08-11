"""Slice 5.8 — recall metric integration with records, summary, and report boundary."""

from __future__ import annotations

from decimal import Decimal

import pytest

from codestrata.domain.quality_metrics.common import QualityMetricAvailability
from codestrata.domain.quality_metrics.recall import build_recall_metric
from validation.compare import pack_precision_from_result
from validation.inventory import compute_precision_recall
from validation.models import PackPrecisionRecord, ValidationVerdict
from validation.recording import RECORD_SCHEMA_VERSION, RepositoryValidationRecord
from validation.summary_artifact import (
    DISCLAIMER,
    SUMMARY_SCHEMA_VERSION,
    SourceRecordRef,
    SummaryScope,
)
from validation.summary_from_records import (
    RecordValidationError,
    aggregate_pack_precision,
    build_summary_artifact,
    render_summary_markdown,
    validate_repository_record,
)


class _Result:
    def __init__(
        self,
        *,
        repository_id: str,
        tp: int,
        fp: int = 0,
        fn: int = 0,
        amb: int = 0,
        passed: bool | None = True,
    ) -> None:
        self.repository_id = repository_id
        self.true_positives = tp
        self.false_positives = fp
        self.false_negatives = fn
        self.ambiguous = amb
        self.passed = passed
        p, r, _ = compute_precision_recall(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
        )
        self.precision = p
        self.recall = r


def test_pack_result_projects_canonical_recall_metric() -> None:
    record = pack_precision_from_result(
        "security",
        _Result(repository_id="local-security-hygiene", tp=3, fp=1, fn=1, amb=2),
    )
    assert record.recall == pytest.approx(0.75)
    assert record.recall_metric_id == (
        "recall:repository:local-security-hygiene:security"
    )
    assert record.recall_metric is not None
    assert Decimal(str(record.recall_metric["value"])) == Decimal("0.75")
    # FP and ambiguous do not enter recall.
    assert record.false_positives == 1
    assert record.ambiguous == 2
    assert record.recall_metric["denominator"] == 4


def test_negative_control_pass_with_unavailable_recall() -> None:
    record = pack_precision_from_result(
        "security",
        _Result(repository_id="local-ai-negative", tp=0, fp=0, fn=0, passed=True),
    )
    assert record.passed is True
    assert record.precision is None
    assert record.recall is None
    assert record.recall_availability == QualityMetricAvailability.UNAVAILABLE.value
    assert record.recall != 1.0


def test_fp_only_precision_available_recall_unavailable() -> None:
    record = pack_precision_from_result(
        "security",
        _Result(repository_id="local-security-hygiene", tp=0, fp=2, fn=0),
    )
    assert record.precision == 0.0
    assert record.recall is None


def test_legacy_record_without_canonical_recall_still_validates() -> None:
    pack = PackPrecisionRecord(
        pack="security",
        true_positives=2,
        false_positives=0,
        false_negatives=0,
        ambiguous=0,
        precision=1.0,
        recall=1.0,
        passed=True,
    )
    record = RepositoryValidationRecord(
        repository_id="legacy-repo",
        run_id="20260801T120000Z",
        recorded_at="2026-08-01T12:00:00Z",
        verdict=ValidationVerdict.PASS,
        schema_version="1.2",
        expectations_evaluated=1,
        expectations_matched=1,
        pack_precision=(pack,),
    )
    assert record.record_schema_version == RECORD_SCHEMA_VERSION
    validate_repository_record(record)


def test_invalid_legacy_recall_count_mismatch_rejected() -> None:
    pack = PackPrecisionRecord(
        pack="security",
        true_positives=2,
        false_positives=0,
        false_negatives=0,
        precision=1.0,
        recall=0.5,
        passed=True,
    )
    record = RepositoryValidationRecord(
        repository_id="bad-repo",
        run_id="20260801T120000Z",
        recorded_at="2026-08-01T12:00:00Z",
        verdict=ValidationVerdict.PASS,
        expectations_evaluated=1,
        expectations_matched=1,
        pack_precision=(pack,),
    )
    with pytest.raises(RecordValidationError, match="recall inconsistent"):
        validate_repository_record(record)


def test_aggregate_sums_tp_fn_not_averages() -> None:
    records = (
        RepositoryValidationRecord(
            repository_id="local-security-hygiene",
            run_id="20260801T120000Z",
            recorded_at="2026-08-01T12:00:00Z",
            verdict=ValidationVerdict.PASS,
            expectations_evaluated=1,
            expectations_matched=1,
            pack_precision=(
                pack_precision_from_result(
                    "security",
                    _Result(repository_id="local-security-hygiene", tp=4, fn=0),
                ),
            ),
        ),
        RepositoryValidationRecord(
            repository_id="remote-python-fastapi",
            run_id="20260801T120000Z",
            recorded_at="2026-08-01T12:00:00Z",
            verdict=ValidationVerdict.PASS,
            expectations_evaluated=1,
            expectations_matched=1,
            pack_precision=(
                pack_precision_from_result(
                    "security",
                    _Result(repository_id="remote-python-fastapi", tp=0, fn=2),
                ),
            ),
        ),
    )
    security = {item.pack: item for item in aggregate_pack_precision(records)}["security"]
    assert security.true_positives == 4
    assert security.false_negatives == 2
    assert security.recall == pytest.approx(4 / 6)
    assert security.recall_metric_id == "recall:validation_set:security"
    assert security.recall_source == "mixed_validation_set"
    assert security.expected_positive_repository_count == 2


def test_skipped_and_error_excluded_without_classifications() -> None:
    records = (
        RepositoryValidationRecord(
            repository_id="skipped-repo",
            run_id="20260801T120000Z",
            recorded_at="2026-08-01T12:00:00Z",
            verdict=ValidationVerdict.SKIPPED,
            skip_reason="missing checkout",
            expectations_evaluated=0,
            expectations_matched=0,
            pack_precision=(),
        ),
        RepositoryValidationRecord(
            repository_id="error-repo",
            run_id="20260801T120000Z",
            recorded_at="2026-08-01T12:00:00Z",
            verdict=ValidationVerdict.ERROR,
            error_message="boom",
            expectations_evaluated=0,
            expectations_matched=0,
            pack_precision=(),
        ),
        RepositoryValidationRecord(
            repository_id="local-security-hygiene",
            run_id="20260801T120000Z",
            recorded_at="2026-08-01T12:00:00Z",
            verdict=ValidationVerdict.PASS,
            expectations_evaluated=1,
            expectations_matched=1,
            pack_precision=(
                pack_precision_from_result(
                    "security",
                    _Result(repository_id="local-security-hygiene", tp=1, fn=0),
                ),
            ),
        ),
    )
    security = {item.pack: item for item in aggregate_pack_precision(records)}["security"]
    assert security.repositories_evaluated == 1
    assert security.false_negatives == 0
    assert any("skipped" in item for item in security.limitations)
    assert any("error" in item for item in security.limitations)


def test_summary_markdown_scoped_recall_language() -> None:
    packs = (
        pack_precision_from_result(
            "security",
            _Result(repository_id="local-security-hygiene", tp=4, fn=0),
        ),
    )
    record = RepositoryValidationRecord(
        repository_id="local-security-hygiene",
        run_id="20260801T120000Z",
        recorded_at="2026-08-01T12:00:00Z",
        verdict=ValidationVerdict.PASS,
        expectations_evaluated=1,
        expectations_matched=1,
        pack_precision=packs,
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
    security = {item.pack: item for item in artifact.pack_precision}["security"]
    assert security.recall_metric is not None
    md = render_summary_markdown(artifact)
    assert DISCLAIMER in md
    assert "100% detection" not in md.lower()
    assert "all issues found" not in md.lower()
    assert "complete recall" not in md.lower()
    assert "within this authored validation scope" in md


def test_rule_miss_lowers_recall() -> None:
    metric = build_recall_metric(
        scope="rule",
        scope_id="security.credential-literal",
        true_positive_count=1,
        false_negative_count=1,
        source="controlled_fixture",
    )
    assert metric.value == Decimal("0.5")
    assert metric.metric_id == "recall:rule:security.credential-literal"


def test_customer_report_boundary_no_validation_recall_field() -> None:
    from codestrata.reporting.contract import identifiers

    names = {name.lower() for name in dir(identifiers)}
    assert "validation_recall" not in names
    assert "recall_metric" not in names
