"""Every SV.11.6 check module passes, and each check is well formed.

The suite is asserted category by category so a regression names the area that
broke rather than only the aggregate count.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from verification.openai_provider_migration.contract import PACKAGE_RELATIVE_PATH
from verification.openai_provider_migration.models import CheckResult

from verification.openai_provider_migration import (
    authentication,
    baseline_compatibility,
    configuration,
    dependency_boundary,
    doctor,
    errors,
    execution,
    fail_soft,
    inventory,
    mixed_mode,
    privacy,
    reporting_boundary,
    requests,
    responses,
    usage,
)

ENGINE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


def _run(runner: Any, *args: Any) -> tuple[list[CheckResult], dict[str, Any]]:
    return runner(*args)


_CHECK_RUNNERS: dict[str, tuple[Any, tuple[Any, ...]]] = {
    "authentication": (authentication.run_authentication_checks, ()),
    "baseline_compatibility": (baseline_compatibility.run_baseline_compatibility_checks, ()),
    "configuration": (configuration.run_configuration_checks, ()),
    "dependency_boundary": (
        dependency_boundary.run_dependency_boundary_checks,
        (ENGINE_ROOT, PACKAGE_DIR),
    ),
    "doctor": (doctor.run_doctor_checks, (ENGINE_ROOT,)),
    "errors": (errors.run_error_checks, ()),
    "execution": (execution.run_execution_checks, ()),
    "fail_soft": (fail_soft.run_fail_soft_checks, ()),
    "inventory": (inventory.run_inventory_checks, (ENGINE_ROOT, PACKAGE_DIR)),
    "mixed_mode": (mixed_mode.run_mixed_mode_checks, (ENGINE_ROOT,)),
    "privacy": (privacy.run_adapter_privacy_checks, ()),
    "reporting_boundary": (reporting_boundary.run_reporting_boundary_checks, (PACKAGE_DIR,)),
    "requests": (requests.run_request_checks, ()),
    "responses": (responses.run_response_checks, ()),
    "usage": (usage.run_usage_checks, ()),
}


@pytest.mark.parametrize("category", sorted(_CHECK_RUNNERS))
def test_every_check_in_the_category_passes(category: str) -> None:
    runner, args = _CHECK_RUNNERS[category]
    checks, _ = _run(runner, *args)

    failures = [(check.name, check.detail) for check in checks if not check.ok]
    assert not failures, failures


@pytest.mark.parametrize("category", sorted(_CHECK_RUNNERS))
def test_every_check_is_well_formed(category: str) -> None:
    runner, args = _CHECK_RUNNERS[category]
    checks, matrix = _run(runner, *args)

    assert checks, f"{category} produced no checks"
    assert isinstance(matrix, dict)
    for check in checks:
        assert check.name and check.name == check.name.lower()
        assert " " not in check.name
        assert check.detail, f"{check.name} has no detail"


@pytest.mark.parametrize("category", sorted(_CHECK_RUNNERS))
def test_check_names_are_unique_within_a_category(category: str) -> None:
    runner, args = _CHECK_RUNNERS[category]
    checks, _ = _run(runner, *args)

    names = [check.name for check in checks]
    assert len(names) == len(set(names))


def test_check_names_are_unique_across_all_categories() -> None:
    names: list[str] = []
    for runner, args in _CHECK_RUNNERS.values():
        checks, _ = _run(runner, *args)
        names.extend(check.name for check in checks)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, duplicates


def test_each_check_reports_its_own_category() -> None:
    for category, (runner, args) in _CHECK_RUNNERS.items():
        checks, _ = _run(runner, *args)
        mislabeled = sorted({check.category for check in checks} - {category})
        assert not mislabeled, (category, mislabeled)


def test_the_suite_covers_a_meaningful_number_of_checks() -> None:
    total = sum(len(_run(runner, *args)[0]) for runner, args in _CHECK_RUNNERS.values())
    assert total >= 120
