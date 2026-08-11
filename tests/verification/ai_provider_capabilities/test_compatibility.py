"""Unit tests for verification.ai_provider_capabilities.compatibility."""

from __future__ import annotations

from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_capabilities.compatibility import run_compatibility_checks
from verification.ai_provider_capabilities.contract import (
    PRIOR_SLICE_IDS,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)


def test_baseline_defines_cr1_through_cr6_for_real() -> None:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    assert ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_run_compatibility_checks_all_pass() -> None:
    checks, matrix = run_compatibility_checks()
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]
    assert set(matrix["requirement_ids"]) == set(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)
    assert all(matrix["statement_holds_by_requirement_id"].values())
    assert set(matrix["prior_slice_notes_hold_by_slice_id"]) == set(PRIOR_SLICE_IDS)
    assert all(matrix["prior_slice_notes_hold_by_slice_id"].values())
