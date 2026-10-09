"""E14.4 publication preflight rehearsal and R01 guardrails."""

from __future__ import annotations

import json
from pathlib import Path

from verification.live_release_baseline.models import PublisherStatus
from verification.live_release_baseline.publisher import evaluate_r01
from verification.live_release_baseline.workflows import parse_workflow_text

from codestrata.application.release.publication.r01_gate import (
    WorkflowPublisherView,
    build_r01_preflight_record,
    monorepo_ci_relabeled_as_publisher,
)
from codestrata.application.release.publication.rehearsal import build_rehearsal_verify_payload
from codestrata.application.release.publication.service import run_publication_preflight
from codestrata.application.release.verification import VerificationStatus, verify_payload

ENGINE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = ENGINE_ROOT.parent

CI = """
name: ci
on:
  push:
permissions:
  contents: read
jobs:
  test:
    steps:
      - run: pytest
"""

AWS_OIDC = """
name: aws-identity-check
on:
  workflow_dispatch:
permissions:
  id-token: write
jobs:
  check:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
"""

FAKE_CI_PUBLISHER = """
name: ci
on:
  push:
permissions:
  id-token: write
  contents: read
jobs:
  publish:
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
"""


def _blocked_r01_kwargs() -> dict[str, object]:
    inventory = evaluate_r01(
        (
            parse_workflow_text(".github/workflows/ci.yml", CI),
            parse_workflow_text(".github/workflows/aws-identity-check.yml", AWS_OIDC),
        )
    )
    assert inventory.status is PublisherStatus.BLOCKED
    views = tuple(
        WorkflowPublisherView(
            path=item.path,
            name=item.name,
            pypi_oidc_publish=item.pypi_oidc_publish,
            engine_only_publish=item.engine_only_publish,
            aws_oidc=item.aws_oidc,
            id_token_write=item.id_token_write,
        )
        for item in inventory.workflows
    )
    return {
        "r01_status": inventory.status.value,
        "r01_reason": inventory.reason,
        "engine_only_oidc_publisher": inventory.engine_only_oidc_publisher,
        "required_outside_engine_change": inventory.required_outside_engine_change,
        "workflows": views,
    }


def test_rehearsal_payload_verifies_against_packaged_oidc_policy() -> None:
    artifact = b"codestrata-e144-candidate-wheel-bytes\n"
    payload = build_rehearsal_verify_payload(artifact)
    result = verify_payload(payload)
    assert result.status is VerificationStatus.VERIFIED
    assert result.issuer == "https://token.actions.githubusercontent.com"
    assert result.identity is not None
    assert "release.yml@refs/tags/v" in result.identity


def test_publication_preflight_produces_catalog_and_rehearsal(tmp_path: Path) -> None:
    summary = run_publication_preflight(
        engine_root=ENGINE_ROOT,
        output_directory=tmp_path,
        **_blocked_r01_kwargs(),
    )
    assert summary.build_ok is True
    assert summary.public_rehearsal_ok is True
    assert summary.r01_ready is False
    assert summary.ok is True
    assert summary.r01 is not None
    assert summary.r01.status == "BLOCKED"
    assert summary.r01.publication_performed is False
    assert "outside" in summary.r01.required_outside_engine_change.lower()
    assert (tmp_path / "publication-catalog.json").is_file()
    assert (tmp_path / "publication-preflight-summary.json").is_file()
    assert (tmp_path / "publication-rehearsal" / "wheel.sigstore-bundle.json").is_file()
    catalog = json.loads((tmp_path / "publication-catalog.json").read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in catalog["entries"]}
    assert {"wheel", "sdist", "sbom", "provenance", "sigstore_bundle"}.issubset(kinds)


def test_ci_cannot_be_relabeled_as_publisher() -> None:
    surface = parse_workflow_text(".github/workflows/ci.yml", FAKE_CI_PUBLISHER)
    view = WorkflowPublisherView(
        path=surface.path,
        name=surface.name,
        pypi_oidc_publish=surface.pypi_oidc_publish,
        engine_only_publish=surface.engine_only_publish,
        aws_oidc=surface.aws_oidc,
        id_token_write=surface.id_token_write,
    )
    assert monorepo_ci_relabeled_as_publisher((view,)) is True
    record = build_r01_preflight_record(
        status="PRESENT",
        reason="fake",
        engine_only_oidc_publisher=".github/workflows/ci.yml",
        required_outside_engine_change="",
        workflows=(view,),
    )
    assert record.monorepo_ci_relabeled_as_publisher is True


def test_tampered_candidate_fails_rehearsal_verification() -> None:
    artifact = b"codestrata-e144-candidate-wheel-bytes\n"
    payload = build_rehearsal_verify_payload(artifact)
    bundle = payload["bundle"]
    assert isinstance(bundle, dict)
    message = bundle.get("messageSignature")
    assert isinstance(message, dict)
    message["signature"] = "AAAA"
    result = verify_payload(payload)
    assert result.status is not VerificationStatus.VERIFIED


def test_live_monorepo_r01_inventory_is_blocked_not_ci_publisher() -> None:
    inventory = evaluate_r01(())
    if (REPO_ROOT / ".github" / "workflows").is_dir():
        from verification.live_release_baseline.workflows import load_root_workflows

        inventory = evaluate_r01(load_root_workflows(REPO_ROOT))
    ci_paths = [item for item in inventory.workflows if item.path.endswith("ci.yml")]
    for ci in ci_paths:
        assert not ci.engine_only_publish, "ci.yml must not be the Engine OIDC publisher"
    if inventory.status is PublisherStatus.PRESENT:
        assert inventory.engine_only_oidc_publisher is not None
        assert "engine-pypi-release" in inventory.engine_only_oidc_publisher
        return
    assert inventory.status is PublisherStatus.BLOCKED
    assert inventory.engine_only_oidc_publisher is None
