"""Live-release inventory lives beside src/, not in the wheel; no publish secrets."""

from __future__ import annotations

from pathlib import Path

from verification.live_release_baseline.models import PublisherStatus
from verification.live_release_baseline.publisher import evaluate_r01
from verification.live_release_baseline.record import load_recorded, render_baseline
from verification.live_release_baseline.workflows import load_root_workflows

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
PKG = ENGINE / "src" / "codestrata"
LIVE = ENGINE / "verification" / "live_release_baseline"


def test_package_is_not_in_wheel_payload() -> None:
    pyproject = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["codestrata*"]' in pyproject
    assert (LIVE / "recorded.yaml").is_file()
    assert not (PKG / "verification" / "live_release_baseline").exists()


def test_no_production_publish_credentials_in_sources() -> None:
    forbidden_fragments = (
        "AKIA",
        "pypi-AgE",
        "-----BEGIN",
        "aws_secret_access_key",
        "TWINE_PASSWORD=",
    )
    for path in (*LIVE.glob("*.py"), *LIVE.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for fragment in forbidden_fragments:
            assert fragment.lower() not in lowered, f"{path} contains {fragment}"


def test_does_not_instruct_workflow_or_manifest_edits() -> None:
    for path in LIVE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "edit .github/workflows" not in text.lower()
        assert "edit public-export-manifest" not in text.lower()
    publisher = (LIVE / "publisher.py").read_text(encoding="utf-8")
    assert "must not be made here" in publisher


def test_recorded_yaml_agrees_with_root_workflow_scan() -> None:
    record = load_recorded()
    live = evaluate_r01(load_root_workflows(REPO))
    assert record.r01.status is live.status
    if live.status is PublisherStatus.PRESENT:
        assert record.r01.engine_only_oidc_publisher == live.engine_only_oidc_publisher
    else:
        assert record.r01.engine_only_oidc_publisher is None
    assert record.pypi.live_version != ""
    assert record.pyproject_version_ignored is not None
    # Even if they happen to match numerically, the source of truth is PyPI files.
    assert record.pypi.files
    rendered = render_baseline(record)
    assert "was" in rendered and "**not** used as the live version" in rendered
    assert "pyproject" in rendered.lower()
    assert record.pypi.live_version in rendered
