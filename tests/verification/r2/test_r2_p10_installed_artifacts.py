"""R2-P10 isolated wheel/sdist journeys. No source-tree PYTHONPATH."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tests.application.incremental.git_repo_helpers import commit_dated, init_repo, write

ENGINE = Path(__file__).resolve().parents[3]
EXAMPLES = ENGINE / "examples" / "journeys"
PINNED = "2026-09-27T00:00:00Z"


def _python(venv: Path) -> Path:
    windows = venv / "Scripts" / "python.exe"
    return windows if windows.exists() else venv / "bin" / "python"


def _cli(python: Path) -> Path:
    windows = python.parent / "codestrata.exe"
    return windows if windows.exists() else python.parent / "codestrata"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["CODESTRATA_EVALUATION_TIME"] = PINNED
    return env


def _run(python: Path, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_cli(python)), *args],
        cwd=cwd,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture(scope="module")
def built_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    work = tmp_path_factory.mktemp("r2-p10-dist")
    built = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(work)],
        cwd=ENGINE,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    wheel = next(work.glob("codestrata-*.whl"))
    sdist = next(work.glob("codestrata-*.tar.gz"))
    return wheel, sdist


def _install(artifact: Path, tmp_path: Path) -> Path:
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = _python(venv)
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", str(artifact)],
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    locate = (
        "import codestrata, pathlib; "
        "print(pathlib.Path(codestrata.__file__).resolve())"
    )
    location = subprocess.run(
        [str(python), "-c", locate],
        env=_env(),
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "site-packages" in location
    assert str(ENGINE / "src") not in location
    return python


def _five_commit_complete(dest: Path) -> Path:
    shutil.copytree(EXAMPLES / "complete-js", dest)
    init_repo(dest)
    write(dest, "src/app.js", "function score(n) { return 1; }\n")
    commit_dated(dest, "s1", unix=1_700_000_000)
    for index in range(2, 6):
        write(dest, "src/app.js", f"function score(n) {{ return {index}; }}\n")
        commit_dated(dest, f"s{index}", unix=1_700_000_000 + index * 100)
    return dest


def _first(output: Path, *names: str) -> Path:
    for name in names:
        matches = list(output.rglob(name))
        if matches:
            return matches[0]
    raise AssertionError(f"missing {names} under {output}")


def _assert_baseline(python: Path, repo: Path, output: Path) -> None:
    result = _run(
        python,
        ["assess", "--repo", str(repo), "--output", str(output), "--no-ai"],
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    html = _first(output, "assessment.html", "canonical-report.html").read_text(
        encoding="utf-8"
    )
    canon_path = _first(output, "canonical-report.json", "assessment.json")
    canon = json.loads(canon_path.read_text(encoding="utf-8"))
    assert "Engineering Health" in html
    assert "Architecture" in html
    assert "Security" in html
    assert "Quality" in html
    assert "Maintainability" in html
    assert canon.get("health_score") is None
    assert "Five-commit health trend" not in html
    from tests.reporting.html_claims import assert_no_network_asset

    assert_no_network_asset(html)


def _assert_trend(python: Path, repo: Path, output: Path) -> None:
    result = _run(
        python,
        ["trend", "--repo", str(repo), "--output", str(output)],
        cwd=output.parent,
    )
    assert result.returncode == 0, result.stderr
    html_path = next(output.rglob("five-commit-trend.html"))
    html = html_path.read_text(encoding="utf-8")
    index = json.loads(html_path.with_name("trend-index.json").read_text(encoding="utf-8"))
    assert "What changed across the five commits" in html
    assert "Architecture" in html
    assert "health_score" not in html
    from tests.reporting.html_claims import assert_no_network_asset

    assert_no_network_asset(html)
    assert "<script src" not in html
    assert len(index["slots"]) == 5
    assert {row["id"] for row in index["comparisons"]} == {
        "s1-s2",
        "s2-s3",
        "s3-s4",
        "s4-s5",
        "s1-s5",
    }
    assert index["profile"]["engine_version"]
    assert index["profile"]["config_digest"]


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_isolated_artifact_assess_and_trend(
    built_artifacts: tuple[Path, Path], tmp_path: Path, kind: str
) -> None:
    wheel, sdist = built_artifacts
    artifact = wheel if kind == "wheel" else sdist
    python = _install(artifact, tmp_path / f"env-{kind}")
    help_text = _run(python, ["--help"], cwd=tmp_path).stdout
    assert "assess" in help_text
    assert "trend" in help_text
    assert "compare" in help_text
    repo = _five_commit_complete(tmp_path / f"repo-{kind}")
    initialized = _run(python, ["init"], cwd=repo)
    assert initialized.returncode == 0, initialized.stderr
    _assert_baseline(python, repo, tmp_path / f"assess-{kind}")
    _assert_trend(python, repo, tmp_path / f"trend-{kind}")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert len(digest) == 64
