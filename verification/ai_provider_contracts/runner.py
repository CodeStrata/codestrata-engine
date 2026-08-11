"""SV.11.2 Common AI Provider Contracts verification — orchestration runner."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_contracts import (
    baseline_compatibility,
    dependency_boundary,
    inventory,
    privacy,
    reporting,
    scenarios,
)
from verification.ai_provider_contracts.contract import (
    PACKAGE_RELATIVE_PATH,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
)
from verification.ai_provider_contracts.models import CheckResult, ContractVerificationReport


def engine_root_from_package() -> Path:
    """Resolve the Engine repository root (directory containing pyproject.toml)."""

    # verification/ai_provider_contracts/runner.py -> parents[2] == engine/
    return Path(__file__).resolve().parents[2]


def _default_package_dir(engine_root: Path) -> Path:
    return engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


def _default_verification_dir(engine_root: Path) -> Path:
    return engine_root / "verification" / "ai_provider_contracts"


def _default_output_dir(engine_root: Path) -> Path:
    return engine_root / "reports" / "verification" / "sv11-2"


def run_ai_provider_contract_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    write_markdown: bool = True,
) -> ContractVerificationReport:
    """Run the full SV.11.2 verification suite and write the report."""

    engine = (engine_root or engine_root_from_package()).resolve()
    package_dir = _default_package_dir(engine)
    verification_dir = _default_verification_dir(engine)
    out = (output_dir or _default_output_dir(engine)).resolve()

    all_checks: list[CheckResult] = []
    matrices: dict[str, object] = {}

    def _collect(category: str, result: tuple[list[CheckResult], object]) -> None:
        checks, matrix = result
        all_checks.extend(checks)
        matrices[category] = matrix

    _collect("inventory", inventory.run_inventory_checks(engine, package_dir))
    _collect(
        "dependency_boundary",
        dependency_boundary.run_dependency_boundary_checks(engine, package_dir),
    )
    _collect("baseline_compatibility", baseline_compatibility.run_baseline_compatibility_checks())
    _collect("privacy", privacy.run_privacy_checks())

    value_object_checks = scenarios.run_value_object_negative_checks()
    all_checks.extend(value_object_checks)
    matrices["value_object_invariants"] = {
        "check_names": sorted(c.name for c in value_object_checks)
    }

    checks_by_name = {check.name: check for check in all_checks}
    report_payload_preview = {"matrices": matrices}
    negative_scenarios = scenarios.build_negative_scenarios(
        package_dir=package_dir,
        verification_dir=verification_dir,
        checks_by_name=checks_by_name,
        report_payload_preview=report_payload_preview,
    )

    report = reporting.assemble_report(
        all_checks=all_checks,
        matrices=matrices,
        negative_scenarios=negative_scenarios,
    )

    out.mkdir(parents=True, exist_ok=True)
    json_path = out / REPORT_FILENAME
    report.write_json(json_path)
    blob = json_path.read_text(encoding="utf-8")
    leaks = reporting.report_contains_forbidden_leak(blob)
    if leaks:
        raise RuntimeError(
            "contract verification report contains forbidden tokens "
            f"(categories only, no values): {sorted(leaks)}"
        )
    if write_markdown:
        report.write_markdown(out / REPORT_MD_FILENAME)
    return report


__all__ = ["engine_root_from_package", "run_ai_provider_contract_verification"]
