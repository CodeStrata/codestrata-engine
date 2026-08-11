"""Unit tests for verification.ai_provider_configuration.baseline_compatibility."""

from __future__ import annotations

from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_configuration.baseline_compatibility import (
    run_baseline_compatibility_checks,
)
from verification.ai_provider_configuration.contract import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)


def test_baseline_defines_cr1_through_cr6_for_real() -> None:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    assert ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_run_baseline_compatibility_checks_all_pass() -> None:
    checks, matrix = run_baseline_compatibility_checks()
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]
    assert set(matrix["requirement_ids"]) == set(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)
    assert all(matrix["statement_holds_by_requirement_id"].values())


def test_default_provider_and_model_ids_match_the_real_loaded_baseline() -> None:
    from verification.ai_provider_configuration.baseline_compatibility import (
        check_default_model_ids_match_baseline,
        check_default_provider_matches_baseline,
    )

    assert check_default_provider_matches_baseline().ok is True
    assert check_default_model_ids_match_baseline().ok is True
