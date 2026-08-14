"""Projector unit matrix P1–P15 + privacy canary (Slice 20.8)."""

from __future__ import annotations

import json
import re
from uuid import UUID

from codestrata.telemetry.assessment_metadata.models import (
    AssessmentMetadataProjectionSource,
    FindingProjectionRow,
    HeadConfidenceProjectionRow,
)
from codestrata.telemetry.assessment_metadata.projector import project_assessment_metadata
from codestrata.telemetry.assessment_metadata.source import (
    build_failure_projection_source,
    new_assessment_id,
)

_AID = "11111111-2222-3333-4444-555555555555"
_EVENT = "amd-engine-test-0001"
_CANARIES = (
    "VERY_PRIVATE_REPO_123",
    "/Users/private/AcmeSecretProject/payments/",
    "AcmeInternalSettlementEngine",
    "TEST_SECRET_DO_NOT_TRANSMIT",
    "git@github.com:private/acme-secret.git",
    "acme-internal-payments-sdk",
    "https://internal.acme.example/private",
)


def _base(**overrides: object) -> AssessmentMetadataProjectionSource:
    data: dict[str, object] = {
        "assessment_id": _AID,
        "event_id": _EVENT,
        "client_version": "0.2.0",
        "platform": "darwin",
        "success": True,
        "assessment_mode": "deterministic",
        "executed_heads": ("technology_inventory", "security"),
        "findings": (),
        "head_confidence": (),
        "duration_ms": 15_000.0,
        "installation_id": "11111111-1111-4111-8111-111111111111",
        "finding_count": 0,
        "recommendation_count": 0,
        "offline_mode": True,
        "ai_used": False,
        "report_json_generated": True,
        "findings_json_generated": True,
        "recommendations_json_generated": False,
        "html_report_generated": True,
        "artifact_count": 3,
        "primary_language": "python",
        "language_count": 1,
        "dependency_ecosystem_count": 1,
        "file_count_bucket": "11_to_50",
        "source_file_count_bucket": "1_to_10",
        "test_file_count_bucket": "none",
        "repository_shape": "application",
        "has_tests": True,
        "has_build_files": True,
        "has_dependency_manifests": True,
    }
    data.update(overrides)
    return AssessmentMetadataProjectionSource(**data)  # type: ignore[arg-type]


def _serialize(source: AssessmentMetadataProjectionSource) -> dict[str, object]:
    return project_assessment_metadata(source).to_stable_dict()


def test_p1_minimal_successful_result() -> None:
    payload = _serialize(_base())
    assert payload["schema_version"] == "1.1"
    assert payload["assessment_id"] == _AID
    assert payload["execution"]["result"] == "succeeded"
    assert payload["assessment"]["assessment_status"] == "completed"
    assert payload["finding_aggregates"] == []


def test_p2_rich_successful_result() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="architecture.layer-dependency",
                severity="high",
                category="architecture",
            ),
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
        ),
        head_confidence=(
            HeadConfidenceProjectionRow(head="security", confidence_level="moderate"),
            HeadConfidenceProjectionRow(
                head="architecture_intelligence", confidence_level="high"
            ),
        ),
        finding_count=2,
        recommendation_count=1,
        ai_used=True,
        assessment_mode="deterministic_with_ai",
    )
    payload = _serialize(source)
    assert payload["execution"]["ai_used"] is True
    assert payload["assessment"]["assessment_mode"] == "deterministic_with_ai"
    assert len(payload["finding_aggregates"]) == 2
    assert {row["head"] for row in payload["head_confidence"]} == {
        "architecture",
        "security",
    }


def test_p3_empty_findings() -> None:
    payload = _serialize(_base(findings=(), finding_count=0))
    assert payload["finding_aggregates"] == []
    assert payload["assessment"]["finding_count"] == 0


def test_p4_duplicate_findings_aggregate() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
        ),
        finding_count=3,
    )
    rows = _serialize(source)["finding_aggregates"]
    assert len(rows) == 1
    assert rows[0]["count"] == 3
    assert rows[0]["rule_id"] == "security.debug-enabled"


def test_p5_distinct_severity_category_rows() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="high",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="governance",
            ),
        )
    )
    rows = _serialize(source)["finding_aggregates"]
    assert len(rows) == 3
    keys = {(r["rule_id"], r["severity"], r["category"]) for r in rows}
    assert len(keys) == 3


def test_p6_excluded_pmd_rule() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="PMD.UnusedPrivateMethod",
                severity="medium",
                category="maintainability",
            ),
            FindingProjectionRow(
                rule_id="architecture.layer-dependency",
                severity="high",
                category="architecture",
            ),
        )
    )
    blob = json.dumps(_serialize(source))
    assert "PMD" not in blob
    assert "pmd." not in blob.lower()
    assert "architecture.layer-dependency" in blob


def test_p7_excluded_provider_rule() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="provider:openai",
                severity="low",
                category="unknown",
            ),
        )
    )
    blob = json.dumps(_serialize(source))
    assert "provider:" not in blob
    assert _serialize(source)["finding_aggregates"] == []


def test_p8_malformed_dynamic_rule_id() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="/Users/private/AcmeSecretProject/payments/rule",
                severity="high",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="https://internal.acme.example/private",
                severity="high",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="not a rule",
                severity="high",
                category="security",
            ),
        )
    )
    payload = _serialize(source)
    assert payload["finding_aggregates"] == []
    blob = json.dumps(payload)
    for canary in _CANARIES[:3]:
        assert canary not in blob


def test_p9_all_head_confidence_enum_values() -> None:
    source = _base(
        head_confidence=(
            HeadConfidenceProjectionRow(head="security", confidence_level="high"),
            HeadConfidenceProjectionRow(head="architecture", confidence_level="moderate"),
            HeadConfidenceProjectionRow(head="dependency", confidence_level="limited"),
            HeadConfidenceProjectionRow(head="testing", confidence_level="unavailable"),
        )
    )
    levels = {row["confidence_level"] for row in _serialize(source)["head_confidence"]}
    assert levels == {"high", "moderate", "limited", "unavailable"}


def test_p10_missing_head_confidence() -> None:
    payload = _serialize(_base(head_confidence=()))
    assert payload["head_confidence"] == []


def test_p11_failed_assessment() -> None:
    source = build_failure_projection_source(
        assessment_id=_AID,
        installation_id="11111111-1111-4111-8111-111111111111",
        failure_category="validation",
        event_id=_EVENT,
        client_version="0.2.0",
        platform_name="darwin",
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert payload["assessment"]["assessment_status"] == "failed"
    assert payload["execution"]["result"] == "failed"
    assert payload["execution"]["failure_category"] == "validation"
    assert payload["finding_aggregates"] == []
    assert payload["assessment_id"] == _AID


def test_p12_unknown_failure_maps_unknown() -> None:
    source = build_failure_projection_source(
        assessment_id=_AID,
        installation_id=None,
        failure_category="not-a-real-category",
        event_id=_EVENT,
        client_version="0.2.0",
        platform_name="linux",
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert payload["execution"]["failure_category"] == "unknown"


def test_p13_sensitive_canary_result() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="architecture.layer-dependency",
                severity="high",
                category="architecture",
            ),
            FindingProjectionRow(
                rule_id="PMD.VERY_PRIVATE_REPO_123",
                severity="critical",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="provider:TEST_SECRET_DO_NOT_TRANSMIT",
                severity="high",
                category="security",
            ),
        ),
        head_confidence=(
            HeadConfidenceProjectionRow(head="security", confidence_level="limited"),
        ),
    )
    payload = _serialize(source)
    blob = json.dumps(payload, sort_keys=True)
    for canary in _CANARIES:
        assert canary not in blob
        assert canary not in payload.keys()
    assert "PMD." not in blob
    assert "provider:" not in blob
    # Must not look like repo-timestamp assessment ids.
    assert not re.fullmatch(r".+-\d{8}-\d{6}", str(payload["assessment_id"]))
    UUID(str(payload["assessment_id"]))


def test_p14_deterministic_ordering() -> None:
    source = _base(
        findings=(
            FindingProjectionRow(
                rule_id="security.debug-enabled",
                severity="medium",
                category="security",
            ),
            FindingProjectionRow(
                rule_id="architecture.layer-dependency",
                severity="high",
                category="architecture",
            ),
            FindingProjectionRow(
                rule_id="dependency.unresolved-version",
                severity="low",
                category="dependency",
            ),
        ),
        head_confidence=(
            HeadConfidenceProjectionRow(head="security", confidence_level="high"),
            HeadConfidenceProjectionRow(head="architecture", confidence_level="moderate"),
            HeadConfidenceProjectionRow(head="dependency", confidence_level="limited"),
        ),
        executed_heads=("security", "technology_inventory", "architecture"),
    )
    first = _serialize(source)
    second = _serialize(source)
    assert first == second
    rules = [row["rule_id"] for row in first["finding_aggregates"]]
    assert rules == sorted(rules)
    heads = [row["head"] for row in first["head_confidence"]]
    assert heads == sorted(heads)
    assert first["assessment"]["executed_heads"] == sorted(
        first["assessment"]["executed_heads"]
    )


def test_p15_unique_assessment_id_across_runs() -> None:
    ids = {new_assessment_id() for _ in range(20)}
    assert len(ids) == 20
    for value in ids:
        UUID(value)
        assert "-" in value
        assert not re.fullmatch(r".+-\d{8}-\d{6}", value)
