"""Privacy-safe report models for SV.5."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from verification.assessment_report.contract import (
    ASSESSMENT_REPORT_VERIFICATION_ID,
    ASSESSMENT_REPORT_VERIFICATION_VERSION,
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    category: str = "structural"


@dataclass(frozen=True, slots=True)
class RunVerification:
    run_id: str
    source: str  # local_fixture | catalog
    repository_id: str | None
    project_name: str | None
    github_repository: str | None
    qualified_revision_type: str | None
    qualified_revision_value: str | None
    assessment_run_reference: str  # catalog- or fixture-relative, never absolute
    ok: bool
    artifact_inventory: dict[str, str] = field(default_factory=dict)
    report_schema_version: str | None = None
    structural_checks: tuple[CheckResult, ...] = ()
    traceability_checks: tuple[CheckResult, ...] = ()
    parity_checks: tuple[CheckResult, ...] = ()
    html_checks: tuple[CheckResult, ...] = ()
    credibility_checks: tuple[CheckResult, ...] = ()
    determinism_checks: tuple[CheckResult, ...] = ()
    privacy_checks: tuple[CheckResult, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationReport:
    schema_name: str = ASSESSMENT_REPORT_VERIFICATION_ID
    schema_version: str = ASSESSMENT_REPORT_VERIFICATION_VERSION
    verification_id: str = ASSESSMENT_REPORT_VERIFICATION_ID
    ok: bool = False
    verdict: str = "fail"
    runs: tuple[RunVerification, ...] = ()
    negative_scenarios: tuple[CheckResult, ...] = ()
    defects: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        def checks(items: tuple[CheckResult, ...]) -> list[dict[str, Any]]:
            return [asdict(item) for item in items]

        payload = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
            "ok": self.ok,
            "verdict": self.verdict,
            "runs": [
                {
                    "run_id": run.run_id,
                    "source": run.source,
                    "repository_id": run.repository_id,
                    "project_name": run.project_name,
                    "github_repository": run.github_repository,
                    "qualified_revision_type": run.qualified_revision_type,
                    "qualified_revision_value": run.qualified_revision_value,
                    "assessment_run_reference": run.assessment_run_reference,
                    "ok": run.ok,
                    "artifact_inventory": run.artifact_inventory,
                    "report_schema_version": run.report_schema_version,
                    "structural_checks": checks(run.structural_checks),
                    "traceability_checks": checks(run.traceability_checks),
                    "parity_checks": checks(run.parity_checks),
                    "html_checks": checks(run.html_checks),
                    "credibility_checks": checks(run.credibility_checks),
                    "determinism_checks": checks(run.determinism_checks),
                    "privacy_checks": checks(run.privacy_checks),
                    "counts": run.counts,
                    "failures": list(run.failures),
                    "warnings": list(run.warnings),
                    "limitations": list(run.limitations),
                }
                for run in self.runs
            ],
            "negative_scenarios": checks(self.negative_scenarios),
            "defects": list(self.defects),
            "warnings": list(self.warnings),
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
