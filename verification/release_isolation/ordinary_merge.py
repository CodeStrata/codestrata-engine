"""Ordinary push/PR merges must not publish or move stable tags."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from verification.live_release_baseline.models import WorkflowSurface
from verification.release_isolation.models import CheckStatus, OrdinaryMergeEvidence

_ORDINARY = frozenset({"push", "pull_request"})

_TAG_MUTATION = re.compile(
    r"\bgit\s+tag\b|\bgit\s+push\s+[^\n]*--tags\b|"
    r"softprops/action-gh-release|ncipollo/release-action|"
    r"\bgh\s+release\s+create\b|\bgh\s+release\s+edit\b",
    re.IGNORECASE,
)
_PUBLISH = re.compile(
    r"pypa/gh-action-pypi-publish|\btwine\s+upload\b|"
    r"\bdocker\s+push\b|docker/build-push-action|"
    r"\bvsce\s+publish\b|\bnpm\s+publish\b",
    re.IGNORECASE,
)


def _without_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def evaluate_ordinary_merge_side_effects(
    workflows: Sequence[WorkflowSurface],
    texts: Mapping[str, str],
) -> OrdinaryMergeEvidence:
    if not workflows:
        return OrdinaryMergeEvidence(
            status=CheckStatus.BLOCKED,
            workflows_considered=(),
            reasons=("no workflows to inspect; cannot claim merges are side-effect free",),
        )
    considered: list[str] = []
    failures: list[str] = []
    for surface in workflows:
        if not _ORDINARY.intersection(surface.triggers):
            continue
        considered.append(surface.path)
        executable = _without_comments(texts.get(surface.path, ""))
        if surface.contents_write:
            failures.append(f"{surface.path} grants contents: write on ordinary triggers")
        if surface.pypi_oidc_publish or surface.engine_only_publish:
            failures.append(f"{surface.path} publishes to PyPI on ordinary triggers")
        if surface.container_publish:
            failures.append(f"{surface.path} publishes a container on ordinary triggers")
        if surface.marketplace_publish:
            failures.append(f"{surface.path} publishes a marketplace artifact")
        if _TAG_MUTATION.search(executable):
            failures.append(f"{surface.path} mutates git tags or GitHub releases")
        if _PUBLISH.search(executable):
            failures.append(f"{surface.path} contains a publish command")
    if not considered:
        return OrdinaryMergeEvidence(
            status=CheckStatus.UNSUPPORTED,
            workflows_considered=(),
            reasons=("no push/pull_request workflows; ordinary-merge claim does not apply",),
        )
    if failures:
        return OrdinaryMergeEvidence(
            status=CheckStatus.FAIL,
            workflows_considered=tuple(considered),
            reasons=tuple(failures),
        )
    return OrdinaryMergeEvidence(
        status=CheckStatus.PASS,
        workflows_considered=tuple(considered),
        reasons=("ordinary push/PR workflows do not publish or move stable tags",),
    )
