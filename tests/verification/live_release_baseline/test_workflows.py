"""Workflow inventory: OIDC AWS vs Engine PyPI publisher."""

from __future__ import annotations

from pathlib import Path

from verification.live_release_baseline.workflows import load_root_workflows, parse_workflow_text

CI = """
name: ci
on:
  pull_request:
  push:
    branches:
      - main
      - "release/**"
permissions:
  contents: read
jobs:
  engine-tests:
    steps:
      - run: python -m pytest tests
      # Marketplace publish is intentionally NOT invoked here.
"""

AWS_OIDC = """
name: aws-identity-check
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  oidc-identity:
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123:role/example
"""

PYPI_ENGINE = """
name: publish-engine
on:
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
jobs:
  publish:
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: engine/dist
"""

COMMENT_ONLY_WRITE = """
name: ci
on:
  push:
permissions:
  contents: read
jobs:
  x:
    steps:
      - run: echo ok
# configure-aws-credentials, contents:write, artifact upload
"""


def test_ci_is_not_a_publisher() -> None:
    surface = parse_workflow_text(".github/workflows/ci.yml", CI)
    assert surface.triggers == ("pull_request", "push")
    assert not surface.id_token_write
    assert not surface.contents_write
    assert not surface.pypi_oidc_publish
    assert not surface.engine_only_publish


def test_aws_oidc_is_not_pypi_publish() -> None:
    surface = parse_workflow_text(".github/workflows/aws-identity-check.yml", AWS_OIDC)
    assert surface.id_token_write
    assert surface.aws_oidc
    assert not surface.pypi_oidc_publish
    assert not surface.engine_only_publish


def test_engine_pypi_oidc_is_detected() -> None:
    surface = parse_workflow_text(".github/workflows/publish-engine.yml", PYPI_ENGINE)
    assert surface.pypi_oidc_publish
    assert surface.engine_only_publish
    assert not surface.aws_oidc


def test_comment_contents_write_is_ignored() -> None:
    surface = parse_workflow_text(".github/workflows/ci.yml", COMMENT_ONLY_WRITE)
    assert not surface.contents_write


def test_root_workflows_exist_on_this_checkout(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(CI, encoding="utf-8")
    (root / "engine" / ".github" / "workflows").mkdir(parents=True)
    (root / "engine" / ".github" / "workflows" / "hidden.yml").write_text(
        PYPI_ENGINE, encoding="utf-8"
    )
    surfaces = load_root_workflows(root)
    assert len(surfaces) == 1
    assert surfaces[0].path == ".github/workflows/ci.yml"
    assert not surfaces[0].engine_only_publish
