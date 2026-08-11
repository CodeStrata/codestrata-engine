"""Deterministic report models for SV.11.11."""

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
class OpenRouterDoctorIntegrationVerificationReport:
    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: str
    slice_id: str
    verdict: str
    limitations: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    negative_scenarios: tuple[ScenarioResult, ...]
    check_counts: dict[str, int]
    status_fields: dict[str, str]
    notes: tuple[str, ...]
    warnings: tuple[str, ...] = ()

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
            "base_url_status": self.status_fields.get("base_url", "not_run"),
            "bedrock_regression_status": self.status_fields.get("bedrock_regression", "not_run"),
            "blockers": [],
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [c.to_dict() for c in self.checks],
            "credential_status": self.status_fields.get("credentials", "not_run"),
            "defects": defects,
            "dependency_boundary_status": self.status_fields.get(
                "dependency_boundary", "not_run"
            ),
            "dependency_status": self.status_fields.get("dependency", "not_run"),
            "deterministic_status": self.status_fields.get("determinism", "not_run"),
            "doctor_exit_status": self.status_fields.get("doctor_exit", "not_run"),
            "doctor_output_status": self.status_fields.get("doctor_output", "not_run"),
            "doctor_policy_status": self.status_fields.get("doctor_policy", "not_run"),
            "epic": self.epic,
            "fail_soft_status": self.status_fields.get("fail_soft", "not_run"),
            "failed_checks": self.check_counts.get("failed", 0),
            "integration_failure_status": self.status_fields.get(
                "integration_failure", "not_run"
            ),
            "integration_success_status": self.status_fields.get(
                "integration_success", "not_run"
            ),
            "limitations": list(self.limitations),
            "model_status": self.status_fields.get("model", "not_run"),
            "negative_scenarios": [s.to_dict() for s in self.negative_scenarios],
            "notes": list(self.notes),
            "openai_regression_status": self.status_fields.get("openai_regression", "not_run"),
            "optional_header_status": self.status_fields.get("optional_header", "not_run"),
            "privacy_status": self.status_fields.get("privacy", "not_run"),
            "provider_selection_status": self.status_fields.get(
                "provider_selection", "not_run"
            ),
            "readiness_status": self.status_fields.get("readiness", "not_run"),
            "reporting_boundary_status": self.status_fields.get(
                "reporting_boundary", "not_run"
            ),
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "slice_id": self.slice_id,
            "total_checks": self.check_counts.get("total", 0),
            "verdict": self.verdict,
            "verification_id": self.verification_id,
            "verification_version": self.verification_version,
            "warnings": list(self.warnings),
        }
        return {key: payload[key] for key in sorted(payload)}

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_markdown(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# OpenRouter Doctor Integration Verification (Epic 11, Slice 11.11)",
            "",
            f"- Verdict: **{self.verdict}**",
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
    "CheckResult",
    "OpenRouterDoctorIntegrationVerificationReport",
    "ScenarioResult",
    "build_check_counts",
    "category_status",
]
