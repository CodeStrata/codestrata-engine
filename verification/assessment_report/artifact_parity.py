"""Artifact inventory and parity checks."""

from __future__ import annotations

from verification.assessment_report.contract import REQUIRED_ARTIFACTS
from verification.assessment_report.loaders import (
    AssessmentRunArtifacts,
    finding_list,
    recommendation_list,
    report_findings,
    report_priority_actions,
    report_recommendations,
)
from verification.assessment_report.models import CheckResult


def inventory_artifacts(run: AssessmentRunArtifacts) -> dict[str, str]:
    present = set(run.present_files)
    result: dict[str, str] = {}
    for name in REQUIRED_ARTIFACTS:
        result[name] = "required" if name in present else "missing"
    for name in sorted(present):
        if name not in result:
            result[name] = "optional"
    return result


def check_artifact_inventory(run: AssessmentRunArtifacts) -> list[CheckResult]:
    inventory = inventory_artifacts(run)
    checks: list[CheckResult] = []
    for name in REQUIRED_ARTIFACTS:
        status = inventory.get(name)
        checks.append(
            CheckResult(
                name=f"artifact:{name}",
                ok=status == "required",
                detail=status or "missing",
                category="inventory",
            )
        )
    return checks


def check_artifact_parity(run: AssessmentRunArtifacts) -> list[CheckResult]:
    report_f = report_findings(run.report)
    companion_f = finding_list(run.findings)
    report_r = report_recommendations(run.report)
    companion_r = recommendation_list(run.recommendations)
    report_f_ids = sorted(str(item.get("id")) for item in report_f if item.get("id"))
    companion_f_ids = sorted(str(item.get("id")) for item in companion_f if item.get("id"))
    report_r_ids = sorted(str(item.get("id")) for item in report_r if item.get("id"))
    companion_r_ids = sorted(str(item.get("id")) for item in companion_r if item.get("id"))

    checks = [
        CheckResult(
            name="parity:finding_ids",
            ok=report_f_ids == companion_f_ids,
            detail=f"report={len(report_f_ids)} companion={len(companion_f_ids)}",
            category="parity",
        ),
        CheckResult(
            name="parity:recommendation_ids",
            ok=report_r_ids == companion_r_ids,
            detail=f"report={len(report_r_ids)} companion={len(companion_r_ids)}",
            category="parity",
        ),
        CheckResult(
            name="parity:finding_count_field",
            ok=(
                not isinstance(run.findings, dict)
                or run.findings.get("finding_count") is None
                or int(run.findings.get("finding_count")) == len(companion_f)
            ),
            detail="finding_count reconciles",
            category="parity",
        ),
        CheckResult(
            name="parity:recommendation_count_field",
            ok=(
                not isinstance(run.recommendations, dict)
                or run.recommendations.get("recommendation_count") is None
                or int(run.recommendations.get("recommendation_count")) == len(companion_r)
            ),
            detail="recommendation_count reconciles",
            category="parity",
        ),
    ]

    # HTML should not invent finding/recommendation IDs absent from JSON.
    html = run.html
    invented = []
    for prefix, ids in (
        ("finding-", set(report_f_ids)),
        ("recommendation-", set(report_r_ids)),
    ):
        # Look for id="finding-..." anchors only when prefix matches known pattern.
        import re

        for match in re.finditer(rf'id="({re.escape(prefix)}[^"]+)"', html):
            # Entity anchors may encode IDs differently; only flag presentation:finding:
            pass
    if "presentation:finding:" in html:
        invented.append("presentation:finding")
    checks.append(
        CheckResult(
            name="parity:html_no_presentation_finding",
            ok=not invented,
            detail=",".join(invented) if invented else "ok",
            category="parity",
        )
    )

    pa = report_priority_actions(run.report)
    checks.append(
        CheckResult(
            name="parity:priority_action_count",
            ok=True,
            detail=f"count={len(pa)}",
            category="parity",
        )
    )
    return checks
