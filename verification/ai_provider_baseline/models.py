"""Deterministic report models for the AI Provider Compatibility Baseline (SV.11.1).

These dataclasses define the shape of ``ai-provider-compatibility-baseline.json``.
Every collection is stored pre-sorted so two runs over an unchanged Engine
checkout produce byte-identical JSON (no wall-clock timestamps, no unordered
sets, no absolute paths).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One named characterization check."""

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
class CouplingInventoryEntry:
    """Structural inventory of one existing Engine source module.

    ``module`` is a relative dotted path (e.g. ``ai.providers.bedrock``) —
    never an absolute filesystem path.
    """

    module: str
    classes: tuple[dict[str, Any], ...] = ()
    functions: tuple[str, ...] = ()
    internal_imports: tuple[str, ...] = ()
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "classes": list(self.classes),
            "functions": list(self.functions),
            "internal_imports": list(self.internal_imports),
            "line_count": self.line_count,
            "module": self.module,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityRequirement:
    """A requirement future Slice 11.2+ work must satisfy — not implemented here."""

    requirement_id: str
    description: str
    rationale: str
    applies_to: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "applies_to": list(self.applies_to),
            "description": self.description,
            "rationale": self.rationale,
            "requirement_id": self.requirement_id,
        }


@dataclass(frozen=True, slots=True)
class IntentionalDifference:
    """A deliberate, documented behavioral difference between bedrock and openai."""

    aspect: str
    bedrock: str
    openai: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "aspect": self.aspect,
            "bedrock": self.bedrock,
            "openai": self.openai,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class BaselineReport:
    """Full AI Provider Compatibility Baseline report (SV.11.1)."""

    schema_name: str
    schema_version: str
    verification_id: str
    verification_version: str
    epic: str
    slice_id: str
    verdict: str
    providers: tuple[str, ...]
    default_provider: str
    provider_family_map: dict[str, str]
    default_model_ids: dict[str, str]
    model_invocation_defaults: dict[str, Any]
    assess_advisor_max_output_tokens: int
    assessment_schema_version: str
    invoke_calls_per_assess_run: int
    settings_timeout_max_retries_wired: bool
    existing_coupling_surface: tuple[str, ...]
    coupling_inventory: tuple[CouplingInventoryEntry, ...]
    matrices: dict[str, Any]
    compatibility_requirements: tuple[CompatibilityRequirement, ...]
    intentional_differences: tuple[IntentionalDifference, ...]
    negative_scenarios: tuple[ScenarioResult, ...]
    checks: tuple[CheckResult, ...]
    limitations: tuple[str, ...]
    warnings: tuple[str, ...]
    notes: tuple[str, ...]
    check_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "assess_advisor_max_output_tokens": self.assess_advisor_max_output_tokens,
            "assessment_schema_version": self.assessment_schema_version,
            "check_counts": dict(sorted(self.check_counts.items())),
            "checks": [c.to_dict() for c in self.checks],
            "compatibility_requirements": [c.to_dict() for c in self.compatibility_requirements],
            "coupling_inventory": [c.to_dict() for c in self.coupling_inventory],
            "default_model_ids": dict(sorted(self.default_model_ids.items())),
            "default_provider": self.default_provider,
            "epic": self.epic,
            "existing_coupling_surface": list(self.existing_coupling_surface),
            "intentional_differences": [d.to_dict() for d in self.intentional_differences],
            "invoke_calls_per_assess_run": self.invoke_calls_per_assess_run,
            "limitations": list(self.limitations),
            "matrices": self.matrices,
            "model_invocation_defaults": dict(sorted(self.model_invocation_defaults.items())),
            "negative_scenarios": [s.to_dict() for s in self.negative_scenarios],
            "notes": list(self.notes),
            "provider_family_map": dict(sorted(self.provider_family_map.items())),
            "providers": list(self.providers),
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "settings_timeout_max_retries_wired": self.settings_timeout_max_retries_wired,
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
            "# AI Provider Compatibility Baseline (Epic 11, Slice 11.1)",
            "",
            f"- Verdict: **{self.verdict}**",
            f"- Providers (Engine IDs): {', '.join(self.providers)}",
            f"- Default provider: `{self.default_provider}`",
            f"- Assessment schema version: `{self.assessment_schema_version}`",
            f"- Invoke calls per assess run: {self.invoke_calls_per_assess_run}",
            (
                "- `[ai.bedrock]`/`[ai.openai]` `timeout_seconds`/`max_retries` wired "
                f"into assess factory: {self.settings_timeout_max_retries_wired}"
            ),
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
        lines.append("## Compatibility requirements for Slice 11.2+")
        lines.append("")
        for req in self.compatibility_requirements:
            lines.append(f"- **{req.requirement_id}**: {req.description}")
        lines.append("")
        text = "\n".join(lines) + "\n"
        path.write_text(text, encoding="utf-8")
        return path


def build_check_counts(checks: list[CheckResult]) -> dict[str, int]:
    passed = sum(1 for c in checks if c.ok)
    failed = sum(1 for c in checks if not c.ok)
    return {"failed": failed, "passed": passed, "total": len(checks)}


def dataclass_to_sorted_dict(instance: Any) -> dict[str, Any]:
    """Generic helper: dataclass -> dict with sorted keys (test/debug use)."""

    return {key: value for key, value in sorted(asdict(instance).items())}
