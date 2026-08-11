"""Structural validation for SV.4 (reuses product validators)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from codestrata.application.report_validation import validate_report_json
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.traceability import (
    AssessmentTraceabilityError,
    CanonicalReportLoadError,
    validate_assessment_traceability,
    validate_canonical_assessment,
)

_ABS_PATH = re.compile(
    r"(/Users/|/home/|/var/folders/|/tmp/|[A-Za-z]:\\)"
)
_SECRETISH = re.compile(
    r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|cscc_v1_[A-Za-z0-9]+|-----BEGIN [A-Z ]+PRIVATE KEY-----)"
)


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report.json root must be an object")
    return payload


def validate_report_structure(path: Path) -> dict[str, Any]:
    """Run existing report validator; return privacy-safe summary."""

    result = validate_report_json(path)
    return {
        "ok": result.ok,
        "schema_version": result.schema_version,
        "expected_schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "schema_match": result.schema_version == ASSESSMENT_JSON_SCHEMA_VERSION,
        "error_count": sum(1 for item in result.issues if item.severity == "error"),
        "warning_count": sum(1 for item in result.issues if item.severity == "warning"),
        "issue_codes": sorted({item.code for item in result.issues}),
    }


def validate_traceability(document: dict[str, Any]) -> dict[str, Any]:
    assessment = document.get("assessment") if isinstance(document.get("assessment"), dict) else document
    try:
        state = validate_canonical_assessment(assessment)
        # Also run full chain when complete.
        if state == "complete":
            validate_assessment_traceability(assessment)
        return {"ok": True, "state": state, "detail": "traceability resolved"}
    except (AssessmentTraceabilityError, CanonicalReportLoadError, Exception) as exc:
        return {"ok": False, "state": "invalid", "detail": str(exc)[:300]}


def validate_ai_disabled(document: dict[str, Any]) -> dict[str, Any]:
    assessment = document.get("assessment") if isinstance(document.get("assessment"), dict) else document
    ai = assessment.get("ai") if isinstance(assessment.get("ai"), dict) else {}
    executed = bool(ai.get("executed"))
    provider_invoked = bool(ai.get("provider_invoked"))
    status = str(ai.get("status") or "")
    ok = (not executed) and (not provider_invoked) and status in {
        "not_requested",
        "disabled",
        "skipped",
        "",
    }
    return {
        "ok": ok,
        "executed": executed,
        "provider_invoked": provider_invoked,
        "status": status or "absent",
    }


def scan_forbidden_content(document: dict[str, Any]) -> list[str]:
    blob = json.dumps(document, sort_keys=True)
    issues: list[str] = []
    if _ABS_PATH.search(blob):
        issues.append("absolute_path_detected")
    if "file://" in blob:
        issues.append("file_url_detected")
    if _SECRETISH.search(blob):
        issues.append("secret_shaped_value_detected")
    # Source bodies are large; flag obvious pasted source markers only.
    if '"source_body"' in blob or '"file_contents"' in blob:
        issues.append("source_body_field_detected")
    return issues


def structural_summary(report_path: Path) -> dict[str, Any]:
    document = load_report(report_path)
    structure = validate_report_structure(report_path)
    trace = validate_traceability(document)
    ai = validate_ai_disabled(document)
    forbidden = scan_forbidden_content(document)
    ok = (
        structure.get("ok") is True
        and structure.get("schema_match") is True
        and trace.get("ok") is True
        and ai.get("ok") is True
        and not forbidden
    )
    return {
        "ok": ok,
        "structure": structure,
        "traceability": trace,
        "ai": ai,
        "forbidden_content": forbidden,
    }
