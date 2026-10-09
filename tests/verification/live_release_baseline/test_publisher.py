"""R01 is blocked unless an Engine-only OIDC publisher exists."""

from __future__ import annotations

from tests.verification.live_release_baseline.test_workflows import AWS_OIDC, CI, PYPI_ENGINE
from verification.live_release_baseline.models import PublisherStatus
from verification.live_release_baseline.publisher import evaluate_r01
from verification.live_release_baseline.workflows import parse_workflow_text


def test_empty_inventory_is_blocked_not_assumed_solved() -> None:
    inventory = evaluate_r01(())
    assert inventory.status is PublisherStatus.BLOCKED
    assert inventory.engine_only_oidc_publisher is None
    assert "outside" in inventory.required_outside_engine_change.lower()


def test_ci_plus_aws_oidc_does_not_close_r01() -> None:
    workflows = (
        parse_workflow_text(".github/workflows/ci.yml", CI),
        parse_workflow_text(".github/workflows/aws-identity-check.yml", AWS_OIDC),
    )
    inventory = evaluate_r01(workflows)
    assert inventory.status is PublisherStatus.BLOCKED
    assert inventory.engine_only_oidc_publisher is None
    assert "AWS" in inventory.reason


def test_engine_only_pypi_oidc_is_present() -> None:
    workflows = (parse_workflow_text(".github/workflows/publish-engine.yml", PYPI_ENGINE),)
    inventory = evaluate_r01(workflows)
    assert inventory.status is PublisherStatus.PRESENT
    assert inventory.engine_only_oidc_publisher == ".github/workflows/publish-engine.yml"


def test_pypi_publish_without_oidc_is_blocked() -> None:
    text = """
name: twine
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  publish:
    steps:
      - run: twine upload dist/*
"""
    inventory = evaluate_r01((parse_workflow_text(".github/workflows/twine.yml", text),))
    assert inventory.status is PublisherStatus.BLOCKED


def test_monorepo_pypi_plus_platform_is_not_engine_only() -> None:
    text = """
name: publish-all
on:
  workflow_dispatch:
permissions:
  id-token: write
  contents: read
jobs:
  publish:
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
      - run: echo platform/ also ships
"""
    surface = parse_workflow_text(".github/workflows/publish-all.yml", text)
    assert not surface.engine_only_publish
    inventory = evaluate_r01((surface,))
    assert inventory.status is PublisherStatus.BLOCKED
