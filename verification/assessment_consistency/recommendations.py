"""Recommendation authority-chain consistency."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.contract import RECOMMENDATION_TYPE_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_recommendations(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    for bundle in bundles:
        finding_ids = {str(f.get("id")) for f in bundle.findings}
        ids = [str(r.get("id") or "") for r in bundle.recommendations]
        dupes = [i for i, n in Counter(ids).items() if i and n > 1]
        if dupes:
            defects.append(
                DefectCandidate(
                    classification="recommendation_authority",
                    repository_ids=[bundle.repository_id],
                    entity_id=dupes[0],
                    expected="unique Recommendation IDs",
                    actual=f"duplicates={dupes[:5]}",
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
        for rec in bundle.recommendations:
            rtype = str(rec.get("recommendation_type") or "").lower()
            if rtype and rtype not in RECOMMENDATION_TYPE_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="recommendation_authority",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected=f"type in {sorted(RECOMMENDATION_TYPE_VOCAB)}",
                        actual=rtype,
                        handling="product_defect_for_sv13",
                    )
                )
            support = [str(x) for x in (rec.get("supporting_finding_ids") or [])]
            primary = rec.get("primary_finding_id")
            if primary is not None and str(primary) and str(primary) not in support and support:
                defects.append(
                    DefectCandidate(
                        classification="recommendation_authority",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected="primary Finding belongs to supporting set",
                        actual=f"primary={primary}",
                        handling="product_defect_for_sv13",
                    )
                )
            for fid in support:
                if fid not in finding_ids:
                    defects.append(
                        DefectCandidate(
                            classification="recommendation_authority",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(rec.get("id")),
                            expected="supporting_finding_ids resolve",
                            actual=f"dangling={fid}",
                            release_impact="blocks_release",
                            handling="product_defect_for_sv13",
                        )
                    )
            if rtype in {"legacy", "fact_based", "fact-based"}:
                if support and rtype == "legacy":
                    # Legacy may still list empty support; if it claims finding_backed that's wrong.
                    pass
            if rtype == "finding_backed" and not support:
                defects.append(
                    DefectCandidate(
                        classification="recommendation_authority",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected="finding_backed has supporting Findings",
                        actual="empty supporting_finding_ids",
                        handling="product_defect_for_sv13",
                    )
                )
            if not support and rtype not in {"legacy", "fact_based", "fact-based", ""}:
                defects.append(
                    DefectCandidate(
                        classification="recommendation_authority",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected="Recommendations without Findings are legacy/fact-based",
                        actual=rtype or "missing_type",
                        handling="product_defect_for_sv13",
                    )
                )

    checks.append(
        CheckResult(
            name="recommendation_support_resolve",
            ok=not any("dangling=" in d.actual for d in defects),
            detail="supporting_finding_ids resolve within each report",
        )
    )
    checks.append(
        CheckResult(
            name="recommendation_type_vocabulary",
            ok=not any("type in" in d.expected for d in defects),
            detail="recommendation_type uses canonical vocabulary",
        )
    )
    return checks, defects
