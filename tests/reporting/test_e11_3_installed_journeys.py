"""E11.3 journeys on a wheel installed outside the checkout."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# complete-js feed is published 2026-09-26; 7-day freshness is fresh at this pin.
_JOURNEY_EVALUATION_TIME = "2026-09-27T00:00:00Z"

_ENGINE = Path(__file__).resolve().parents[2]
_EXAMPLES = _ENGINE / "examples" / "journeys"
_VIEWS = (
    "engineering-hotspots",
    "ownership-concentration",
    "temporal-co-change",
    "change-summary",
    "capability-coverage",
    "before-after-delta",
)
_SECRET = "AKIA1234567890ABCDEF"


def _python(venv: Path) -> Path:
    windows = venv / "Scripts" / "python.exe"
    if windows.exists():
        return windows
    return venv / "bin" / "python"


def _env(*, evaluation_time: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if evaluation_time:
        env["CODESTRATA_EVALUATION_TIME"] = evaluation_time
    return env


def _cli(python: Path) -> Path:
    windows = python.parent / "codestrata.exe"
    if windows.exists():
        return windows
    return python.parent / "codestrata"


def _run(
    python: Path,
    args: list[str],
    *,
    cwd: Path,
    evaluation_time: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_cli(python)), *args],
        cwd=cwd,
        env=_env(evaluation_time=evaluation_time),
        text=True,
        capture_output=True,
        check=False,
    )


def _commit(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    env = _env()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Ada Lovelace",
            "GIT_AUTHOR_EMAIL": "ada@example.com",
            "GIT_COMMITTER_NAME": "Ada Lovelace",
            "GIT_COMMITTER_EMAIL": "ada@example.com",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Ada Lovelace",
            "-c",
            "user.email=ada@example.com",
            "commit",
            "-m",
            "pin fixture",
        ],
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.fixture(scope="module")
def installed_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("e11-3-wheel")
    built = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(work)],
        cwd=_ENGINE,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    wheel = next(work.glob("codestrata-*.whl"))
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (work / "wheel.sha256").write_text(digest + "\n", encoding="utf-8")
    venv = work / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = _python(venv)
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    pytest.wheel_sha256 = digest  # type: ignore[attr-defined]
    return python


def _canonical(repo: Path) -> Path:
    matches = list(repo.rglob("canonical-report.html"))
    assert matches, "assess did not write canonical-report.html"
    return matches[0]


def _links_resolve(html: str) -> None:
    ids = set(re.findall(r'id="([^"]+)"', html))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in ids, href


def test_installed_wheel_has_catalog_and_schema(installed_python: Path) -> None:
    code = (
        "import codestrata, pathlib; "
        "root = pathlib.Path(codestrata.__file__).resolve().parent; "
        "print(root); "
        "yaml = list(root.rglob('quality.complexity.yaml')); "
        "schemas = list(root.rglob('AssessmentReport.json')); "
        "assert yaml, 'rule catalog missing'; "
        "assert schemas, 'schema missing'; "
        "assert 'site-packages' in str(root)"
    )
    result = subprocess.run(
        [str(installed_python), "-c", code],
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_repository_is_actionable(installed_python: Path, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = _run(
        installed_python,
        ["assess", "--repo", str(missing), "--no-ai"],
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "Fix:" in result.stderr or "not found" in result.stderr.lower()


def test_first_assess_restart_and_views(installed_python: Path, tmp_path: Path) -> None:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    _commit(repo)
    init = _run(installed_python, ["init"], cwd=repo)
    assert init.returncode == 0, init.stderr
    first = _run(
        installed_python,
        ["assess", "--repo", ".", "--no-ai"],
        cwd=repo,
        evaluation_time=_JOURNEY_EVALUATION_TIME,
    )
    assert first.returncode == 0, first.stderr
    html_path = _canonical(repo)
    html = html_path.read_text(encoding="utf-8")
    for view in _VIEWS:
        assert f'id="{view}"' in html
    assert "no baseline" in html
    assert "trend" not in html.lower()
    assert "healthy" not in html.lower()
    assert "health_score: none" in html
    assert "<script" not in html.lower()
    assert "ranking_value: 12" in html
    assert "1.000000" in html
    assert "feed_fresh" in html
    _links_resolve(html)
    canonical_text = html_path.with_name("canonical-report.json").read_text(encoding="utf-8")
    canonical_json = json.loads(canonical_text)
    assert canonical_json["health_score"] is None
    assert canonical_json["hotspots"][0]["ranking_value"] == "12"
    assert "ranking_value: 12" in html
    sarif = html_path.with_name("canonical-report.sarif.json").read_text(encoding="utf-8")
    assert "health_score" in sarif
    assert _SECRET not in html
    assert _SECRET not in sarif
    second = _run(
        installed_python,
        ["assess", "--repo", ".", "--no-ai"],
        cwd=repo,
        evaluation_time=_JOURNEY_EVALUATION_TIME,
    )
    assert second.returncode == 0, second.stderr
    databases = list(repo.rglob("*.sqlite")) + list(repo.rglob("*.db"))
    assert databases == []
    evidence = _ENGINE / ".quality-runs" / "e11.3"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "canonical-report.html").write_text(html, encoding="utf-8")
    (evidence / "wheel.sha256").write_text(
        str(getattr(pytest, "wheel_sha256", "")) + "\n",
        encoding="utf-8",
    )


def test_controlled_fix_and_incompatible_compare(installed_python: Path, tmp_path: Path) -> None:
    def make(label: str, source: str) -> Path:
        repo = tmp_path / label
        repo.mkdir()
        shutil.copy(_EXAMPLES / "secret-finding" / source / "App.java", repo / "App.java")
        snapshot = _EXAMPLES / "secret-finding" / "codestrata" / "osv-snapshot.json"
        (repo / "codestrata").mkdir()
        shutil.copy(snapshot, repo / "codestrata" / "osv-snapshot.json")
        _commit(repo)
        init = _run(installed_python, ["init"], cwd=repo)
        assert init.returncode == 0, init.stderr
        assessed = _run(installed_python, ["assess", "--repo", ".", "--no-ai"], cwd=repo)
        assert assessed.returncode == 0, assessed.stderr
        return repo

    before = make("before", "before")
    after = make("after", "after")
    before_html = _canonical(before).read_text(encoding="utf-8")
    after_html = _canonical(after).read_text(encoding="utf-8")
    before_json = _canonical(before).with_name("analysis-result.json")
    after_json = _canonical(after).with_name("analysis-result.json")
    assert _SECRET not in before_html
    assert _SECRET not in after_html
    assert _SECRET not in before_json.read_text(encoding="utf-8")
    assert _SECRET not in after_json.read_text(encoding="utf-8")
    assert "src/App.java" in before_html or "App.java" in before_html
    compared = _run(
        installed_python,
        ["compare", "--baseline", str(before_json), "--candidate", str(after_json)],
        cwd=tmp_path,
    )
    assert compared.returncode == 0, compared.stderr
    summary = json.loads(compared.stdout[compared.stdout.find("{") :])
    assert summary["resolved_findings"] >= 1
    movement_html = Path(summary["canonical_html_path"]).read_text(encoding="utf-8")
    assert "no baseline" not in movement_html
    assert "Compatible baseline" not in movement_html
    baseline_payload = json.loads(before_json.read_text(encoding="utf-8"))
    candidate_payload = json.loads(after_json.read_text(encoding="utf-8"))
    baseline_payload["ruleset_version"] = "1.0.0"
    candidate_payload["ruleset_version"] = "2.0.0"
    baseline_copy = tmp_path / "baseline.json"
    candidate_copy = tmp_path / "candidate.json"
    baseline_copy.write_text(json.dumps(baseline_payload), encoding="utf-8")
    candidate_copy.write_text(json.dumps(candidate_payload), encoding="utf-8")
    incompatible = _run(
        installed_python,
        ["compare", "--baseline", str(baseline_copy), "--candidate", str(candidate_copy)],
        cwd=tmp_path,
    )
    assert incompatible.returncode == 0, incompatible.stderr
    incompatible_summary = json.loads(incompatible.stdout[incompatible.stdout.find("{") :])
    assert incompatible_summary["compatibility_status"] == "incompatible"
    report = Path(incompatible_summary["canonical_html_path"])
    incompatible_html = report.read_text(encoding="utf-8")
    assert "incompatible" in incompatible_html
    assert "Compatible baseline" not in incompatible_html
    assert "Stable" not in incompatible_html


def test_trend_html_stays_offline_like_installed_baseline() -> None:
    from codestrata.reporting.engineering_health.trend_report import _TREND_CSS

    assert "https://" not in _TREND_CSS
    assert "cdn." not in _TREND_CSS


def test_installed_wheel_registers_trend_and_runs_five_commits(
    installed_python: Path, tmp_path: Path
) -> None:
    help_result = _run(installed_python, ["trend", "--help"], cwd=tmp_path)
    assert help_result.returncode == 0, help_result.stderr
    help_text = help_result.stdout + help_result.stderr
    assert "--repo" in help_text
    assert "--max-count" not in help_text
    repo = tmp_path / "complete-js-five"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    _commit(repo)
    app = repo / "src" / "app.js"
    for index in range(2, 6):
        app.write_text(f"function score(n) {{ return {index}; }}\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/app.js"],
            check=True,
            capture_output=True,
        )
        env = _env()
        env.update(
            {
                "GIT_AUTHOR_NAME": "Ada Lovelace",
                "GIT_AUTHOR_EMAIL": "ada@example.com",
                "GIT_COMMITTER_NAME": "Ada Lovelace",
                "GIT_COMMITTER_EMAIL": "ada@example.com",
                "GIT_AUTHOR_DATE": f"2026-01-0{index}T00:00:00Z",
                "GIT_COMMITTER_DATE": f"2026-01-0{index}T00:00:00Z",
            }
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Ada Lovelace",
                "-c",
                "user.email=ada@example.com",
                "commit",
                "-m",
                f"state {index}",
            ],
            check=True,
            capture_output=True,
            env=env,
        )
    output = tmp_path / "trend-out"
    result = _run(
        installed_python,
        ["trend", "--repo", str(repo), "--output", str(output)],
        cwd=tmp_path,
        evaluation_time=_JOURNEY_EVALUATION_TIME,
    )
    assert result.returncode == 0, result.stderr
    htmls = list(output.rglob("five-commit-trend.html"))
    assert htmls, result.stdout
    html = htmls[0].read_text(encoding="utf-8")
    assert "Five-commit health trend" in html or "What changed across the five commits" in html
    assert "Architecture" in html
    assert "health_score" not in html
    from tests.reporting.html_claims import assert_no_network_asset

    assert_no_network_asset(html)
    assert "<script src" not in html
    index = json.loads(htmls[0].with_name("trend-index.json").read_text(encoding="utf-8"))
    assert len(index["slots"]) == 5
    assert all(slot["status"] in {"available", "UNKNOWN", "failed"} for slot in index["slots"])
    assert {row["id"] for row in index["comparisons"]} == {
        "s1-s2",
        "s2-s3",
        "s3-s4",
        "s4-s5",
        "s1-s5",
    }
    locate = (
        "import codestrata, pathlib; "
        "print(pathlib.Path(codestrata.__file__))"
    )
    assert "site-packages" in str(
        subprocess.run(
            [str(installed_python), "-c", locate],
            env=_env(),
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )
