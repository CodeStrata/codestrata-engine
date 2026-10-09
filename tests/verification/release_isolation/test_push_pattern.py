"""Push-pattern coverage of release/**."""

from __future__ import annotations

from pathlib import Path

from verification.release_isolation.models import CheckStatus
from verification.release_isolation.policy import load_policy
from verification.release_isolation.push_pattern import (
    evaluate_checkout_ci,
    evaluate_push_pattern,
)

from tests.verification.release_isolation.test_globs import CI, MAIN_ONLY, STAR, UNFILTERED


def test_ci_pattern_covers_release_glob() -> None:
    evidence = evaluate_push_pattern(
        CI, policy=load_policy(), workflow_path=".github/workflows/ci.yml"
    )
    assert evidence.status is CheckStatus.PASS
    assert evidence.covers_required_glob
    assert evidence.integration_ref_matches
    assert not evidence.story_ref_matches


def test_main_only_fails_coverage() -> None:
    evidence = evaluate_push_pattern(
        MAIN_ONLY, policy=load_policy(), workflow_path=".github/workflows/ci.yml"
    )
    assert evidence.status is CheckStatus.FAIL
    assert not evidence.covers_required_glob


def test_single_star_is_partial() -> None:
    evidence = evaluate_push_pattern(
        STAR, policy=load_policy(), workflow_path=".github/workflows/ci.yml"
    )
    assert evidence.status is CheckStatus.PARTIAL
    assert evidence.integration_ref_matches
    assert not evidence.covers_required_glob


def test_unfiltered_push_is_partial() -> None:
    evidence = evaluate_push_pattern(
        UNFILTERED, policy=load_policy(), workflow_path=".github/workflows/ci.yml"
    )
    assert evidence.status is CheckStatus.PARTIAL
    assert evidence.story_ref_matches


def test_missing_workflow_is_blocked(tmp_path: Path) -> None:
    evidence = evaluate_checkout_ci(tmp_path, load_policy())
    assert evidence.status is CheckStatus.BLOCKED
