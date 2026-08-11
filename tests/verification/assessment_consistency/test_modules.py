"""Module import smoke tests for SV.11 packages."""

from __future__ import annotations


def test_repositories_module() -> None:
    from verification.assessment_consistency import repositories

    assert repositories.reconcile_with_catalog


def test_artifacts_module() -> None:
    from verification.assessment_consistency import artifacts

    assert artifacts.check_artifact_contracts


def test_schemas_module() -> None:
    from verification.assessment_consistency import schemas

    assert schemas.check_schemas


def test_heads_module() -> None:
    from verification.assessment_consistency import heads

    assert heads.check_heads


def test_activation_module() -> None:
    from verification.assessment_consistency import activation

    assert activation.check_activation


def test_coverage_module() -> None:
    from verification.assessment_consistency import coverage

    assert coverage.check_coverage


def test_confidence_module() -> None:
    from verification.assessment_consistency import confidence

    assert confidence.check_confidence


def test_findings_module() -> None:
    from verification.assessment_consistency import findings

    assert findings.check_findings


def test_severity_module() -> None:
    from verification.assessment_consistency import severity

    assert severity.check_severity


def test_recommendations_module() -> None:
    from verification.assessment_consistency import recommendations

    assert recommendations.check_recommendations


def test_priority_module() -> None:
    from verification.assessment_consistency import priority

    assert priority.check_priority


def test_traceability_module() -> None:
    from verification.assessment_consistency import traceability

    assert traceability.check_traceability


def test_limitations_module() -> None:
    from verification.assessment_consistency import limitations

    assert limitations.check_limitations


def test_terminology_module() -> None:
    from verification.assessment_consistency import terminology

    assert terminology.check_terminology


def test_outliers_module() -> None:
    from verification.assessment_consistency import outliers

    assert outliers.build_outliers


def test_determinism_module() -> None:
    from verification.assessment_consistency import determinism

    assert determinism.verify_order_independence
