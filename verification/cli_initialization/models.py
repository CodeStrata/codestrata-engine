"""Report models for SV.3 (privacy-safe, no absolute paths)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from verification.cli_initialization.contract import (
    CLI_INITIALIZATION_VERIFICATION_ID,
    CLI_INITIALIZATION_VERIFICATION_VERSION,
)


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    ok: bool
    detail: str = ""
    commands: tuple[dict[str, Any], ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    actual_artifacts: tuple[str, ...] = ()
    artifact_digests: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    classifications: dict[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationReport:
    schema_name: str = CLI_INITIALIZATION_VERIFICATION_ID
    schema_version: str = CLI_INITIALIZATION_VERIFICATION_VERSION
    verification_id: str = CLI_INITIALIZATION_VERIFICATION_ID
    ok: bool = False
    verdict: str = "fail"
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
        payload: dict[str, Any] = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
            "ok": self.ok,
            "verdict": self.verdict,
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
