"""Ordinary merges must not publish or move stable tags."""

from __future__ import annotations

from verification.live_release_baseline.workflows import parse_workflow_text
from verification.release_isolation.models import CheckStatus
from verification.release_isolation.ordinary_merge import evaluate_ordinary_merge_side_effects

from tests.verification.live_release_baseline.test_workflows import AWS_OIDC, CI

TAG_ON_PUSH = """
name: tag
on:
  push:
    branches:
      - main
permissions:
  contents: write
jobs:
  release:
    steps:
      - run: git tag -f v0.2.1
      - run: git push --tags
"""

COMMENT_ONLY = """
name: ci
on:
  push:
    branches:
      - "release/**"
permissions:
  contents: read
jobs:
  x:
    steps:
      - run: echo ok
# git tag -f v0.2.1
# twine upload dist/*
"""

PUBLISH_ON_PUSH = """
name: publish
on:
  push:
permissions:
  contents: read
  id-token: write
jobs:
  publish:
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
"""


def test_validation_ci_has_no_tag_or_publish_side_effect() -> None:
    surface = parse_workflow_text(".github/workflows/ci.yml", CI)
    evidence = evaluate_ordinary_merge_side_effects((surface,), {surface.path: CI})
    assert evidence.status is CheckStatus.PASS


def test_workflow_dispatch_aws_is_not_an_ordinary_merge() -> None:
    surface = parse_workflow_text(".github/workflows/aws-identity-check.yml", AWS_OIDC)
    evidence = evaluate_ordinary_merge_side_effects((surface,), {surface.path: AWS_OIDC})
    assert evidence.status is CheckStatus.UNSUPPORTED


def test_force_tag_on_push_fails() -> None:
    surface = parse_workflow_text(".github/workflows/tag.yml", TAG_ON_PUSH)
    evidence = evaluate_ordinary_merge_side_effects((surface,), {surface.path: TAG_ON_PUSH})
    assert evidence.status is CheckStatus.FAIL
    assert any("tag" in reason.lower() or "contents" in reason for reason in evidence.reasons)


def test_comment_only_publish_is_ignored() -> None:
    surface = parse_workflow_text(".github/workflows/ci.yml", COMMENT_ONLY)
    evidence = evaluate_ordinary_merge_side_effects((surface,), {surface.path: COMMENT_ONLY})
    assert evidence.status is CheckStatus.PASS


def test_pypi_publish_on_push_fails() -> None:
    surface = parse_workflow_text(".github/workflows/publish.yml", PUBLISH_ON_PUSH)
    evidence = evaluate_ordinary_merge_side_effects((surface,), {surface.path: PUBLISH_ON_PUSH})
    assert evidence.status is CheckStatus.FAIL


def test_empty_inventory_is_blocked() -> None:
    evidence = evaluate_ordinary_merge_side_effects((), {})
    assert evidence.status is CheckStatus.BLOCKED
