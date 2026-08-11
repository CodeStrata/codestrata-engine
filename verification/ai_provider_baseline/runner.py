"""SV.11.1 AI Provider Compatibility Baseline — orchestration runner."""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_baseline import (
    assessment_integration,
    authentication,
    boundaries,
    capabilities,
    configuration,
    diagnostics,
    errors,
    fail_soft,
    inventory,
    provider_selection,
    reporting,
    reporting_integration,
    responses,
    retries,
    scenarios,
    timeouts,
    usage,
)
from verification.ai_provider_baseline import (
    requests as requests_module,
)
from verification.ai_provider_baseline.contract import (
    OUTPUT_RELATIVE,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
)
from verification.ai_provider_baseline.models import BaselineReport, CheckResult


def engine_root_from_package() -> Path:
    """Resolve the Engine repository root (directory containing pyproject.toml)."""

    # verification/ai_provider_baseline/runner.py -> parents[2] == engine/
    return Path(__file__).resolve().parents[2]


def _default_source_root(engine_root: Path) -> Path:
    return engine_root / "src" / "codestrata"


def _default_output_dir(engine_root: Path) -> Path:
    return engine_root / OUTPUT_RELATIVE


def run_ai_provider_baseline(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    write_markdown: bool = True,
) -> BaselineReport:
    """Run the full SV.11.1 characterization suite and write the report."""

    engine = (engine_root or engine_root_from_package()).resolve()
    source_root = _default_source_root(engine)
    out = (output_dir or _default_output_dir(engine)).resolve()

    all_checks: list[CheckResult] = []
    matrices: dict[str, object] = {}

    def _collect(category: str, result: tuple[list[CheckResult], object]) -> None:
        checks, matrix = result
        all_checks.extend(checks)
        matrices[category] = matrix

    _collect("provider_selection", provider_selection.run_provider_selection_checks(source_root))
    _collect("configuration", configuration.run_configuration_checks(source_root))
    _collect("authentication", authentication.run_authentication_checks(source_root))
    _collect("requests", requests_module.run_request_checks(source_root))
    _collect("responses", responses.run_response_checks(source_root))
    _collect("timeouts", timeouts.run_timeout_checks(source_root))
    _collect("retries", retries.run_retry_checks(source_root))
    _collect("errors", errors.run_error_checks(source_root))
    _collect("diagnostics", diagnostics.run_diagnostics_checks(source_root))
    _collect("usage", usage.run_usage_checks(source_root))
    _collect("capabilities", capabilities.run_capability_checks(source_root))
    _collect("fail_soft", fail_soft.run_fail_soft_checks(source_root))
    _collect(
        "assessment_integration",
        assessment_integration.run_assessment_integration_checks(source_root),
    )
    _collect(
        "reporting_integration",
        reporting_integration.run_reporting_integration_checks(source_root),
    )
    _collect("boundaries", boundaries.run_boundary_checks(source_root))

    coupling_inventory = inventory.build_coupling_inventory(source_root)

    checks_by_name = {check.name: check for check in all_checks}
    report_payload_preview = {
        "coupling_inventory": [entry.to_dict() for entry in coupling_inventory],
        "matrices": matrices,
    }
    negative_scenarios = scenarios.build_negative_scenarios(
        source_root,
        checks_by_name=checks_by_name,
        report_payload_preview=report_payload_preview,
    )

    report = reporting.assemble_report(
        all_checks=all_checks,
        coupling_inventory=coupling_inventory,
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
            "baseline report contains forbidden tokens "
            f"(categories only, no values): {sorted(leaks)}"
        )
    if write_markdown:
        report.write_markdown(out / REPORT_MD_FILENAME)
    return report


__all__ = ["engine_root_from_package", "run_ai_provider_baseline"]
