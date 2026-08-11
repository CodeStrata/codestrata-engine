"""report.json structural verification (reuses product validators)."""

from __future__ import annotations

from typing import Any

from codestrata.application.report_validation import validate_report_json
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.assessment_report.loaders import (
    AssessmentRunArtifacts,
    assessment_of,
    report_evidence,
    report_findings,
    report_priority_actions,
    report_recommendations,
)
from verification.assessment_report.models import CheckResult
from verification.repository_assessment.validation import (
    scan_forbidden_content,
    validate_ai_disabled,
)


def check_report_json(run: AssessmentRunArtifacts) -> list[CheckResult]:
    path = run.run_directory / "report.json"
    result = validate_report_json(path)
    assessment = assessment_of(run.report)
    schema = str(run.report.get("schema_version") or assessment.get("schema_version") or "")
    checks = [
        CheckResult(
            name="report:valid_json_object",
            ok=isinstance(run.report, dict),
            detail="top-level object",
            category="report_json",
        ),
        CheckResult(
            name="report:schema_version",
            ok=schema == ASSESSMENT_JSON_SCHEMA_VERSION,
            detail=f"actual={schema} expected={ASSESSMENT_JSON_SCHEMA_VERSION}",
            category="report_json",
        ),
        CheckResult(
            name="report:validate_report_json",
            ok=result.ok,
            detail=f"errors={sum(1 for i in result.issues if i.severity == 'error')}",
            category="report_json",
        ),
        CheckResult(
            name="report:assessment_object",
            ok=isinstance(run.report.get("assessment"), dict),
            detail="assessment present",
            category="report_json",
        ),
    ]

    # Unique IDs across canonical collections
    for label, items in (
        ("findings", report_findings(run.report)),
        ("recommendations", report_recommendations(run.report)),
        ("priority_actions", report_priority_actions(run.report)),
        ("evidence", report_evidence(run.report)),
    ):
        ids = [str(item.get("id")) for item in items if item.get("id") is not None]
        checks.append(
            CheckResult(
                name=f"report:unique_{label}_ids",
                ok=len(ids) == len(set(ids)),
                detail=f"count={len(ids)} unique={len(set(ids))}",
                category="report_json",
            )
        )

    ai = validate_ai_disabled(run.report)
    checks.append(
        CheckResult(
            name="report:ai_disabled",
            ok=bool(ai.get("ok")),
            detail=str(ai.get("status")),
            category="report_json",
        )
    )

    forbidden = scan_forbidden_content(run.report)
    checks.append(
        CheckResult(
            name="report:no_forbidden_content",
            ok=not forbidden,
            detail=",".join(forbidden) if forbidden else "ok",
            category="report_json",
        )
    )

    # Coverage / confidence maps when present
    for key in ("assessment_coverage", "assessment_head_confidence"):
        value = assessment.get(key)
        checks.append(
            CheckResult(
                name=f"report:{key}_type",
                ok=value is None or isinstance(value, dict),
                detail="map or absent",
                category="report_json",
            )
        )

    # Technology inventory
    tech = assessment.get("technologies")
    checks.append(
        CheckResult(
            name="report:technologies_present",
            ok=tech is not None,
            detail=type(tech).__name__ if tech is not None else "missing",
            category="report_json",
        )
    )
    return checks


def bounded_counts(run: AssessmentRunArtifacts) -> dict[str, int]:
    return {
        "findings": len(report_findings(run.report)),
        "recommendations": len(report_recommendations(run.report)),
        "priority_actions": len(report_priority_actions(run.report)),
        "evidence": len(report_evidence(run.report)),
    }
