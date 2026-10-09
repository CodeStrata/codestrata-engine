"""E16.3 published-artifact smoke planning and live PyPI guards."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from verification.live_release_baseline.models import InferenceError
from verification.published_smoke.install import install_published_semver
from verification.published_smoke.models import SmokeDecision
from verification.published_smoke.plan import build_five_repository_plan, load_targets
from verification.published_smoke.pypi_client import wheel_sha256_for_version
from verification.published_smoke.runner import evaluate_readiness, run_cli_smoke
from verification.validation.models import DepthRole


def test_targets_and_five_repository_plan_match_e15_1() -> None:
    targets = load_targets()
    assert targets.candidate_semver == "0.2.2"
    assert targets.rollback_semver == "0.2.1"
    assert targets.observation_business_days == 3
    plan = build_five_repository_plan()
    roles = {item.role: item.repository_id for item in plan}
    assert roles[DepthRole.SUPPORTED_JAVA.value] == "doris"
    assert roles[DepthRole.SUPPORTED_JS_TS.value] == "typescript"
    assert roles[DepthRole.MIXED_BUILD_MONOREPO.value] == "vscode"
    assert roles[DepthRole.RETAINED_LOWER_DEPTH.value] == "django"
    assert roles[DepthRole.PARTIAL_UNSUPPORTED.value] == "rust"
    for item in plan:
        assert len(item.pin_sha) == 40
        assert item.github_repository


def test_candidate_readiness_blocked_until_pypi_and_digest() -> None:
    readiness = evaluate_readiness()
    assert readiness.decision is SmokeDecision.BLOCKED
    assert readiness.candidate_on_pypi is False
    assert "0.2.2" in readiness.notes[0] or readiness.candidate_on_pypi is False


def test_live_rollback_wheel_digest_matches_targets() -> None:
    targets = load_targets()
    try:
        observed = wheel_sha256_for_version(targets.pypi_project, targets.rollback_semver)
    except InferenceError as exc:
        reason = str(exc)
        if "certificate verify failed" in reason or "CERTIFICATE_VERIFY_FAILED" in reason:
            pytest.skip(f"rollback wheel digest unverified: {reason}")
        raise
    assert observed == targets.rollback_wheel_sha256


def test_wheel_digest_missing_version_raises() -> None:
    targets = load_targets()
    with pytest.raises(InferenceError):
        wheel_sha256_for_version(targets.pypi_project, "0.0.0-not-published")


@pytest.mark.published_smoke
def test_published_rollback_install_fixture_journey(tmp_path: Path) -> None:
    if os.environ.get("CODESTRATA_RUN_PUBLISHED_SMOKE") != "1":
        pytest.skip("CODESTRATA_RUN_PUBLISHED_SMOKE=1 required for live PyPI install smoke")
    targets = load_targets()
    outside = tmp_path / "outside"
    outside.mkdir()
    installed = install_published_semver(
        project=targets.pypi_project,
        semver=targets.rollback_semver,
        expected_wheel_sha256=targets.rollback_wheel_sha256,
        outside_root=outside,
    )
    exits = run_cli_smoke(installed.codestrata, cwd=installed.workspace)
    assert exits["version"] == 0
    assert exits["telemetry_status"] == 0
    assert exits["mcp_help"] == 0

    from tests.cli import e11_3_support as support

    repo = support.copy_fixture_repo("java-minimal", Path(installed.workspace) / "repo")
    engine = support.InstalledEngine(
        wheel_path=Path(installed.wheel_path),
        wheel_sha256=installed.wheel_sha256,
        codestrata=Path(installed.codestrata),
        python=Path(installed.python),
        env=dict(installed.env),
        workspace=Path(installed.workspace),
    )
    artifacts = support.run_first_assessment(engine, repo)
    html = artifacts.canonical_html.read_text(encoding="utf-8")
    support.assert_canonical_first_assessment(html, support.load_first_assessment_expectations())
    compare_dir = Path(installed.workspace) / "compare"
    baseline, candidate = support.write_compare_reports(compare_dir, "compatible_resolved")
    compatible = support.run_compare(engine, baseline, candidate, cwd=compare_dir)
    support.assert_compare_compatible_html(str(compatible["canonical_html"]))
