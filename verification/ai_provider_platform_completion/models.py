"""Deterministic report models for SV.11.13."""

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
class AIProviderPlatformCompletionVerificationReport:
    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: int
    release: str
    slice_id: str
    verdict: str
    completed_slices: int
    total_slices: int
    start_epic_12: bool
    providers: tuple[str, ...]
    provider_default: str
    provider_selection: dict[str, Any]
    registry_decision: str
    registry_decision_label: str
    compatibility_requirements: tuple[str, ...]
    policy_registry: dict[str, str]
    schema_registry: dict[str, str]
    slice_matrix: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    negative_scenarios: tuple[ScenarioResult, ...]
    check_counts: dict[str, int]
    status_fields: dict[str, str]
    release_posture: dict[str, bool]
    notes: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

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
            "bedrock_migration_status": self.status_fields.get("migrations", "not_run"),
            "blockers": list(self.blockers),
            "capability_status": self.status_fields.get("capabilities", "not_run"),
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [c.to_dict() for c in self.checks],
            "cli_status": self.status_fields.get("cli", "not_run"),
            "compatibility_requirements": list(self.compatibility_requirements),
            "completed_slices": self.completed_slices,
            "configuration_status": self.status_fields.get("configuration", "not_run"),
            "defects": defects,
            "dependency_status": self.status_fields.get("dependency_boundary", "not_run"),
            "doctor_status": self.status_fields.get("doctor", "not_run"),
            "documentation_status": self.status_fields.get("documentation", "not_run"),
            "epic": self.epic,
            "epic12_absent_status": self.status_fields.get("epic12_absence", "not_run"),
            "execution_status": self.status_fields.get("execution", "not_run"),
            "failed_checks": self.check_counts.get("failed", 0),
            "failure_isolation_status": self.status_fields.get("failure_isolation", "not_run"),
            "limitations": list(self.limitations),
            "negative_scenario_count": len(self.negative_scenarios),
            "negative_scenarios": [s.to_dict() for s in self.negative_scenarios],
            "notes": list(self.notes),
            "openai_migration_status": self.status_fields.get("migrations", "not_run"),
            "openrouter_status": self.status_fields.get("openrouter", "not_run"),
            "packaging_status": self.status_fields.get("packaging", "not_run"),
            "policy_registry": dict(sorted(self.policy_registry.items())),
            "privacy_status": self.status_fields.get("privacy", "not_run"),
            "provider_default": self.provider_default,
            "provider_selection": self.provider_selection,
            "providers": list(self.providers),
            "public_export_status": self.status_fields.get("public_export", "not_run"),
            "registry_decision": self.registry_decision,
            "registry_decision_label": self.registry_decision_label,
            "release": self.release,
            "release_posture": dict(sorted(self.release_posture.items())),
            "reporting_boundary_status": self.status_fields.get(
                "reporting_boundary", "not_run"
            ),
            "schema_name": self.schema_name,
            "schema_registry": dict(sorted(self.schema_registry.items())),
            "schema_version": self.schema_version,
            "slice_id": self.slice_id,
            "slice_matrix": list(self.slice_matrix),
            "start_epic_12": self.start_epic_12,
            "total_checks": self.check_counts.get("total", 0),
            "total_slices": self.total_slices,
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
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    def write_markdown(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# AI Provider Platform Completion Verification (Epic 11, Slice 11.13)",
            "",
            f"- Verdict: **{self.verdict}**",
            f"- Completed slices: {self.completed_slices}/{self.total_slices}",
            f"- Providers: {', '.join(self.providers)}",
            f"- Default provider: {self.provider_default}",
            f"- start_epic_12: {self.start_epic_12}",
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
    "AIProviderPlatformCompletionVerificationReport",
    "CheckResult",
    "ScenarioResult",
    "build_check_counts",
    "category_status",
]
