"""Prove the existing CI push pattern covers ``release/**``."""

from __future__ import annotations

from pathlib import Path

from verification.release_isolation.globs import (
    any_glob_matches,
    extract_push_branch_patterns,
)
from verification.release_isolation.models import (
    CheckStatus,
    IsolationPolicy,
    PushPatternEvidence,
)


def evaluate_push_pattern(
    text: str,
    *,
    policy: IsolationPolicy,
    workflow_path: str,
) -> PushPatternEvidence:
    patterns = extract_push_branch_patterns(text)
    if patterns is None:
        return PushPatternEvidence(
            workflow_path=workflow_path,
            patterns=(),
            covers_required_glob=False,
            integration_ref_matches=False,
            story_ref_matches=False,
            status=CheckStatus.FAIL,
            reason="workflow has no push trigger; release/** is not covered",
        )
    covers = policy.required_push_glob in patterns
    integration_match = any_glob_matches(patterns, policy.lanes.integration)
    story_sample = f"{policy.lanes.story_prefix}E00.3-isolation"
    story_match = any_glob_matches(patterns, story_sample)
    if not patterns:
        return PushPatternEvidence(
            workflow_path=workflow_path,
            patterns=patterns,
            covers_required_glob=True,
            integration_ref_matches=True,
            story_ref_matches=True,
            status=CheckStatus.PARTIAL,
            reason="push has no branch filter; it covers release/** but also every branch",
        )
    if covers and integration_match:
        status = CheckStatus.PASS
        reason = f"push.branches includes {policy.required_push_glob}"
    elif integration_match and not covers:
        status = CheckStatus.PARTIAL
        reason = (
            f"integration ref matches {patterns!r} but required glob "
            f"{policy.required_push_glob!r} is absent"
        )
    else:
        status = CheckStatus.FAIL
        reason = f"push.branches {patterns!r} does not cover {policy.required_push_glob}"
    return PushPatternEvidence(
        workflow_path=workflow_path,
        patterns=patterns,
        covers_required_glob=covers,
        integration_ref_matches=integration_match,
        story_ref_matches=story_match,
        status=status,
        reason=reason,
    )


def evaluate_checkout_ci(repo_root: Path, policy: IsolationPolicy) -> PushPatternEvidence:
    path = repo_root / policy.ordinary_ci_workflow
    if not path.is_file():
        return PushPatternEvidence(
            workflow_path=policy.ordinary_ci_workflow,
            patterns=(),
            covers_required_glob=False,
            integration_ref_matches=False,
            story_ref_matches=False,
            status=CheckStatus.BLOCKED,
            reason="ordinary CI workflow is missing; coverage cannot be claimed",
        )
    return evaluate_push_pattern(
        path.read_text(encoding="utf-8"),
        policy=policy,
        workflow_path=policy.ordinary_ci_workflow,
    )
