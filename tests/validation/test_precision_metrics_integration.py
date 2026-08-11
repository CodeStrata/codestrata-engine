"""Slice 5.7 — precision metric integration with records, summary, and report boundary."""

from __future__ import annotations

from decimal import Decimal

import pytest

from codestrata.domain.quality_metrics.precision import (
    QualityMetricAvailability,
    QualityMetricScope,
    build_precision_metric,
)
from validation.compare import pack_precision_from_result
from validation.inventory import compute_precision_recall
from validation.models import PackPrecisionRecord, ValidationVerdict
from validation.recording import (
    RECORD_SCHEMA_VERSION,
    RepositoryValidationRecord,
)
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
        fp: int,
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


def test_pack_precision_from_result_projects_canonical_metric() -> None:
    record = pack_precision_from_result(
        "security",
        _Result(repository_id="local-security-hygiene", tp=4, fp=0, fn=1, amb=2),
    )
    assert record.true_positives == 4
    assert record.false_positives == 0
    assert record.ambiguous == 2
    assert record.precision == 1.0
    assert record.recall == pytest.approx(0.8)
    assert record.precision_metric_id == (
        "precision:repository:local-security-hygiene:security"
    )
    assert record.recall_metric_id == (
        "recall:repository:local-security-hygiene:security"
    )
    assert record.precision_availability is not None
    assert record.precision_metric is not None
    assert Decimal(str(record.precision_metric["value"])) == Decimal("1")
    assert record.recall_metric is not None
    assert Decimal(str(record.recall_metric["value"])) == Decimal("0.8")


def test_negative_control_pass_with_unavailable_precision() -> None:
    record = pack_precision_from_result(
        "security",
        _Result(repository_id="local-ai-negative", tp=0, fp=0, fn=0, passed=True),
    )
    assert record.passed is True
    assert record.precision is None
    assert record.precision_availability == QualityMetricAvailability.UNAVAILABLE.value


def test_legacy_record_without_canonical_metric_still_validates() -> None:
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


def test_invalid_legacy_precision_count_mismatch_rejected() -> None:
    pack = PackPrecisionRecord(
        pack="security",
        true_positives=2,
        false_positives=0,
        false_negatives=0,
        precision=0.5,
        recall=1.0,
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
    with pytest.raises(RecordValidationError, match="precision inconsistent"):
        validate_repository_record(record)


def test_aggregate_sums_not_averages_and_preserves_source() -> None:
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
                    _Result(repository_id="local-security-hygiene", tp=4, fp=0),
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
                    _Result(repository_id="remote-python-fastapi", tp=0, fp=2),
                ),
            ),
        ),
    )
    security = {item.pack: item for item in aggregate_pack_precision(records)}["security"]
    assert security.true_positives == 4
    assert security.false_positives == 2
    assert security.precision == pytest.approx(4 / 6)
    assert security.precision_metric_id == "precision:validation_set:security"
    assert security.precision_source == "mixed_validation_set"
    assert "local-security-hygiene" in security.source_repository_ids
    assert "remote-python-fastapi" in security.source_repository_ids


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
                    _Result(repository_id="local-security-hygiene", tp=1, fp=0),
                ),
            ),
        ),
    )
    security = {item.pack: item for item in aggregate_pack_precision(records)}["security"]
    assert security.repositories_evaluated == 1
    assert security.true_positives == 1
    assert any("skipped" in item for item in security.limitations)
    assert any("error" in item for item in security.limitations)


def test_summary_markdown_disclaimer_and_no_100_percent_accurate() -> None:
    packs = (
        pack_precision_from_result(
            "security",
            _Result(repository_id="local-security-hygiene", tp=4, fp=0),
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
    md = render_summary_markdown(artifact)
    assert DISCLAIMER in md
    assert "100% accurate" not in md.lower()
    assert "within this validation scope" in md
    assert "within this authored validation scope" in md


def test_rule_and_category_scopes() -> None:
    rule = build_precision_metric(
        scope=QualityMetricScope.RULE,
        scope_id="security.credential-literal",
        true_positive_count=2,
        false_positive_count=0,
        source="controlled_fixture",
    )
    assert rule.scope is QualityMetricScope.RULE
    category = build_precision_metric(
        scope=QualityMetricScope.INVENTORY_CATEGORY,
        scope_id="languages",
        true_positive_count=3,
        false_positive_count=1,
    )
    family = build_precision_metric(
        scope=QualityMetricScope.EVIDENCE_FAMILY,
        scope_id="cloud.container",
        true_positive_count=0,
        false_positive_count=0,
    )
    assert category.value == Decimal("0.75")
    assert family.availability is QualityMetricAvailability.UNAVAILABLE


def test_customer_report_boundary_no_validation_precision_field() -> None:
    from codestrata.reporting.contract import identifiers

    names = {name.lower() for name in dir(identifiers)}
    assert "validation_precision" not in names
    assert "precision_metric" not in names
