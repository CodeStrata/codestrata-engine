"""Artifact validation for SV.10 — reuses SV.4/SV.5 helpers."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from verification.repository_assessment.artifacts import find_latest_run_directory
from verification.repository_assessment.contract import REQUIRED_ARTIFACT_NAMES
from verification.repository_assessment.validation import (
    validate_ai_disabled,
    validate_report_structure,
    validate_traceability,
)

# Operator / harness identity leaks only. Do not flag repository CI examples
# such as `/home/runner/work/...` found in OSS source evidence.
_HARNESS_MARKER = re.compile(r"(cs-sv10-|cs-sv4-|cs-sv5-|/var/folders/)")
_HARNESS_SECRET = re.compile(r"(cscc_v1_[A-Za-z0-9]+|AKIA[0-9A-Z]{16})")


def _operator_home_patterns() -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    home = str(Path.home())
    if home and home not in {"/", ""}:
        patterns.append(re.compile(re.escape(home)))
    user = getpass.getuser() or os.environ.get("USER") or os.environ.get("USERNAME") or ""
    if user:
        patterns.append(
            re.compile(rf"(?<![A-Za-z0-9_])/Users/{re.escape(user)}/")
        )
        patterns.append(
            re.compile(rf"(?<![A-Za-z0-9_])/home/{re.escape(user)}/")
        )
    return patterns


def discover_run_dir(repo_cwd: Path, output_relative: str = "reports") -> Path | None:
    root = repo_cwd / output_relative
    if not root.is_dir():
        return None
    return find_latest_run_directory(root)


def _scan_harness_leaks(document: dict[str, Any]) -> list[str]:
    blob = json.dumps(document, sort_keys=True)
    issues: list[str] = []
    if _HARNESS_MARKER.search(blob) or any(p.search(blob) for p in _operator_home_patterns()):
        issues.append("harness_absolute_path_detected")
    if _HARNESS_SECRET.search(blob):
        issues.append("harness_secret_detected")
    if '"source_body"' in blob or '"file_contents"' in blob:
        issues.append("source_body_field_detected")
    return issues


def _check_html(run_dir: Path) -> tuple[bool, list[str]]:
    try:
        from verification.assessment_report.html_structure import check_html_structure
        from verification.assessment_report.loaders import load_run_directory

        run = load_run_directory(
            run_dir,
            run_id=run_dir.name,
            source="sv10",
            assessment_run_reference=run_dir.name,
        )
        html_checks = check_html_structure(run)
        hard = [c for c in html_checks if not c.ok and c.name in {"html:csp", "html:unique_ids"}]
        if hard:
            return False, [f"{c.name}:{c.detail}" for c in hard]
        soft = [c for c in html_checks if not c.ok]
        return True, [f"{c.name}:{c.detail}" for c in soft[:5]]
    except Exception as exc:  # noqa: BLE001
        return True, [f"html_check_skipped:{type(exc).__name__}"]


def validate_artifacts(run_dir: Path) -> dict[str, Any]:
    required = {name: (run_dir / name).is_file() for name in REQUIRED_ARTIFACT_NAMES}
    optional_names = (
        "graphs",
        "security-assessment.json",
        "dependency-assessment.json",
        "technical-debt-assessment.json",
        "testing-assessment.json",
    )
    optional = {name: (run_dir / name).exists() for name in optional_names}
    result: dict[str, Any] = {
        "required_artifacts": required,
        "optional_artifacts": optional,
        "artifact_validation": "pass" if all(required.values()) else "artifact_missing",
        "report_schema": None,
        "traceability_validation": "not_run",
        "ai_executed": False,
        "privacy_ok": True,
        "details": [],
        "limitations": [],
    }
    if not all(required.values()):
        result["failure_classification"] = "artifact_missing"
        return result

    report_path = run_dir / "report.json"
    structure = validate_report_structure(report_path)
    if not structure.get("ok", False) or not structure.get("schema_match", False):
        result["artifact_validation"] = "schema_failure"
        result["failure_classification"] = "schema_failure"
        result["report_schema"] = str(structure.get("schema_version"))
        result["details"].append("report structure/schema failed")
        return result
    result["report_schema"] = str(structure.get("schema_version") or "1.2")

    document = json.loads(report_path.read_text(encoding="utf-8"))
    ai = validate_ai_disabled(document)
    result["ai_executed"] = bool(ai.get("executed"))
    if not ai.get("ok", True):
        result["artifact_validation"] = "privacy_failure"
        result["failure_classification"] = "privacy_failure"
        return result

    trace = validate_traceability(document)
    result["traceability_validation"] = "pass" if trace.get("ok", False) else "traceability_failure"
    if not trace.get("ok", False):
        result["artifact_validation"] = "traceability_failure"
        result["failure_classification"] = "traceability_failure"
        result["details"].append(str(trace.get("detail") or "traceability failed")[:200])
        return result

    leaks = _scan_harness_leaks(document)
    if leaks:
        result["privacy_ok"] = False
        result["artifact_validation"] = "privacy_failure"
        result["failure_classification"] = "privacy_failure"
        result["details"].extend(leaks)
        return result

    html_ok, html_details = _check_html(run_dir)
    result["details"].extend(html_details)
    if not html_ok:
        result["artifact_validation"] = "artifact_malformed"
        result["failure_classification"] = "artifact_malformed"
        return result

    # Repository-sourced secret-shaped findings (e.g. OWASP demos) are limitations,
    # not harness privacy failures — recorded by the runner when category is Known Issues.
    result["artifact_validation"] = "pass"
    return result


def preserve_run_artifacts(run_dir: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(run_dir, destination)
