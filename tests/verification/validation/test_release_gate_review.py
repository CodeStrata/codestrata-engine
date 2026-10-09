"""E15.3 release-gate review harness."""

from __future__ import annotations

from pathlib import Path

from verification.validation.release_gate.ledger import evaluate_story_prerequisites
from verification.validation.release_gate.models import ReviewDecision
from verification.validation.release_gate.policy import load_policy
from verification.validation.release_gate.runner import run_release_gate_review
from verification.validation.release_gate.tiers import (
    collect_repository_results,
    remote_tiers_enabled,
)

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"


def test_release_gate_decision_tracks_tier_records(monkeypatch) -> None:
    monkeypatch.delenv("CODESTRATA_RUN_REMOTE_VALIDATION", raising=False)
    report = run_release_gate_review(engine_root=ENGINE, repo_root=REPO)
    blocked_stories = [s for s in report.story_prerequisites if s.status is not ReviewDecision.PASS]
    assert not blocked_stories, blocked_stories
    assert report.corpus_manifest_ok is True
    assert report.regression_harness_ok is True
    assert report.external_pin_count >= 50
    assert report.remote_tiers_enabled is False
    assert len(report.source_tree_digest) == 64
    if not report.tiers_executed:
        # No fresh records for every pin: the env var alone never unblocks.
        assert report.decision in {ReviewDecision.BLOCKED, ReviewDecision.FAIL}
    elif not report.resource_envelope.budgets_published:
        assert report.decision is ReviewDecision.BLOCKED
    assert any("Failed or unrun required checks are never PASS." in note for note in report.notes)


def test_story_prerequisites_flag_missing_ledgers() -> None:
    policy = load_policy()
    stories = evaluate_story_prerequisites(ENGINE, policy)
    by_id = {item.story_id: item for item in stories}
    assert by_id["E12.3"].present is True
    assert by_id["E12.3"].status is ReviewDecision.PASS
    assert by_id["E15.2"].present is True


def test_repository_results_include_three_tiers() -> None:
    policy = load_policy()
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=policy,
        remote_enabled=remote_tiers_enabled(policy),
    )
    tiers = {item.tier.value for item in results}
    assert "dogfood" in tiers
    assert "external_large" in tiers
    assert "flagship_labeled" in tiers
