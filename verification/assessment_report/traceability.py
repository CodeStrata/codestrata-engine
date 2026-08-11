"""Traceability, Priority Action, and roadmap verification."""

from __future__ import annotations

from codestrata.reporting.traceability import (
    AssessmentTraceabilityError,
    CanonicalReportLoadError,
    validate_assessment_traceability,
    validate_canonical_assessment,
)
from verification.assessment_report.loaders import (
    AssessmentRunArtifacts,
    assessment_of,
    report_findings,
    report_priority_actions,
    report_recommendations,
)
from verification.assessment_report.models import CheckResult


def check_traceability(run: AssessmentRunArtifacts) -> list[CheckResult]:
    assessment = assessment_of(run.report)
    checks: list[CheckResult] = []
    try:
        state = validate_canonical_assessment(assessment)
        if state == "complete":
            validate_assessment_traceability(assessment)
        checks.append(
            CheckResult(
                name="traceability:canonical",
                ok=True,
                detail=f"state={state}",
                category="traceability",
            )
        )
    except (AssessmentTraceabilityError, CanonicalReportLoadError, Exception) as exc:
        checks.append(
            CheckResult(
                name="traceability:canonical",
                ok=False,
                detail=str(exc)[:200],
                category="traceability",
            )
        )

    findings = {str(item.get("id")) for item in report_findings(run.report) if item.get("id")}
    recs = report_recommendations(run.report)
    pas = report_priority_actions(run.report)

    # Recommendation → Finding
    dangling_rec = 0
    for rec in recs:
        support = rec.get("supporting_finding_ids") or rec.get("related_finding_ids") or []
        for fid in support:
            if findings and str(fid) not in findings:
                dangling_rec += 1
    checks.append(
        CheckResult(
            name="traceability:recommendation_to_finding",
            ok=dangling_rec == 0,
            detail=f"dangling={dangling_rec}",
            category="traceability",
        )
    )

    # PA → Recommendation
    rec_ids = {str(item.get("id")) for item in recs if item.get("id")}
    dangling_pa = 0
    for action in pas:
        for rid in action.get("recommendation_ids") or action.get("related_recommendation_ids") or []:
            if rec_ids and str(rid) not in rec_ids:
                dangling_pa += 1
    checks.append(
        CheckResult(
            name="traceability:pa_to_recommendation",
            ok=dangling_pa == 0,
            detail=f"dangling={dangling_pa}",
            category="traceability",
        )
    )
    checks.append(
        CheckResult(
            name="traceability:pa_unique_ids",
            ok=len([a.get("id") for a in pas if a.get("id")])
            == len({str(a.get("id")) for a in pas if a.get("id")}),
            detail=f"count={len(pas)}",
            category="traceability",
        )
    )

    # Roadmap
    roadmap = assessment.get("roadmap")
    if isinstance(roadmap, dict):
        initiatives = roadmap.get("initiatives") or []
        if not isinstance(initiatives, list):
            phases = roadmap.get("phases") or []
            initiatives = []
            for phase in phases if isinstance(phases, list) else []:
                if isinstance(phase, dict):
                    initiatives.extend(phase.get("initiatives") or [])
        init_ids = [str(i.get("id")) for i in initiatives if isinstance(i, dict) and i.get("id")]
        checks.append(
            CheckResult(
                name="traceability:roadmap_unique_initiatives",
                ok=len(init_ids) == len(set(init_ids)),
                detail=f"count={len(init_ids)}",
                category="traceability",
            )
        )
        # No invented ROI/cost fields as numeric certainty claims in labels
        blob = str(roadmap).lower()
        bad = [p for p in ("roi", "exact cost", "guaranteed savings") if p in blob]
        checks.append(
            CheckResult(
                name="traceability:roadmap_no_invented_economics",
                ok=not bad,
                detail=",".join(bad) if bad else "ok",
                category="traceability",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="traceability:roadmap_absent_ok",
                ok=True,
                detail="roadmap optional/absent",
                category="traceability",
            )
        )
    return checks
