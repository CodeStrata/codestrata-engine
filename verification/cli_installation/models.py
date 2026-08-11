"""Deterministic report models for SV.2 CLI installation verification."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from verification.cli_installation.contract import (
    CLI_INSTALLATION_VERIFICATION_ID,
    CLI_INSTALLATION_VERIFICATION_VERSION,
)


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    """One named verification check."""

    name: str
    ok: bool
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Aggregate deterministic verification report."""

    schema_name: str = CLI_INSTALLATION_VERIFICATION_ID
    schema_version: str = CLI_INSTALLATION_VERIFICATION_VERSION
    ok: bool = False
    codestrata_version: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    commands: tuple[dict[str, Any], ...] = ()
    checks: tuple[VerificationCheck, ...] = ()
    failures: tuple[str, ...] = ()
    summary: str = ""
    elapsed_ms: float = 0.0
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "ok": self.ok,
            "codestrata_version": self.codestrata_version,
            "environment": dict(sorted(self.environment.items())),
            "commands": list(self.commands),
            "checks": [asdict(item) for item in self.checks],
            "failures": list(self.failures),
            "summary": self.summary,
            "elapsed_ms": self.elapsed_ms,
            "report_path": self.report_path,
        }
        return {key: payload[key] for key in sorted(payload)}

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path


def build_report(
    *,
    ok: bool,
    checks: list[VerificationCheck],
    environment: dict[str, Any],
    commands: list[dict[str, Any]],
    codestrata_version: str | None,
    elapsed_ms: float,
    report_path: str | None = None,
) -> VerificationReport:
    failures = tuple(item.name for item in checks if not item.ok)
    summary = "pass" if ok and not failures else f"failed checks: {list(failures)}"
    return VerificationReport(
        ok=ok and not failures,
        codestrata_version=codestrata_version,
        environment=environment,
        commands=tuple(commands),
        checks=tuple(checks),
        failures=failures,
        summary=summary,
        elapsed_ms=elapsed_ms,
        report_path=report_path,
    )
