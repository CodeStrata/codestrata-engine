"""Pinned corpus manifests meet E15.1 acceptance."""

from __future__ import annotations

from verification.validation.checks import evaluate, overall_status
from verification.validation.loader import load_bundle
from verification.validation.models import CheckStatus, DepthRole


def test_bundle_passes_manifest_checks() -> None:
    bundle = load_bundle()
    results = evaluate(bundle)
    failed = [item for item in results if item.status is not CheckStatus.PASS]
    assert overall_status(results) is CheckStatus.PASS, failed
    assert len(bundle.external_large) == 50


def test_five_representatives_cover_required_mix() -> None:
    bundle = load_bundle()
    mapping = {rep.role: rep.repository_id for rep in bundle.representatives}
    assert mapping[DepthRole.SUPPORTED_JAVA] == "doris"
    assert mapping[DepthRole.SUPPORTED_JS_TS] == "typescript"
    assert mapping[DepthRole.MIXED_BUILD_MONOREPO] == "vscode"
    assert mapping[DepthRole.RETAINED_LOWER_DEPTH] == "django"
    assert mapping[DepthRole.PARTIAL_UNSUPPORTED] == "rust"
    ids = {pin.id for pin in bundle.external_large}
    assert set(mapping.values()) <= ids


def test_window_inputs_and_budget_publication_state() -> None:
    bundle = load_bundle()
    assert bundle.window.history_days == 180
    assert bundle.window.history_commit_cap == 1000
    if bundle.window.budgets_published:
        # Publication is allowed only with measured values and an evidence file.
        assert bundle.window.measured_budget_le_10k
        assert bundle.window.measured_budget_le_100k
        assert bundle.window.budget_evidence
    else:
        assert bundle.window.measured_budget_le_10k == ""
    assert "detached HEAD" in bundle.inputs.git_state
    assert "OSV" in bundle.inputs.feed
    assert bundle.expectations.survival_is_not_analytical_correctness
    assert bundle.expectations.failed_or_unrun_never_pass
