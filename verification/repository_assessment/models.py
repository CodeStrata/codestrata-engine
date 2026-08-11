"""Privacy-safe report models for SV.4."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from verification.repository_assessment.contract import (
    REPOSITORY_ASSESSMENT_VERIFICATION_ID,
    REPOSITORY_ASSESSMENT_VERIFICATION_VERSION,
)


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    ok: bool
    detail: str = ""
    catalog_id: str | None = None
    repository_id: str | None = None
    project_name: str | None = None
    github_repository: str | None = None
    qualified_revision_type: str | None = None
    qualified_revision_value: str | None = None
    checked_out_sha: str | None = None
    assessment_command: tuple[str, ...] = ()
    execution_mode: str = "deterministic_no_ai"
    exit_code: int | None = None
    duration_bucket: str | None = None
    expected_artifacts: tuple[str, ...] = ()
    actual_artifacts: tuple[str, ...] = ()
    artifact_validation: dict[str, str] = field(default_factory=dict)
    normalized_summary: dict[str, Any] = field(default_factory=dict)
    source_integrity: str = "not_run"
    network_behavior: str = "offline"
    telemetry_behavior: str = "disabled"
    determinism: str | None = None
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationReport:
    schema_name: str = REPOSITORY_ASSESSMENT_VERIFICATION_ID
    schema_version: str = REPOSITORY_ASSESSMENT_VERIFICATION_VERSION
    verification_id: str = REPOSITORY_ASSESSMENT_VERIFICATION_ID
    ok: bool = False
    verdict: str = "fail"
    catalog_id: str | None = None
    installation_method: str = "pip_path_non_editable"
    platform: str = ""
    python_version: str = ""
    cli_version: str | None = None
    scenarios: tuple[ScenarioResult, ...] = ()
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
            "ok": self.ok,
            "verdict": self.verdict,
            "catalog_id": self.catalog_id,
            "installation_method": self.installation_method,
            "platform": self.platform,
            "python_version": self.python_version,
            "cli_version": self.cli_version,
            "scenarios": [asdict(item) for item in self.scenarios],
            "warnings": list(self.warnings),
            "failures": list(self.failures),
            "limitations": list(self.limitations),
            "elapsed_ms": self.elapsed_ms,
        }
        return {key: payload[key] for key in sorted(payload)}

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
