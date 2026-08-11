"""SV.11 assessment consistency runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.assessment_consistency import (
    ASSESSMENT_CONSISTENCY_VERIFICATION_ID,
)
from verification.assessment_consistency.activation import check_activation
from verification.assessment_consistency.artifacts import check_artifact_contracts
from verification.assessment_consistency.confidence import check_confidence
from verification.assessment_consistency.contract import (
    DATASET_DISCLAIMER,
    QUALITY_COMPARISON_GUARD,
    RELEASE_VALIDATION_TARGET,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SV11_OUTPUT_RELATIVE,
    REPORT_FILENAME,
    default_contract,
)
from verification.assessment_consistency.coverage import check_coverage
from verification.assessment_consistency.determinism import (
    verify_order_independence,
    verify_sv10_determinism_samples,
)
from verification.assessment_consistency.findings import (
    check_consolidation,
    check_correlations,
    check_findings,
)
from verification.assessment_consistency.heads import check_heads
from verification.assessment_consistency.inputs import default_sv10_dir, load_all_bundles
from verification.assessment_consistency.limitations import check_limitations
from verification.assessment_consistency.models import (
    CheckResult,
    ConsistencyReport,
    DefectCandidate,
    OutlierRecord,
    RepositoryBundle,
)
from verification.assessment_consistency.outliers import build_outliers
from verification.assessment_consistency.priority import check_priority
from verification.assessment_consistency.recommendations import check_recommendations
from verification.assessment_consistency.reporting import (
    check_engineering_intelligence_input_ready,
)
from verification.assessment_consistency.repositories import reconcile_with_catalog
from verification.assessment_consistency.schemas import check_schemas
from verification.assessment_consistency.severity import check_severity
from verification.assessment_consistency.terminology import check_terminology
from verification.assessment_consistency.traceability import check_traceability
from verification.cli_installation.environment import engine_root_from_package


def _default_output_dir(engine_root: Path) -> Path:
    return engine_root / SV11_OUTPUT_RELATIVE


def _analyze_fingerprint(bundles: list[RepositoryBundle]) -> dict[str, Any]:
    """Lightweight analyzer used for order-independence checks."""

    defects: list[DefectCandidate] = []
    outliers: list[OutlierRecord] = []
    checks: list[CheckResult] = []

    for fn in (
        check_artifact_contracts,
        check_schemas,
        check_activation,
        check_coverage,
        check_confidence,
        check_findings,
        check_consolidation,
        check_correlations,
        check_recommendations,
        check_limitations,
        check_terminology,
    ):
        c, d = fn(bundles)
        checks.extend(c)
        defects.extend(d)

    c, d, o = check_heads(bundles)
    checks.extend(c)
    defects.extend(d)
    outliers.extend(o)

    c, d, o = check_severity(bundles)
    checks.extend(c)
    defects.extend(d)
    outliers.extend(o)

    c, d, o = check_priority(bundles)
    checks.extend(c)
    defects.extend(d)
    outliers.extend(o)

    c, d, _counts = check_traceability(bundles)
    checks.extend(c)
    defects.extend(d)

    outliers.extend(build_outliers(bundles))
    ready, c, d = check_engineering_intelligence_input_ready(bundles)
    checks.extend(c)
    defects.extend(d)

    release_blocking = [
        x
        for x in defects
        if x.handling == "product_defect_for_sv13"
        and x.release_impact in {"blocks_release", "blocks_sv11", "blocks_sv12_input"}
    ]
    verdict = _verdict(len(bundles), defects, ready, release_blocking)
    return {
        "verdict": verdict,
        "defect_ids": [x.defect_id for x in defects],
        "outlier_ids": [x.outlier_id for x in outliers],
        "check_ok_count": sum(1 for c in checks if c.ok),
        "check_fail_count": sum(1 for c in checks if not c.ok),
        "aggregate_counts": {
            "repositories": len(bundles),
            "defects": len(defects),
            "outliers": len(outliers),
            "ei_ready": sum(1 for v in ready.values() if v),
        },
    }


def _verdict(
    repo_count: int,
    defects: list[DefectCandidate],
    ready: dict[str, bool],
    release_blocking: list[DefectCandidate],
) -> str:
    if repo_count != RELEASE_VALIDATION_TARGET:
        return "FAIL"
    if release_blocking:
        return "FAIL"
    if any(d.classification in {"privacy", "traceability", "schema_contract"} for d in defects):
        return "FAIL"
    if ready and not all(ready.values()):
        return "FAIL"
    # Remaining defects that are expected variation / documentation do not fail.
    hard = [
        d
        for d in defects
        if d.handling == "product_defect_for_sv13"
        and d.classification
        not in {
            # none — product_defect_for_sv13 always matters unless release_impact soft
        }
        and d.release_impact not in {"investigate", "unknown"}
    ]
    # Soft product defects with investigate impact → PASS_WITH_LIMITATIONS if any.
    soft = [
        d
        for d in defects
        if d.handling in {"repository_specific_limitation", "expected_variation", "documentation_only"}
        or d.release_impact == "investigate"
    ]
    if hard:
        return "FAIL"
    if soft or any(
        b.record.get("verdict") == "PASS_WITH_LIMITATIONS"
        for b in []  # filled by caller via limitations note
    ):
        return "PASS_WITH_LIMITATIONS"
    return "PASS"


def run_assessment_consistency(
    *,
    engine_root: Path | None = None,
    sv10_dir: Path | None = None,
    output_dir: Path | None = None,
) -> ConsistencyReport:
    contract = default_contract()
    engine = (engine_root or engine_root_from_package()).resolve()
    sv10 = (sv10_dir or default_sv10_dir(engine)).resolve()
    out = (output_dir or _default_output_dir(engine)).resolve()
    out.mkdir(parents=True, exist_ok=True)

    final_report, records, bundles = load_all_bundles(sv10, engine_root=engine)
    repo_checks, repo_defects, meta = reconcile_with_catalog(records, engine_root=engine)

    all_checks: list[CheckResult] = list(repo_checks)
    all_defects: list[DefectCandidate] = list(repo_defects)
    all_outliers: list[OutlierRecord] = []

    buckets: dict[str, list[dict[str, Any]]] = {
        "artifact_contract_checks": [],
        "schema_checks": [],
        "assessment_head_checks": [],
        "activation_checks": [],
        "coverage_checks": [],
        "confidence_checks": [],
        "finding_checks": [],
        "severity_checks": [],
        "recommendation_checks": [],
        "priority_checks": [],
        "traceability_checks": [],
        "limitation_checks": [],
        "terminology_checks": [],
        "consolidation_checks": [],
        "correlation_checks": [],
    }

    def _store(key: str, checks: list[CheckResult], defects: list[DefectCandidate]) -> None:
        buckets[key].extend(c.to_dict() for c in checks)
        all_checks.extend(checks)
        all_defects.extend(defects)

    c, d = check_artifact_contracts(bundles)
    _store("artifact_contract_checks", c, d)
    c, d = check_schemas(bundles)
    _store("schema_checks", c, d)
    c, d, o = check_heads(bundles)
    _store("assessment_head_checks", c, d)
    all_outliers.extend(o)
    c, d = check_activation(bundles)
    _store("activation_checks", c, d)
    c, d = check_coverage(bundles)
    _store("coverage_checks", c, d)
    c, d = check_confidence(bundles)
    _store("confidence_checks", c, d)
    c, d = check_findings(bundles)
    _store("finding_checks", c, d)
    c, d = check_consolidation(bundles)
    _store("consolidation_checks", c, d)
    c, d = check_correlations(bundles)
    _store("correlation_checks", c, d)
    c, d, o = check_severity(bundles)
    _store("severity_checks", c, d)
    all_outliers.extend(o)
    c, d = check_recommendations(bundles)
    _store("recommendation_checks", c, d)
    c, d, o = check_priority(bundles)
    _store("priority_checks", c, d)
    all_outliers.extend(o)
    c, d, _trace_counts = check_traceability(bundles)
    _store("traceability_checks", c, d)
    c, d = check_limitations(bundles)
    _store("limitation_checks", c, d)
    c, d = check_terminology(bundles)
    _store("terminology_checks", c, d)

    all_outliers.extend(build_outliers(bundles))
    ready, c, d = check_engineering_intelligence_input_ready(bundles)
    all_checks.extend(c)
    all_defects.extend(d)

    det_sv10 = verify_sv10_determinism_samples(sv10)
    if not det_sv10.get("ok"):
        all_defects.append(
            DefectCandidate(
                classification="determinism",
                repository_ids=list(det_sv10.get("expected_ids") or []),
                entity_id="sv10_determinism_samples",
                expected="4/4 SV.10 determinism samples preserved ok",
                actual=str(det_sv10),
                release_impact="investigate",
                handling="verification_harness_fix",
            )
        )
    order = verify_order_independence(bundles, _analyze_fingerprint)
    if not order.get("ok"):
        all_defects.append(
            DefectCandidate(
                classification="determinism",
                repository_ids=[],
                entity_id="order_independence",
                expected="identical fingerprints across orderings",
                actual="mismatch",
                release_impact="blocks_release",
                handling="verification_harness_fix",
            )
        )

    release_blocking = [
        x
        for x in all_defects
        if x.release_impact in {"blocks_release", "blocks_sv11", "blocks_sv12_input"}
    ]
    hard_product = [
        x
        for x in all_defects
        if x.handling == "product_defect_for_sv13"
        and (
            x.release_impact in {"blocks_release", "blocks_sv11", "blocks_sv12_input"}
            or x.classification
            in {
                "privacy",
                "traceability",
                "schema_contract",
                "determinism",
            }
        )
    ]
    has_limitations = any(
        b.record.get("verdict") == "PASS_WITH_LIMITATIONS" for b in bundles
    )

    if len(bundles) != RELEASE_VALIDATION_TARGET or release_blocking or hard_product:
        verdict = "FAIL"
    elif ready and not all(ready.values()):
        verdict = "FAIL"
    elif has_limitations or all_defects:
        # Remaining defects are investigate/documentation/expected variation.
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    warnings = [
        DATASET_DISCLAIMER,
        QUALITY_COMPARISON_GUARD,
    ]
    if final_report.get("overall_verdict"):
        warnings.append(f"sv10_overall_verdict={final_report.get('overall_verdict')}")

    limitations = [
        "Uses preserved SV.10 artifacts only; repositories are not reassessed by default.",
        "Outliers are informational unless contract_violation is true.",
        "SV.10 repository-scoped limitations (Known Issues demos, submodules, BookStack runtime) remain expected variation.",
    ]

    report = ConsistencyReport(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        verification_id=ASSESSMENT_CONSISTENCY_VERIFICATION_ID,
        catalog_id=meta.get("catalog_id"),
        repository_count=len(bundles),
        included_repository_ids=sorted(b.repository_id for b in bundles),
        qualified_revisions=meta.get("qualified_revisions") or {},
        language_distribution=meta.get("language_distribution") or {},
        ecosystem_distribution=meta.get("ecosystem_distribution") or {},
        tier_distribution=meta.get("tier_distribution") or {},
        artifact_contract_checks=buckets["artifact_contract_checks"],
        schema_checks=buckets["schema_checks"],
        assessment_head_checks=buckets["assessment_head_checks"],
        activation_checks=buckets["activation_checks"],
        coverage_checks=buckets["coverage_checks"],
        confidence_checks=buckets["confidence_checks"],
        finding_checks=buckets["finding_checks"]
        + buckets["consolidation_checks"]
        + buckets["correlation_checks"],
        severity_checks=buckets["severity_checks"],
        recommendation_checks=buckets["recommendation_checks"],
        priority_checks=buckets["priority_checks"],
        traceability_checks=buckets["traceability_checks"],
        limitation_checks=buckets["limitation_checks"],
        terminology_checks=buckets["terminology_checks"],
        consolidation_checks=buckets["consolidation_checks"],
        correlation_checks=buckets["correlation_checks"],
        engineering_intelligence_input_ready=ready,
        outlier_records=[o.to_dict() for o in all_outliers],
        defect_candidates=[d.to_dict() for d in all_defects],
        warnings=warnings,
        limitations=limitations,
        determinism={
            "sv10_samples": det_sv10,
            "order_independence": {"ok": order.get("ok")},
        },
        guards=[QUALITY_COMPARISON_GUARD, *contract.notes],
        verdict=verdict,
    )
    report.write_json(out / REPORT_FILENAME)
    return report
