"""Integration, hotfix and prerelease isolation (E00.3).

Maintainer-only: not part of the installed ``codestrata`` wheel.
"""

from __future__ import annotations

from verification.release_isolation.candidate import (
    classify_output,
    classify_venv,
    plan_candidate_install,
    preserve_rollback_artifact,
)
from verification.release_isolation.hotfix import evaluate_hotfix
from verification.release_isolation.inspect import inspect_checkout
from verification.release_isolation.models import CheckStatus, IsolationInspection
from verification.release_isolation.policy import load_policy
from verification.release_isolation.render import render_isolation

__all__ = [
    "CheckStatus",
    "IsolationInspection",
    "classify_output",
    "classify_venv",
    "evaluate_hotfix",
    "inspect_checkout",
    "load_policy",
    "plan_candidate_install",
    "preserve_rollback_artifact",
    "render_isolation",
]
