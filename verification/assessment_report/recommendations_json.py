"""recommendations.json verification."""

from __future__ import annotations

from verification.assessment_report.loaders import (
    AssessmentRunArtifacts,
    finding_list,
    recommendation_list,
)
from verification.assessment_report.models import CheckResult


def check_recommendations_json(run: AssessmentRunArtifacts) -> list[CheckResult]:
    doc = run.recommendations
    items = recommendation_list(doc)
    finding_ids = {
        str(item.get("id")) for item in finding_list(run.findings) if item.get("id") is not None
    }
    ids = [str(item.get("id")) for item in items if item.get("id") is not None]
    checks = [
        CheckResult(
            name="recommendations:valid_structure",
            ok=isinstance(doc, (dict, list)),
            detail=type(doc).__name__,
            category="recommendations_json",
        ),
        CheckResult(
            name="recommendations:unique_ids",
            ok=len(ids) == len(set(ids)),
            detail=f"count={len(ids)}",
            category="recommendations_json",
        ),
    ]

    dangling = 0
    for item in items:
        support = item.get("supporting_finding_ids") or item.get("related_finding_ids") or []
        primary = item.get("primary_finding_id")
        for fid in support:
            if finding_ids and str(fid) not in finding_ids:
                dangling += 1
        if primary is not None and finding_ids and str(primary) not in finding_ids:
            dangling += 1
        if primary is not None and support and str(primary) not in {str(x) for x in support}:
            # primary should belong to supporting set when both present
            dangling += 1

    checks.append(
        CheckResult(
            name="recommendations:finding_refs_resolve",
            ok=dangling == 0,
            detail=f"dangling_or_misaligned={dangling}",
            category="recommendations_json",
        )
    )

    blob = str(doc).lower()
    unsupported = []
    for phrase in ("roi", "exact cost", "will save", "migration guaranteed"):
        if phrase in blob:
            unsupported.append(phrase)
    checks.append(
        CheckResult(
            name="recommendations:no_unsupported_roi_claims",
            ok=not unsupported,
            detail=",".join(unsupported) if unsupported else "ok",
            category="recommendations_json",
        )
    )

    leak_codes = []
    raw = str(doc)
    for needle, code in (("/Users/", "abs_path"), ("file://", "file_url"), ("AKIA", "aws_key")):
        if needle in raw:
            leak_codes.append(code)
    checks.append(
        CheckResult(
            name="recommendations:no_leaks",
            ok=not leak_codes,
            detail=",".join(leak_codes) if leak_codes else "ok",
            category="recommendations_json",
        )
    )
    return checks
