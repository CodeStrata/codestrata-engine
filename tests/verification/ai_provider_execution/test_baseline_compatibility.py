"""Unit tests for verification.ai_provider_execution.baseline_compatibility."""

from __future__ import annotations

from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_execution.baseline_compatibility import (
    run_baseline_compatibility_checks,
)
from verification.ai_provider_execution.contract import REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_baseline_defines_cr1_through_cr6_for_real() -> None:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    assert ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_run_baseline_compatibility_checks_all_pass() -> None:
    checks, matrix = run_baseline_compatibility_checks()
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]
    assert set(matrix["requirement_ids"]) == set(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)
    assert all(matrix["statement_holds_by_requirement_id"].values())


def test_default_retry_policy_matches_cr1() -> None:
    from verification.ai_provider_execution.baseline_compatibility import (
        check_default_retry_policy_matches_cr1_exact_one_invoke,
    )

    assert check_default_retry_policy_matches_cr1_exact_one_invoke().ok is True


def test_settings_representable_retry_policy_matches_real_settings_default() -> None:
    from verification.ai_provider_execution.baseline_compatibility import (
        check_settings_representable_retry_policy_matches_real_settings_default,
    )

    assert check_settings_representable_retry_policy_matches_real_settings_default().ok is True


def test_default_timeout_seconds_matches_real_providers_default() -> None:
    from verification.ai_provider_execution.baseline_compatibility import (
        check_default_timeout_seconds_matches_real_providers_default,
    )

    assert check_default_timeout_seconds_matches_real_providers_default().ok is True
