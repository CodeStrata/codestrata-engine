"""Orchestrate E15.3 release-gate review on a candidate checkout."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from verification.validation.checks import evaluate, overall_status
from verification.validation.loader import default_corpus_dir, load_bundle
from verification.validation.regression.runner import run_harness
from verification.validation.release_gate.flagship import confusion_rows_from_report
from verification.validation.release_gate.ledger import (
    evaluate_checkpoint_gates,
    evaluate_story_prerequisites,
)
from verification.validation.release_gate.models import (
    ReleaseGateReport,
    ResourceEnvelope,
    ReviewDecision,
)
from verification.validation.release_gate.policy import load_policy, load_reviewed_exceptions
from verification.validation.release_gate.tier_records import (
    default_results_dir,
    source_tree_digest,
)
from verification.validation.release_gate.tiers import (
    collect_repository_results,
    corpus_yaml_digest,
    remote_tiers_enabled,
    tier_blocked,
    tier_failures,
    tiers_fully_executed,
)


def _git_sha(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip()


def _git_porcelain(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "git unavailable"
    if completed.returncode != 0:
        return "git status failed"
    text = completed.stdout.strip()
    return text or "clean"


def _resource_envelope(
    engine_root: Path,
    policy_budgets: dict[str, str | bool],
) -> ResourceEnvelope:
    bundle = load_bundle()
    return ResourceEnvelope(
        host_cpu_count=os.cpu_count() or 0,
        proposed_le_10k=str(policy_budgets["le_10k_files"]),
        proposed_le_100k=str(policy_budgets["le_100k_files"]),
        host_note=str(policy_budgets["host"]),
        budgets_published=bool(policy_budgets["published"]) or bundle.window.budgets_published,
        corpus_pin_digest=corpus_yaml_digest(default_corpus_dir()),
    )


def _decision_from_report(
    *,
    corpus_ok: bool,
    regression_ok: bool,
    gates: tuple,
    stories: tuple,
    m15_blocked: bool,
    tiers_executed: bool,
    remote_enabled: bool,
    exceptions: tuple,
    repository_results: tuple = (),
    budgets_published: bool = True,
) -> ReviewDecision:
    """BLOCKED: cannot conclude. FAIL: a check ran and was violated."""

    del remote_enabled  # records are the evidence; the env var only enables new runs
    if any(item.decision not in {ReviewDecision.PASS} for item in gates):
        return ReviewDecision.BLOCKED
    if any(item.status is not ReviewDecision.PASS for item in stories):
        return ReviewDecision.BLOCKED
    unreviewed = [
        item
        for item in exceptions
        if not item.reviewed and item.scope != "out_of_engine_release_gate"
    ]
    if unreviewed:
        return ReviewDecision.BLOCKED
    failed_reasons: list[str] = []
    # A repository that ran and failed is a FAIL even while other pins are missing.
    if any(item.status.value != "BLOCKED" for item in tier_failures(repository_results)):
        failed_reasons.append("corpus tier repository failed")
    # No records, stale records, or a clone that could not run: cannot conclude.
    if not tiers_executed or tier_blocked(repository_results):
        return ReviewDecision.FAIL if failed_reasons else ReviewDecision.BLOCKED
    if not budgets_published:
        return ReviewDecision.BLOCKED
    if not corpus_ok:
        failed_reasons.append("E15.1 corpus manifest")
    if not regression_ok:
        failed_reasons.append("E15.2 regression harness")
    if m15_blocked:
        failed_reasons.append("M15 promotion")
    if failed_reasons:
        return ReviewDecision.FAIL
    return ReviewDecision.PASS


def run_release_gate_review(
    *,
    engine_root: Path,
    repo_root: Path | None = None,
    policy=None,
) -> ReleaseGateReport:
    loaded = policy or load_policy()
    root = repo_root or engine_root.parent
    corpus_results = evaluate(load_bundle(), engine_root=engine_root)
    corpus_ok = overall_status(corpus_results).value == "PASS"
    regression = run_harness(engine_root=engine_root, platform=sys.platform)
    regression_ok = regression.ok
    gates = evaluate_checkpoint_gates(engine_root, loaded)
    stories = evaluate_story_prerequisites(engine_root, loaded)
    remote = remote_tiers_enabled(loaded)
    digest = source_tree_digest(engine_root)
    repo_results = collect_repository_results(
        engine_root=engine_root,
        policy=loaded,
        remote_enabled=remote,
        results_dir=default_results_dir(engine_root),
        current_digest=digest,
    )
    m15_report = publish_classification_safe()
    confusion = confusion_rows_from_report(m15_report) if m15_report else ()
    exceptions = load_reviewed_exceptions()
    envelope = _resource_envelope(engine_root, loaded.m33_proposed_budgets)
    executed = tiers_fully_executed(repo_results, remote)
    decision = _decision_from_report(
        corpus_ok=corpus_ok,
        regression_ok=regression_ok,
        gates=gates,
        stories=stories,
        m15_blocked=m15_report.promotion_blocked if m15_report else True,
        tiers_executed=executed,
        remote_enabled=remote,
        exceptions=exceptions,
        repository_results=repo_results,
        budgets_published=envelope.budgets_published,
    )
    external_count = len(load_bundle().external_large)
    failures = tier_failures(repo_results)
    notes = (
        "Pin identity is not execution; each dogfood/external pin needs a fresh "
        "assessment record under verification/validation/corpus/results/.",
        f"Records are bound to Engine source digest {digest[:16]}; a source or pin "
        "change makes them stale.",
        (
            "M33 budgets are published measured limits."
            if envelope.budgets_published
            else "Proposed M33 budgets are not published operational limits."
        ),
        "Five smoke repositories do not replace the 50-large tier.",
        "Platform/R05 remains out of scope; see reviewed-exception-list.yaml.",
        "Failed or unrun required checks are never PASS.",
        *(
            (
                f"{len(failures)} executed pin(s) are not PASS/UNSUPPORTED: "
                + ", ".join(item.repository_id for item in failures[:10]),
            )
            if failures
            else ()
        ),
    )
    ok = decision is ReviewDecision.PASS
    return ReleaseGateReport(
        ok=ok,
        decision=decision,
        candidate_sha=_git_sha(root),
        dirty_inventory=_git_porcelain(root),
        corpus_manifest_ok=corpus_ok,
        regression_harness_ok=regression_ok,
        checkpoint_gates=gates,
        story_prerequisites=stories,
        repository_results=repo_results,
        confusion_matrices=confusion,
        m15_promotion_blocked=m15_report.promotion_blocked if m15_report else True,
        m15_block_reasons=m15_report.block_reasons if m15_report else ("m15_unavailable",),
        resource_envelope=envelope,
        reviewed_exceptions=exceptions,
        remote_tiers_enabled=remote,
        tiers_executed=executed,
        external_pin_count=external_count,
        notes=notes,
        source_tree_digest=digest,
    )


def publish_classification_safe():
    try:
        from codestrata.application.evidence.security.classification import publish_classification

        return publish_classification()
    except Exception:
        return None
