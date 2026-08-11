"""Reporting boundary: schema 1.2, unchanged sections, and no new report surface.

Slice 11.6 changes *how* an OpenAI call is made, never *what* an assessment
report contains. These checks pin the report schema version, the presence of the
Findings/Evidence/Recommendations surface, the AI execution status vocabulary the
assess layer derives from provider failures, and the fact that the adapter never
reaches the reporting layer at all.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.modernization_models import AIExecutionStatus
from verification.openai_provider_migration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    EXPECTED_MODULES,
    PACKAGE_RELATIVE_PATH,
)
from verification.openai_provider_migration.models import CheckResult

# The AI execution statuses the assess layer can report. Frozen here so a new
# status (or a renamed one) shows up as a reporting-surface change.
_EXPECTED_AI_EXECUTION_STATUSES: tuple[str, ...] = tuple(
    sorted(status.value for status in AIExecutionStatus)
)

_REPORTING_PREFIXES: tuple[str, ...] = (
    "codestrata.analytics",
    "codestrata.datalake",
    "codestrata.reporting",
    "codestrata.telemetry",
)


def check_the_assessment_schema_version_is_unchanged() -> CheckResult:
    return CheckResult(
        name="the_assessment_report_schema_version_is_still_1_2",
        category="reporting_boundary",
        ok=ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION,
        detail=f"schema_version={ASSESSMENT_JSON_SCHEMA_VERSION}",
    )


def check_the_adapter_never_imports_the_reporting_layer(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        hits = sorted(name for name in names if name.startswith(_REPORTING_PREFIXES))
        if hits:
            offenders[filename] = hits
    return CheckResult(
        name="the_adapter_never_imports_reporting_analytics_telemetry_or_the_data_lake",
        category="reporting_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
        evidence={"forbidden_prefixes": list(_REPORTING_PREFIXES)},
    )


def check_the_ai_execution_status_vocabulary_is_unchanged() -> CheckResult:
    expected = (
        "authentication_failed",
        "not_requested",
        "parsing_failed",
        "provider_failed",
        "succeeded",
        "validation_failed",
    )
    return CheckResult(
        name="the_ai_execution_status_vocabulary_is_unchanged",
        category="reporting_boundary",
        ok=_EXPECTED_AI_EXECUTION_STATUSES == expected,
        detail=f"ai_execution_statuses={list(_EXPECTED_AI_EXECUTION_STATUSES)}",
    )


def check_the_report_sections_are_unchanged() -> CheckResult:
    """Findings and Recommendations remain core enabled assessment sections."""

    from codestrata.reporting.contract.constants import CORE_ENABLED_SECTIONS

    required = ("findings", "recommendations")
    missing = sorted(name for name in required if name not in CORE_ENABLED_SECTIONS)
    return CheckResult(
        name="the_findings_and_recommendations_sections_remain_core_and_enabled",
        category="reporting_boundary",
        ok=not missing,
        detail=f"missing_core_sections={missing}",
        evidence={"core_enabled_sections": sorted(CORE_ENABLED_SECTIONS)},
    )


def check_the_adapter_adds_no_report_field(package_dir: Path) -> CheckResult:
    """No adapter module writes a report: nothing here serializes an assessment."""

    offenders: list[str] = []
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in ("write_text(", "json.dump", "open(")):
            offenders.append(filename)
    return CheckResult(
        name="no_adapter_module_writes_a_report_or_touches_the_filesystem",
        category="reporting_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
    )


def check_the_adapter_package_location_is_stable() -> CheckResult:
    return CheckResult(
        name="the_adapter_lives_under_the_documented_provider_adapters_path",
        category="reporting_boundary",
        ok=PACKAGE_RELATIVE_PATH == "ai/provider_adapters/openai",
        detail=f"package_relative_path={PACKAGE_RELATIVE_PATH}",
    )


def run_reporting_boundary_checks(
    package_dir: Path,
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_assessment_schema_version_is_unchanged(),
        check_the_adapter_never_imports_the_reporting_layer(package_dir),
        check_the_ai_execution_status_vocabulary_is_unchanged(),
        check_the_report_sections_are_unchanged(),
        check_the_adapter_adds_no_report_field(package_dir),
        check_the_adapter_package_location_is_stable(),
    ]
    matrix: dict[str, Any] = {
        "ai_execution_statuses": list(_EXPECTED_AI_EXECUTION_STATUSES),
        "assessment_schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "forbidden_reporting_prefixes": list(_REPORTING_PREFIXES),
    }
    return checks, matrix


__all__ = [
    "check_the_adapter_adds_no_report_field",
    "check_the_adapter_never_imports_the_reporting_layer",
    "check_the_adapter_package_location_is_stable",
    "check_the_ai_execution_status_vocabulary_is_unchanged",
    "check_the_assessment_schema_version_is_unchanged",
    "check_the_report_sections_are_unchanged",
    "run_reporting_boundary_checks",
]
