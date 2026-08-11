"""Traceability consistency using existing SV.4 validators."""

from __future__ import annotations

from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)
from verification.repository_assessment.validation import validate_traceability


def check_traceability(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate], dict[str, dict]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    counts: dict[str, dict] = {}

    for bundle in bundles:
        result = validate_traceability(bundle.report)
        counts[bundle.repository_id] = {
            "ok": bool(result.get("ok")),
            "state": result.get("state"),
            "finding_count": len(bundle.findings),
            "recommendation_count": len(bundle.recommendations),
            "priority_action_count": len(bundle.assessment.get("priority_actions") or []),
            "correlation_count": len(bundle.assessment.get("finding_correlations") or []),
        }
        if not result.get("ok"):
            defects.append(
                DefectCandidate(
                    classification="traceability",
                    repository_ids=[bundle.repository_id],
                    entity_id="canonical_traceability",
                    expected="validate_canonical_assessment / full chain pass",
                    actual=str(result.get("detail") or "failed")[:200],
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )

    failed = [rid for rid, row in counts.items() if not row["ok"]]
    checks.append(
        CheckResult(
            name="canonical_traceability",
            ok=not failed,
            detail=f"passed={len(counts) - len(failed)}/{len(counts)}",
            repository_ids=failed,
            classification="traceability",
        )
    )
    return checks, defects, counts
