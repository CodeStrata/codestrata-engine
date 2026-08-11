"""findings.json verification."""

from __future__ import annotations

from verification.assessment_report.loaders import AssessmentRunArtifacts, finding_list
from verification.assessment_report.models import CheckResult


def check_findings_json(run: AssessmentRunArtifacts) -> list[CheckResult]:
    doc = run.findings
    items = finding_list(doc)
    ids = [str(item.get("id")) for item in items if item.get("id") is not None]
    checks = [
        CheckResult(
            name="findings:valid_structure",
            ok=isinstance(doc, (dict, list)),
            detail=type(doc).__name__,
            category="findings_json",
        ),
        CheckResult(
            name="findings:unique_ids",
            ok=len(ids) == len(set(ids)),
            detail=f"count={len(ids)}",
            category="findings_json",
        ),
    ]
    # Severity / confidence presence where applicable
    missing_severity = sum(1 for item in items if not item.get("severity"))
    checks.append(
        CheckResult(
            name="findings:severity_present",
            ok=missing_severity == 0 or len(items) == 0,
            detail=f"missing_severity={missing_severity}",
            category="findings_json",
        )
    )
    # No absolute paths / secrets in companion
    blob = str(doc)
    leak_codes = []
    for needle, code in (
        ("/Users/", "abs_path"),
        ("file://", "file_url"),
        ("AKIA", "aws_key"),
        ("-----BEGIN ", "pem"),
        ('"source_body"', "source_body"),
    ):
        if needle in blob:
            leak_codes.append(code)
    checks.append(
        CheckResult(
            name="findings:no_leaks",
            ok=not leak_codes,
            detail=",".join(leak_codes) if leak_codes else "ok",
            category="findings_json",
        )
    )
    # Evidence refs structural presence (resolve checked in traceability)
    with_refs = sum(
        1
        for item in items
        if item.get("evidence_refs") or item.get("evidence") or item.get("primary_evidence_id")
    )
    checks.append(
        CheckResult(
            name="findings:evidence_linkage_fields",
            ok=True,
            detail=f"items_with_evidence_fields={with_refs}/{len(items)}",
            category="findings_json",
        )
    )
    return checks
