"""Authoritative Epic 11 slice completion matrix for SV.11.13."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_PRIOR_VERDICTS: frozenset[str] = frozenset({"pass", "pass_with_limitations"})


@dataclass(frozen=True, slots=True)
class SliceSpec:
    slice_id: str
    package: str
    schema_name: str
    report_relative: str
    is_self: bool = False

    @property
    def package_dir(self) -> str:
        return f"verification/{self.package}"

    @property
    def tests_dir(self) -> str:
        return f"tests/verification/{self.package}"


SLICE_SPECS: tuple[SliceSpec, ...] = (
    SliceSpec(
        "11.1",
        "ai_provider_baseline",
        "ai-provider-compatibility-baseline",
        "reports/verification/sv11-1/ai-provider-compatibility-baseline.json",
    ),
    SliceSpec(
        "11.2",
        "ai_provider_contracts",
        "ai-provider-contract-verification",
        "reports/verification/sv11-2/ai-provider-contract-verification.json",
    ),
    SliceSpec(
        "11.3",
        "ai_provider_configuration",
        "ai-provider-configuration-verification",
        "reports/verification/sv11-3/ai-provider-configuration-verification.json",
    ),
    SliceSpec(
        "11.4",
        "ai_provider_execution",
        "ai-provider-execution-verification",
        "reports/verification/sv11-4/ai-provider-execution-verification.json",
    ),
    SliceSpec(
        "11.5",
        "ai_provider_capabilities",
        "ai-provider-capability-verification",
        "reports/verification/sv11-5/ai-provider-capability-verification.json",
    ),
    SliceSpec(
        "11.6",
        "openai_provider_migration",
        "openai-provider-migration-verification",
        "reports/verification/sv11-6/openai-provider-migration-verification.json",
    ),
    SliceSpec(
        "11.7",
        "bedrock_provider_migration",
        "bedrock-provider-migration-verification",
        "reports/verification/sv11-7/bedrock-provider-migration-verification.json",
    ),
    SliceSpec(
        "11.8",
        "ai_provider_cross_provider",
        "ai-provider-cross-provider-verification",
        "reports/verification/sv11-8/ai-provider-cross-provider-verification.json",
    ),
    SliceSpec(
        "11.9",
        "openrouter_provider",
        "openrouter-provider-verification",
        "reports/verification/sv11-9/openrouter-provider-verification.json",
    ),
    SliceSpec(
        "11.10",
        "openrouter_configuration",
        "openrouter-configuration-verification",
        "reports/verification/sv11-10/openrouter-configuration-verification.json",
    ),
    SliceSpec(
        "11.11",
        "openrouter_doctor_integration",
        "openrouter-doctor-integration-verification",
        "reports/verification/sv11-11/openrouter-doctor-integration-verification.json",
    ),
    SliceSpec(
        "11.12",
        "ai_provider_privacy_boundaries",
        "ai-provider-privacy-boundary-verification",
        "reports/verification/sv11-12/ai-provider-privacy-boundary-verification.json",
    ),
    SliceSpec(
        "11.13",
        "ai_provider_platform_completion",
        "ai-provider-platform-completion-verification",
        "reports/verification/sv11-13/ai-provider-platform-completion-verification.json",
        is_self=True,
    ),
)


def load_report(engine_root: Path, relative: str) -> dict[str, Any] | None:
    path = engine_root / relative
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def report_failed_count(payload: dict[str, Any]) -> int:
    if "failed_checks" in payload:
        return int(payload["failed_checks"])
    counts = payload.get("check_counts") or {}
    if "failed" in counts:
        return int(counts["failed"])
    return -1


def evaluate_slice(
    engine_root: Path,
    spec: SliceSpec,
    *,
    treat_self_complete: bool,
) -> dict[str, Any]:
    package_ok = (engine_root / spec.package_dir).is_dir()
    tests_ok = (engine_root / spec.tests_dir).is_dir()
    contract_ok = (engine_root / spec.package_dir / "contract.py").is_file()

    if spec.is_self:
        complete = treat_self_complete and package_ok and tests_ok and contract_ok
        return {
            "complete": complete,
            "failed_checks": 0 if complete else None,
            "package": spec.package,
            "package_exists": package_ok,
            "report_exists": treat_self_complete,
            "report_relative": spec.report_relative,
            "schema_name": spec.schema_name,
            "schema_match": True,
            "self": True,
            "slice_id": spec.slice_id,
            "tests_exist": tests_ok,
            "contract_exists": contract_ok,
            "verdict": "pass_with_limitations" if complete else None,
        }

    payload = load_report(engine_root, spec.report_relative)
    report_exists = payload is not None
    schema_match = bool(payload and payload.get("schema_name") == spec.schema_name)
    verdict = payload.get("verdict") if payload else None
    failed = report_failed_count(payload) if payload else None
    verdict_ok = verdict in ALLOWED_PRIOR_VERDICTS
    failed_ok = failed == 0
    complete = (
        package_ok
        and report_exists
        and schema_match
        and verdict_ok
        and failed_ok
    )
    return {
        "complete": complete,
        "failed_checks": failed,
        "package": spec.package,
        "package_exists": package_ok,
        "report_exists": report_exists,
        "report_relative": spec.report_relative,
        "schema_name": spec.schema_name,
        "schema_match": schema_match,
        "self": False,
        "slice_id": spec.slice_id,
        "tests_exist": tests_ok,
        "verdict": verdict,
    }


def build_slice_matrix(
    engine_root: Path, *, treat_self_complete: bool = True
) -> list[dict[str, Any]]:
    return [
        evaluate_slice(engine_root, spec, treat_self_complete=treat_self_complete)
        for spec in SLICE_SPECS
    ]


def sorted_slice_matrix(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(matrix, key=lambda row: row["slice_id"])


__all__ = [
    "ALLOWED_PRIOR_VERDICTS",
    "SLICE_SPECS",
    "SliceSpec",
    "build_slice_matrix",
    "evaluate_slice",
    "load_report",
    "report_failed_count",
    "sorted_slice_matrix",
]
