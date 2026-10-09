"""Inspect the checkout against the E00.3 isolation policy."""

from __future__ import annotations

from pathlib import Path

from verification.live_release_baseline.workflows import load_root_workflows
from verification.release_isolation.models import CheckStatus, IsolationInspection
from verification.release_isolation.ordinary_merge import evaluate_ordinary_merge_side_effects
from verification.release_isolation.policy import load_policy
from verification.release_isolation.push_pattern import evaluate_checkout_ci


def inspect_checkout(repo_root: Path) -> IsolationInspection:
    policy = load_policy()
    push = evaluate_checkout_ci(repo_root, policy)
    workflows = load_root_workflows(repo_root)
    texts: dict[str, str] = {}
    workflow_dir = repo_root / ".github" / "workflows"
    if workflow_dir.is_dir():
        for path in (*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")):
            relative = path.relative_to(repo_root).as_posix()
            texts[relative] = path.read_text(encoding="utf-8")
    ordinary = evaluate_ordinary_merge_side_effects(workflows, texts)
    notes = (
        "This inspection does not publish, tag, deploy or notify.",
        "R01 publisher identity remains E00.1 BLOCKED; isolation does not close it.",
    )
    statuses = (push.status, ordinary.status)
    if CheckStatus.BLOCKED in statuses:
        status = CheckStatus.BLOCKED
    elif CheckStatus.FAIL in statuses:
        status = CheckStatus.FAIL
    elif CheckStatus.PARTIAL in statuses or CheckStatus.UNSUPPORTED in statuses:
        status = CheckStatus.PARTIAL
    else:
        status = CheckStatus.PASS
    return IsolationInspection(
        policy=policy,
        push=push,
        ordinary_merge=ordinary,
        status=status,
        notes=notes,
    )
