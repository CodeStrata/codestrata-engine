"""Report JSON structural validation (Phase 5.12).

Validates schema envelope, references, duplicate IDs, evidence links, and
roadmap traceability. Does not re-run assessment.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codestrata.reporting.contract.constants import (
    ALLOWED_CONFIDENCE,
    ALLOWED_EFFORTS,
    ALLOWED_PRIORITIES,
    ALLOWED_RISKS,
    ALLOWED_SEVERITIES,
    ASSESSMENT_JSON_SCHEMA_VERSION,
    OPTIONAL_ASSESSMENT_SECTIONS,
)


@dataclass(frozen=True)
class ReportValidationIssue:
    code: str
    message: str
    path: str
    severity: str = "error"


@dataclass
class ReportValidationResult:
    ok: bool
    issues: list[ReportValidationIssue] = field(default_factory=list)
    schema_version: str | None = None
    enabled_sections: tuple[str, ...] = ()

    def add(
        self,
        code: str,
        message: str,
        *,
        path: str,
        severity: str = "error",
    ) -> None:
        self.issues.append(
            ReportValidationIssue(code=code, message=message, path=path, severity=severity)
        )
        if severity == "error":
            self.ok = False


class ReportValidationService:
    """Validate a customer report.json document."""

    def validate_path(self, report_path: Path) -> ReportValidationResult:
        if not report_path.is_file():
            result = ReportValidationResult(ok=False)
            result.add(
                "file_missing",
                f"report.json not found: {report_path}",
                path=str(report_path),
            )
            return result
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            result = ReportValidationResult(ok=False)
            result.add(
                "invalid_json",
                f"report.json is not valid JSON: {error}",
                path=str(report_path),
            )
            return result
        return self.validate_document(payload)

    def validate_document(self, document: Mapping[str, Any]) -> ReportValidationResult:
        result = ReportValidationResult(ok=True)
        if not isinstance(document, Mapping):
            result.add("not_object", "report root must be a JSON object", path="$")
            return result

        schema_version = document.get("schema_version")
        result.schema_version = str(schema_version) if schema_version is not None else None
        if schema_version != ASSESSMENT_JSON_SCHEMA_VERSION:
            result.add(
                "schema_version",
                f"expected schema_version {ASSESSMENT_JSON_SCHEMA_VERSION!r}, "
                f"got {schema_version!r}",
                path="$.schema_version",
            )
        if "report_version" not in document:
            result.add(
                "report_version_missing",
                "report_version is required",
                path="$.report_version",
            )

        assessment = document.get("assessment")
        if not isinstance(assessment, Mapping):
            result.add(
                "assessment_missing",
                "assessment object is required",
                path="$.assessment",
            )
            return result

        manifest = document.get("manifest")
        if manifest is None:
            result.add(
                "manifest_missing",
                "top-level manifest is required for hardened reports",
                path="$.manifest",
                severity="warning",
            )
        elif not isinstance(manifest, Mapping):
            result.add(
                "manifest_type",
                "manifest must be an object",
                path="$.manifest",
            )
        else:
            enabled = manifest.get("enabled_sections") or []
            if isinstance(enabled, list):
                result.enabled_sections = tuple(str(item) for item in enabled)
            for required in (
                "schema_version",
                "report_version",
                "codestrata_version",
                "generation_mode",
                "enabled_sections",
            ):
                if required not in manifest:
                    result.add(
                        "manifest_field",
                        f"manifest.{required} is required",
                        path=f"$.manifest.{required}",
                    )

        finding_ids = self._validate_findings(assessment, result)
        recommendation_ids = self._validate_recommendations(assessment, finding_ids, result)
        self._validate_roadmap(assessment, finding_ids, recommendation_ids, result)
        self._validate_optional_sections(assessment, result)
        return result

    def _validate_findings(
        self, assessment: Mapping[str, Any], result: ReportValidationResult
    ) -> set[str]:
        findings = assessment.get("findings") or []
        if not isinstance(findings, list):
            result.add("findings_type", "findings must be an array", path="$.assessment.findings")
            return set()
        ids: set[str] = set()
        for index, item in enumerate(findings):
            path = f"$.assessment.findings[{index}]"
            if not isinstance(item, Mapping):
                result.add("finding_type", "finding must be an object", path=path)
                continue
            fid = str(item.get("id") or "").strip()
            if not fid:
                result.add("finding_id", "finding.id is required", path=f"{path}.id")
            elif fid in ids:
                result.add(
                    "duplicate_finding_id",
                    f"duplicate finding id {fid!r}",
                    path=f"{path}.id",
                )
            else:
                ids.add(fid)
            severity = str(item.get("severity") or "").lower()
            if severity and severity not in ALLOWED_SEVERITIES:
                result.add(
                    "severity_value",
                    f"unsupported severity {severity!r}",
                    path=f"{path}.severity",
                    severity="warning",
                )
            evidence = item.get("evidence") or []
            if isinstance(evidence, list):
                seen_ev: set[tuple[Any, ...]] = set()
                for evid in evidence:
                    if not isinstance(evid, Mapping):
                        continue
                    key = (
                        evid.get("file_path"),
                        evid.get("line_number"),
                        evid.get("description"),
                    )
                    if key in seen_ev:
                        result.add(
                            "duplicate_evidence",
                            "duplicate evidence row on finding",
                            path=f"{path}.evidence",
                            severity="warning",
                        )
                    seen_ev.add(key)
                    file_path = evid.get("file_path")
                    if file_path in (None, ""):
                        result.add(
                            "broken_evidence_link",
                            "evidence.file_path is empty",
                            path=f"{path}.evidence",
                            severity="warning",
                        )
        return ids

    def _validate_recommendations(
        self,
        assessment: Mapping[str, Any],
        finding_ids: set[str],
        result: ReportValidationResult,
    ) -> set[str]:
        recommendations = assessment.get("deterministic_recommendations") or []
        if not isinstance(recommendations, list):
            result.add(
                "recommendations_type",
                "deterministic_recommendations must be an array",
                path="$.assessment.deterministic_recommendations",
            )
            return set()
        ids: set[str] = set()
        for index, item in enumerate(recommendations):
            path = f"$.assessment.deterministic_recommendations[{index}]"
            if not isinstance(item, Mapping):
                result.add("recommendation_type", "recommendation must be an object", path=path)
                continue
            rid = str(item.get("id") or "").strip()
            if not rid:
                result.add("recommendation_id", "recommendation.id is required", path=f"{path}.id")
            elif rid in ids:
                result.add(
                    "duplicate_recommendation_id",
                    f"duplicate recommendation id {rid!r}",
                    path=f"{path}.id",
                )
            else:
                ids.add(rid)
            priority = str(item.get("priority") or "").lower()
            if priority and priority not in ALLOWED_PRIORITIES:
                result.add(
                    "priority_value",
                    f"unsupported priority {priority!r}",
                    path=f"{path}.priority",
                    severity="warning",
                )
            effort = str(item.get("effort") or "").lower()
            if effort and effort not in ALLOWED_EFFORTS:
                result.add(
                    "effort_value",
                    f"unsupported effort {effort!r}",
                    path=f"{path}.effort",
                    severity="warning",
                )
            risk = str(item.get("risk") or "").lower()
            if risk and risk not in ALLOWED_RISKS:
                result.add(
                    "risk_value",
                    f"unsupported risk {risk!r}",
                    path=f"{path}.risk",
                    severity="warning",
                )
            related = item.get("related_finding_ids") or []
            if isinstance(related, list):
                for finding_id in related:
                    fid = str(finding_id)
                    if finding_ids and fid not in finding_ids:
                        result.add(
                            "broken_finding_reference",
                            f"related_finding_ids references unknown finding {fid!r}",
                            path=f"{path}.related_finding_ids",
                        )
        return ids

    def _validate_roadmap(
        self,
        assessment: Mapping[str, Any],
        finding_ids: set[str],
        recommendation_ids: set[str],
        result: ReportValidationResult,
    ) -> None:
        roadmap = assessment.get("roadmap")
        if roadmap is None:
            return
        if not isinstance(roadmap, Mapping):
            result.add("roadmap_type", "roadmap must be an object", path="$.assessment.roadmap")
            return
        initiatives = roadmap.get("initiatives") or []
        if not isinstance(initiatives, list):
            result.add(
                "roadmap_initiatives_type",
                "roadmap.initiatives must be an array",
                path="$.assessment.roadmap.initiatives",
            )
            return
        initiative_ids: set[str] = set()
        for index, item in enumerate(initiatives):
            path = f"$.assessment.roadmap.initiatives[{index}]"
            if not isinstance(item, Mapping):
                continue
            iid = str(item.get("initiative_id") or "").strip()
            if not iid:
                result.add(
                    "initiative_id",
                    "initiative_id is required",
                    path=f"{path}.initiative_id",
                )
            elif iid in initiative_ids:
                result.add(
                    "duplicate_initiative_id",
                    f"duplicate initiative id {iid!r}",
                    path=f"{path}.initiative_id",
                )
            else:
                initiative_ids.add(iid)
            confidence = str(item.get("confidence") or "").lower()
            if confidence and confidence not in ALLOWED_CONFIDENCE:
                result.add(
                    "confidence_value",
                    f"unsupported confidence {confidence!r}",
                    path=f"{path}.confidence",
                    severity="warning",
                )
            for fid in item.get("supporting_finding_ids") or []:
                if finding_ids and str(fid) not in finding_ids:
                    result.add(
                        "roadmap_finding_trace",
                        f"supporting_finding_ids references unknown finding {fid!r}",
                        path=f"{path}.supporting_finding_ids",
                    )
            for rid in item.get("supporting_recommendation_ids") or []:
                if recommendation_ids and str(rid) not in recommendation_ids:
                    # Phase 3 recommendations may not appear under deterministic_recommendations.
                    result.add(
                        "roadmap_recommendation_trace",
                        f"supporting_recommendation_ids references {rid!r} "
                        "not present in deterministic_recommendations",
                        path=f"{path}.supporting_recommendation_ids",
                        severity="warning",
                    )
            for dep in item.get("depends_on_initiative_ids") or []:
                if str(dep) not in initiative_ids and str(dep) not in {
                    str(other.get("initiative_id"))
                    for other in initiatives
                    if isinstance(other, Mapping)
                }:
                    # Dependency may reference later-listed initiatives; check full set after loop.
                    pass
        all_ids = {
            str(item.get("initiative_id"))
            for item in initiatives
            if isinstance(item, Mapping) and item.get("initiative_id")
        }
        for index, item in enumerate(initiatives):
            if not isinstance(item, Mapping):
                continue
            for dep in item.get("depends_on_initiative_ids") or []:
                if str(dep) not in all_ids:
                    result.add(
                        "roadmap_dependency",
                        f"depends_on_initiative_ids references unknown initiative {dep!r}",
                        path=f"$.assessment.roadmap.initiatives[{index}].depends_on_initiative_ids",
                    )

    def _validate_optional_sections(
        self, assessment: Mapping[str, Any], result: ReportValidationResult
    ) -> None:
        for key in OPTIONAL_ASSESSMENT_SECTIONS:
            if key not in assessment:
                continue
            section = assessment[key]
            if section is None:
                result.add(
                    "null_optional_section",
                    f"optional section {key!r} should be omitted when empty",
                    path=f"$.assessment.{key}",
                    severity="warning",
                )


def validate_report_json(path: Path | str) -> ReportValidationResult:
    return ReportValidationService().validate_path(Path(path))


def validation_result_payload(result: ReportValidationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "schema_version": result.schema_version,
        "enabled_sections": list(result.enabled_sections),
        "issue_count": len(result.issues),
        "error_count": sum(1 for item in result.issues if item.severity == "error"),
        "warning_count": sum(1 for item in result.issues if item.severity == "warning"),
        "issues": [
            {
                "code": item.code,
                "message": item.message,
                "path": item.path,
                "severity": item.severity,
            }
            for item in result.issues
        ],
    }
