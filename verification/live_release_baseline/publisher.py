"""Inventory whether any existing workflow can satisfy R01."""

from __future__ import annotations

from collections.abc import Sequence

from verification.live_release_baseline.models import (
    PublisherStatus,
    R01Inventory,
    WorkflowSurface,
)

REQUIRED_CHANGE = (
    "An authorized Engine-only GitHub Actions workflow that requests "
    "id-token: write for PyPI Trusted Publishing (or equivalent OIDC-constrained "
    "signer), publishes only the Engine package/image, and is not excluded by "
    "the Community export workflow denylist. Root CI and AWS infrastructure "
    "OIDC cannot be relabeled as that publisher. That change is outside this "
    "story and must not be made here."
)


def evaluate_r01(workflows: Sequence[WorkflowSurface]) -> R01Inventory:
    """R01 is PRESENT only for an Engine-only OIDC PyPI/container publisher."""

    engine_publishers = [
        item
        for item in workflows
        if item.engine_only_publish and item.pypi_oidc_publish and not item.aws_oidc
    ]
    if engine_publishers:
        first = engine_publishers[0]
        return R01Inventory(
            status=PublisherStatus.PRESENT,
            reason=(
                f"{first.path} obtains OIDC and publishes Engine alone "
                f"(triggers: {', '.join(first.triggers) or 'none'})"
            ),
            workflows=tuple(workflows),
            engine_only_oidc_publisher=first.path,
            required_outside_engine_change="",
        )

    aws_oidc = [item.path for item in workflows if item.id_token_write and item.aws_oidc]
    reasons = [
        "No root workflow obtains the required OIDC identity and publishes Engine alone.",
        "ci.yml is validation-only (contents: read; no id-token; no PyPI/container publish).",
    ]
    if aws_oidc:
        reasons.append(
            "OIDC present only for AWS infrastructure identity/plan/apply: "
            + ", ".join(aws_oidc)
            + " - not a PyPI or Engine package publisher."
        )
    reasons.append(
        "Community export excludes .github/workflows/** from codestrata-engine; "
        "adding engine/.github/workflows/ does not close R01."
    )
    return R01Inventory(
        status=PublisherStatus.BLOCKED,
        reason=" ".join(reasons),
        workflows=tuple(workflows),
        engine_only_oidc_publisher=None,
        required_outside_engine_change=REQUIRED_CHANGE,
    )
