"""Assessment-head consistency checks."""

from __future__ import annotations

from verification.assessment_consistency.contract import (
    CANONICAL_HEAD_IDS,
    COVERAGE_AREA_HEAD_IDS,
)
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    OutlierRecord,
    RepositoryBundle,
)


def check_heads(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate], list[OutlierRecord]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    outliers: list[OutlierRecord] = []

    for bundle in bundles:
        cov = bundle.assessment.get("assessment_coverage")
        if not isinstance(cov, dict):
            defects.append(
                DefectCandidate(
                    classification="head_ownership",
                    repository_ids=[bundle.repository_id],
                    entity_id="assessment_coverage",
                    expected="object map of heads",
                    actual=type(cov).__name__,
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
            continue
        unknown = sorted(set(cov) - COVERAGE_AREA_HEAD_IDS)
        if unknown:
            defects.append(
                DefectCandidate(
                    classification="head_ownership",
                    repository_ids=[bundle.repository_id],
                    entity_id="unknown_head",
                    expected="canonical head/area IDs",
                    actual=str(unknown),
                    release_impact="investigate",
                    handling="product_defect_for_sv13",
                )
            )
        conf = bundle.assessment.get("assessment_head_confidence")
        if isinstance(conf, dict):
            conf_unknown = sorted(set(conf) - COVERAGE_AREA_HEAD_IDS)
            if conf_unknown:
                defects.append(
                    DefectCandidate(
                        classification="head_ownership",
                        repository_ids=[bundle.repository_id],
                        entity_id="unknown_head_confidence",
                        expected="canonical head/area IDs",
                        actual=str(conf_unknown),
                        handling="product_defect_for_sv13",
                    )
                )

        # Technology inventory is inventory, not a Finding head producing findings ownership conflict.
        # Modernization remains synthesized — record presence only.
        if "technology_inventory" not in cov:
            outliers.append(
                OutlierRecord(
                    repository_id=bundle.repository_id,
                    metric="missing_technology_inventory_coverage",
                    observed_value=False,
                    comparison_scope="all_repositories",
                    expected_contract="technology_inventory coverage present",
                    contract_violation=True,
                    defect_candidate=True,
                )
            )

        # Finding categories should map to known domains, not invent head aliases.
        for finding in bundle.findings:
            category = str(finding.get("category") or "")
            if category and category.replace("-", "_") in {
                "engineering_intelligence",
            }:
                defects.append(
                    DefectCandidate(
                        classification="head_ownership",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected="Findings not owned by engineering_intelligence summary head",
                        actual=category,
                        handling="product_defect_for_sv13",
                    )
                )

    checks.append(
        CheckResult(
            name="canonical_head_ids",
            ok=not any(d.classification == "head_ownership" for d in defects),
            detail=f"canonical heads={sorted(CANONICAL_HEAD_IDS)}",
            classification="head_ownership",
        )
    )
    checks.append(
        CheckResult(
            name="coverage_map_shape",
            ok=all(isinstance(b.assessment.get("assessment_coverage"), dict) for b in bundles),
            detail="assessment_coverage object present on all repositories",
        )
    )
    return checks, defects, outliers
