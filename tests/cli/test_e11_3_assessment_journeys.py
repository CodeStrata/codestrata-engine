"""P46 / E11.3: first assessment, partial signals, and compare journeys."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from tests.cli import e11_3_support as support
from tests.telemetry.privacy_canaries import ALL_CANARIES

ENGINE_ROOT = support.ENGINE_ROOT


@pytest.fixture(scope="module")
def candidate_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if os.environ.get("CODESTRATA_SKIP_E113_WHEEL") == "1":
        pytest.skip("CODESTRATA_SKIP_E113_WHEEL=1")
    dist = tmp_path_factory.mktemp("e113-dist")
    return support.build_wheel(ENGINE_ROOT, dist)


@pytest.fixture
def installed_engine(candidate_wheel: Path, tmp_path: Path) -> support.InstalledEngine:
    outside = tmp_path / "outside"
    outside.mkdir()
    return support.install_wheel_outside_checkout(candidate_wheel, outside_root=outside)


def test_pinned_fixture_expectations_match_source_assess(tmp_path: Path) -> None:
    """Guard expectations against drift before the slower wheel journey runs."""

    from typer.testing import CliRunner

    from codestrata.cli import app

    repo = support.copy_fixture_repo("java-minimal", tmp_path / "repo")
    env = support.assessment_environ(dict(os.environ))
    env["PYTHONPATH"] = str((ENGINE_ROOT / "src").resolve())
    runner = CliRunner()
    init = runner.invoke(app, ["init", "--config", str(repo / "codestrata.toml")], env=env)
    assert init.exit_code == 0, init.stdout + init.stderr
    assess = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repo),
            "--no-ai",
            "--output",
            str(repo / ".codestrata-artifacts" / "assessments"),
        ],
        env=env,
    )
    assert assess.exit_code == 0, assess.stderr
    current = support.find_current_assessment_dir(
        repo / ".codestrata-artifacts" / "assessments"
    )
    html = (current / "canonical-report.html").read_text(encoding="utf-8")
    support.assert_canonical_first_assessment(html, support.load_first_assessment_expectations())


def test_wheel_first_assessment_journey(installed_engine: support.InstalledEngine) -> None:
    repo = support.copy_fixture_repo(
        "java-minimal",
        installed_engine.workspace / "repo",
    )
    artifacts = support.run_first_assessment(installed_engine, repo)
    html = artifacts.canonical_html.read_text(encoding="utf-8")
    expectations = support.load_first_assessment_expectations()
    support.assert_canonical_first_assessment(html, expectations)
    support.verify_wheel_packaged_assets(installed_engine.wheel_path)
    version = support.run_codestrata(installed_engine, ["--version"], cwd=repo)
    assert version.returncode == 0
    support.assert_no_database_markers(version.stdout + version.stderr)
    # Second assess in the same venv (no-database restart behavior).
    second = support.run_codestrata(
        installed_engine,
        [
            "assess",
            "--repo",
            str(repo),
            "--no-ai",
            "--output",
            str(artifacts.artifacts_root),
        ],
        cwd=repo,
    )
    assert second.returncode == 0


def test_wheel_compare_compatible_and_incompatible(
    installed_engine: support.InstalledEngine,
) -> None:
    compare_dir = installed_engine.workspace / "compare"
    baseline, candidate = support.write_compare_reports(compare_dir, "compatible_resolved")
    compatible = support.run_compare(installed_engine, baseline, candidate, cwd=compare_dir)
    support.assert_compare_compatible_html(str(compatible["canonical_html"]))
    incompatible_dir = compare_dir / "incompatible"
    base2, cand2 = support.write_compare_reports(incompatible_dir, "incompatible_ruleset")
    incompatible = support.run_compare(installed_engine, base2, cand2, cwd=incompatible_dir)
    support.assert_compare_incompatible_html(str(incompatible["canonical_html"]))


def test_wheel_privacy_canary_redaction(installed_engine: support.InstalledEngine) -> None:
    if not support.PRIVACY_CANARY_ROOT.is_dir():
        pytest.skip("privacy canary fixture missing")
    repo = installed_engine.workspace / "privacy"
    shutil.copytree(support.PRIVACY_CANARY_ROOT, repo)
    artifacts = support.run_first_assessment(installed_engine, repo)
    texts = [
        artifacts.canonical_html.read_text(encoding="utf-8"),
        artifacts.assessment_html.read_text(encoding="utf-8"),
        artifacts.findings_json.read_text(encoding="utf-8"),
    ]
    support.assert_redacted(texts, ALL_CANARIES)


def test_wheel_lifecycle_after_controlled_fix(installed_engine: support.InstalledEngine) -> None:
    repo = support.copy_fixture_repo(
        "java-minimal",
        installed_engine.workspace / "lifecycle",
    )
    before = support.run_first_assessment(installed_engine, repo)
    before_html = before.canonical_html.read_text(encoding="utf-8")
    assert "technical_debt.deep-nesting" in before_html
    (repo / "src" / "App.java").write_text(
        "public class App { public int run() { return 0; } }\n",
        encoding="utf-8",
    )
    after = support.run_first_assessment(installed_engine, repo, initialize=False)
    after_html = after.canonical_html.read_text(encoding="utf-8")
    assert after.canonical_sha256 != before.canonical_sha256
    assert "technical_debt.deep-nesting" not in after_html
    assert "technical_debt.excessive-parameters" not in after_html
