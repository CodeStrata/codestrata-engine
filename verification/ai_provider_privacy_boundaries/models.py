"""Deterministic report models for SV.11.12."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    category: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "detail": self.detail,
            "evidence": self.evidence,
            "name": self.name,
            "ok": self.ok,
        }


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    title: str
    forbidden_condition: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "detail": self.detail,
            "forbidden_condition": self.forbidden_condition,
            "ok": self.ok,
            "scenario_id": self.scenario_id,
            "title": self.title,
        }


def build_check_counts(checks: list[CheckResult] | tuple[CheckResult, ...]) -> dict[str, int]:
    total = len(checks)
    failed = sum(1 for check in checks if not check.ok)
    return {"failed": failed, "passed": total - failed, "total": total}


def category_status(checks: list[CheckResult] | tuple[CheckResult, ...], category: str) -> str:
    relevant = [check for check in checks if check.category == category]
    if not relevant:
        return "not_run"
    if any(not check.ok for check in relevant):
        return "fail"
    return "pass"


@dataclass(frozen=True, slots=True)
class AIProviderPrivacyBoundaryVerificationReport:
    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: str
    slice_id: str
    verdict: str
    providers: tuple[str, ...]
    limitations: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    negative_scenarios: tuple[ScenarioResult, ...]
    check_counts: dict[str, int]
    status_fields: dict[str, str]
    provider_matrix: dict[str, Any]
    notes: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    registry_decision: str = "B"
    registry_decision_label: str = "compatibility_registry_retained"

    def to_dict(self) -> dict[str, Any]:
        defects = [
            {"category": c.category, "detail": c.detail, "name": c.name}
            for c in self.checks
            if not c.ok
        ] + [
            {"category": "negative_scenario", "detail": s.detail, "name": s.scenario_id}
            for s in self.negative_scenarios
            if not s.ok
        ]
        payload: dict[str, Any] = {
            "analytics_boundary_status": self.status_fields.get("analytics_boundary", "not_run"),
            "assessment_authority_status": self.status_fields.get(
                "assessment_authority", "not_run"
            ),
            "blockers": [],
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [c.to_dict() for c in self.checks],
            "cli_boundary_status": self.status_fields.get("cli_boundary", "not_run"),
            "configuration_boundary_status": self.status_fields.get(
                "configuration_boundary", "not_run"
            ),
            "credential_privacy_status": self.status_fields.get("credential_privacy", "not_run"),
            "cursor_boundary_status": self.status_fields.get("cursor_boundary", "not_run"),
            "data_lake_boundary_status": self.status_fields.get(
                "data_lake_boundary", "not_run"
            ),
            "defects": defects,
            "dependency_boundary_status": self.status_fields.get(
                "dependency_boundary", "not_run"
            ),
            "deterministic_status": self.status_fields.get("determinism", "not_run"),
            "diagnostics_status": self.status_fields.get("diagnostics", "not_run"),
            "doctor_boundary_status": self.status_fields.get("doctor_boundary", "not_run"),
            "epic": self.epic,
            "error_privacy_status": self.status_fields.get("error_privacy", "not_run"),
            "execution_boundary_status": self.status_fields.get(
                "execution_boundary", "not_run"
            ),
            "failed_checks": self.check_counts.get("failed", 0),
            "failure_isolation_status": self.status_fields.get(
                "failure_isolation", "not_run"
            ),
            "limitations": list(self.limitations),
            "logging_status": self.status_fields.get("logging", "not_run"),
            "model_privacy_status": self.status_fields.get("model_privacy", "not_run"),
            "negative_scenario_count": len(self.negative_scenarios),
            "negative_scenarios": [s.to_dict() for s in self.negative_scenarios],
            "notes": list(self.notes),
            "packaging_status": self.status_fields.get("packaging", "not_run"),
            "platform_boundary_status": self.status_fields.get(
                "platform_boundary", "not_run"
            ),
            "prompt_privacy_status": self.status_fields.get("prompt_privacy", "not_run"),
            "provider_matrix": self.provider_matrix,
            "providers": list(self.providers),
            "public_export_status": self.status_fields.get("public_export", "not_run"),
            "registry_decision": self.registry_decision,
            "registry_decision_label": self.registry_decision_label,
            "registry_status": self.status_fields.get("registry", "not_run"),
            "reporting_boundary_status": self.status_fields.get(
                "reporting_boundary", "not_run"
            ),
            "response_privacy_status": self.status_fields.get("response_privacy", "not_run"),
            "retry_safety_status": self.status_fields.get("retry_safety", "not_run"),
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "slice_id": self.slice_id,
            "telemetry_boundary_status": self.status_fields.get(
                "telemetry_boundary", "not_run"
            ),
            "total_checks": self.check_counts.get("total", 0),
            "verdict": self.verdict,
            "verification_id": self.verification_id,
            "verification_version": self.verification_version,
            "vscode_boundary_status": self.status_fields.get("vscode_boundary", "not_run"),
            "warnings": list(self.warnings),
        }
        return {key: payload[key] for key in sorted(payload)}

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    def write_markdown(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# AI Provider Privacy Boundary Verification (Epic 11, Slice 11.12)",
            "",
            f"- Verdict: **{self.verdict}**",
            f"- Providers: {', '.join(self.providers)}",
            f"- Negative scenarios: {len(self.negative_scenarios)}",
            "",
            "## Check counts",
            "",
        ]
        for key, value in sorted(self.check_counts.items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Limitations", ""])
        for item in self.limitations:
            lines.append(f"- `{item}`")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


__all__ = [
    "AIProviderPrivacyBoundaryVerificationReport",
    "CheckResult",
    "ScenarioResult",
    "build_check_counts",
    "category_status",
]
