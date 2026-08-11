"""Deterministic report models for SV.11.8 Cross-Provider Contract Verification."""

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
class CrossProviderVerificationReport:
    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: str
    slice_id: str
    verdict: str
    providers: tuple[str, ...]
    registry_decision: str
    registry_decision_label: str
    compatibility_requirement_ids: tuple[str, ...]
    matrices: dict[str, Any]
    negative_scenarios: tuple[ScenarioResult, ...]
    checks: tuple[CheckResult, ...]
    limitations: tuple[str, ...]
    warnings: tuple[str, ...]
    notes: tuple[str, ...]
    check_counts: dict[str, int]
    shared_guarantees: tuple[str, ...]
    intentional_differences: tuple[str, ...]
    status_fields: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "authentication_status": self.status_fields.get("authentication", "not_run"),
            "capability_status": self.status_fields.get("capabilities", "not_run"),
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [check.to_dict() for check in self.checks],
            "cli_status": self.status_fields.get("cli", "not_run"),
            "compatibility_requirement_ids": list(self.compatibility_requirement_ids),
            "configuration_status": self.status_fields.get("configuration", "not_run"),
            "blockers": [],
            "cross_provider_matrix": self.matrices.get("cross_provider_matrix", {}),
            "defects": [
                {
                    "category": check.category,
                    "detail": check.detail,
                    "name": check.name,
                }
                for check in self.checks
                if not check.ok
            ]
            + [
                {
                    "category": "negative_scenario",
                    "detail": scenario.detail,
                    "name": scenario.scenario_id,
                }
                for scenario in self.negative_scenarios
                if not scenario.ok
            ],
            "dependency_boundary_status": self.status_fields.get("dependency_boundary", "not_run"),
            "doctor_status": self.status_fields.get("doctor", "not_run"),
            "epic": self.epic,
            "error_status": self.status_fields.get("errors", "not_run"),
            "execution_status": self.status_fields.get("execution", "not_run"),
            "fail_soft_status": self.status_fields.get("fail_soft", "not_run"),
            "failed_checks": self.check_counts.get("failed", 0),
            "intentional_differences": list(self.intentional_differences),
            "limitations": list(self.limitations),
            "matrices": self.matrices,
            "model_resolution_status": self.status_fields.get("model_resolution", "not_run"),
            "negative_scenarios": [scenario.to_dict() for scenario in self.negative_scenarios],
            "notes": list(self.notes),
            "openrouter_absent_status": self.status_fields.get("openrouter_absent", "not_run"),
            "privacy_status": self.status_fields.get("privacy", "not_run"),
            "provider_registry_status": self.status_fields.get("provider_registry", "not_run"),
            "provider_selection_status": self.status_fields.get("provider_selection", "not_run"),
            "providers": list(self.providers),
            "registry_decision": self.registry_decision,
            "registry_decision_label": self.registry_decision_label,
            "reporting_boundary_status": self.status_fields.get("reporting_boundary", "not_run"),
            "request_contract_status": self.status_fields.get("requests", "not_run"),
            "response_contract_status": self.status_fields.get("responses", "not_run"),
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "shared_guarantees": list(self.shared_guarantees),
            "slice_id": self.slice_id,
            "total_checks": self.check_counts.get("total", 0),
            "usage_status": self.status_fields.get("usage", "not_run"),
            "verdict": self.verdict,
            "verification_id": self.verification_id,
            "verification_version": self.verification_version,
            "warnings": list(self.warnings),
        }
        return {key: payload[key] for key in sorted(payload)}

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def write_markdown(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Cross-Provider Contract Verification (Epic 11, Slice 11.8)",
            "",
            f"- Verdict: **{self.verdict}**",
            f"- Providers: {', '.join(self.providers)}",
            f"- Registry decision: **{self.registry_decision}** "
            f"({self.registry_decision_label})",
            "- Compatibility requirements checked: "
            f"{', '.join(self.compatibility_requirement_ids)}",
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
        lines.extend(["", "## Shared guarantees", ""])
        for item in self.shared_guarantees:
            lines.append(f"- {item}")
        lines.extend(["", "## Intentional differences", ""])
        for item in self.intentional_differences:
            lines.append(f"- {item}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


__all__ = [
    "CheckResult",
    "CrossProviderVerificationReport",
    "ScenarioResult",
    "build_check_counts",
    "category_status",
]
