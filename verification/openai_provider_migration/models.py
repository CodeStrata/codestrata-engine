"""Deterministic report models for SV.11.6 OpenAI Provider Migration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One named verification check."""

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
    """One negative scenario (A-Z): a forbidden condition that must NOT hold."""

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


@dataclass(frozen=True, slots=True)
class OpenAIMigrationVerificationReport:
    """Full SV.11.6 OpenAI Provider Migration verification report."""

    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: str
    slice_id: str
    verdict: str
    package_dotted_name: str
    compatibility_requirement_ids: tuple[str, ...]
    matrices: dict[str, Any]
    negative_scenarios: tuple[ScenarioResult, ...]
    checks: tuple[CheckResult, ...]
    limitations: tuple[str, ...]
    warnings: tuple[str, ...]
    notes: tuple[str, ...]
    check_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [check.to_dict() for check in self.checks],
            "compatibility_requirement_ids": list(self.compatibility_requirement_ids),
            "epic": self.epic,
            "limitations": list(self.limitations),
            "matrices": self.matrices,
            "negative_scenarios": [scenario.to_dict() for scenario in self.negative_scenarios],
            "notes": list(self.notes),
            "package_dotted_name": self.package_dotted_name,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "slice_id": self.slice_id,
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
            "# OpenAI Provider Migration Verification (Epic 11, Slice 11.6)",
            "",
            f"- Verdict: **{self.verdict}**",
            f"- Package: `{self.package_dotted_name}`",
            "- Compatibility requirements checked: "
            f"{', '.join(self.compatibility_requirement_ids)}",
            f"- Negative scenarios: {len(self.negative_scenarios)}",
            "",
            "## Check counts",
            "",
        ]
        for key, value in sorted(self.check_counts.items()):
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("## Limitations")
        lines.append("")
        for item in self.limitations:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        for item in self.notes:
            lines.append(f"- {item}")
        lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


def build_check_counts(checks: list[CheckResult]) -> dict[str, int]:
    passed = sum(1 for check in checks if check.ok)
    failed = sum(1 for check in checks if not check.ok)
    return {"failed": failed, "passed": passed, "total": len(checks)}


__all__ = [
    "CheckResult",
    "OpenAIMigrationVerificationReport",
    "ScenarioResult",
    "build_check_counts",
]
