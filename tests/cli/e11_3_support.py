"""Shared helpers for P46 / E11.3 installed-wheel assessment journeys."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.application.release.standalone.install_verify import scrubbed_environ
from codestrata.application.release.standalone.packaging import verify_wheel_inventory
from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    Severity,
)
from codestrata.reporters.json_file_reporter import JsonFileReporter

ENGINE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "e11_3"
PRIVACY_CANARY_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "privacy_canary_repo"

VIEW_IDS = (
    "engineering-hotspots",
    "ownership-concentration",
    "temporal-co-change",
    "change-summary",
    "capability-coverage",
    "before-after-delta",
    "inventory-git",
    "findings",
)

_COMPARE_JSON_MARKER = '{\n  "baseline"'


def assessment_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    """Non-interactive assess env (mirrors SV.4 offline defaults without importing verification)."""
    env = scrubbed_environ(base)
    env["CI"] = "1"
    env["TERM"] = "dumb"
    env.pop("CODESTRATA_TELEMETRY", None)
    env.pop("CODESTRATA_BEDROCK_MODEL_ID", None)
    env.pop("CODESTRATA_OPENAI_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("AWS_ACCESS_KEY_ID", None)
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    env.pop("AWS_SESSION_TOKEN", None)
    env.setdefault("PIP_NO_INDEX", "1")
    return env


@dataclass(frozen=True, slots=True)
class InstalledEngine:
    wheel_path: Path
    wheel_sha256: str
    codestrata: Path
    python: Path
    env: dict[str, str]
    workspace: Path


@dataclass(frozen=True, slots=True)
class AssessmentArtifacts:
    artifacts_root: Path
    current_dir: Path
    canonical_html: Path
    assessment_html: Path
    findings_json: Path
    canonical_sha256: str
    findings_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_first_assessment_expectations() -> dict[str, Any]:
    payload = json.loads(
        (FIXTURE_ROOT / "expected" / "first_assessment_expectations.json").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(payload, dict)
    return payload


def build_wheel(engine_root: Path, dist_dir: Path) -> Path:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=str(engine_root),
        capture_output=True,
        text=True,
        check=False,
        env=scrubbed_environ(),
    )
    if completed.returncode != 0:
        raise RuntimeError(f"wheel build failed: {completed.stderr[-800:]}")
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("wheel build produced no artifact")
    return wheels[-1]


def install_wheel_outside_checkout(
    wheel: Path,
    *,
    outside_root: Path,
) -> InstalledEngine:
    workspace = Path(tempfile.mkdtemp(prefix="codestrata-e113-", dir=str(outside_root)))
    venv_dir = workspace / "venv"
    venv.create(venv_dir, with_pip=True, clear=True)
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    env = scrubbed_environ()
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)
    install = subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if install.returncode != 0:
        raise RuntimeError(f"pip install failed: {install.stderr[-800:]}")
    codestrata = python.parent / ("codestrata.exe" if sys.platform == "win32" else "codestrata")
    if not codestrata.is_file():
        raise RuntimeError(f"missing console script: {codestrata}")
    return InstalledEngine(
        wheel_path=wheel,
        wheel_sha256=sha256_file(wheel),
        codestrata=codestrata,
        python=python,
        env=env,
        workspace=workspace,
    )


def copy_fixture_repo(name: str, destination: Path) -> Path:
    source = FIXTURE_ROOT / name
    if not source.is_dir():
        raise FileNotFoundError(source)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def run_codestrata(
    installed: InstalledEngine,
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    env = assessment_environ(installed.env)
    return subprocess.run(
        [str(installed.codestrata), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=600,
    )


def find_current_assessment_dir(artifacts_root: Path) -> Path:
    candidates = [
        path.parent
        for path in artifacts_root.rglob("canonical-report.html")
        if path.parent.name == "current"
    ]
    if not candidates:
        raise FileNotFoundError(f"no canonical-report.html under {artifacts_root}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def run_first_assessment(
    installed: InstalledEngine,
    repo: Path,
    *,
    artifacts_root: Path | None = None,
    initialize: bool = True,
) -> AssessmentArtifacts:
    config = repo / "codestrata.toml"
    out = artifacts_root or (repo / ".codestrata-artifacts" / "assessments")
    if initialize or not config.is_file():
        init = run_codestrata(
            installed,
            ["init", "--config", str(config)],
            cwd=repo,
        )
        if init.returncode != 0:
            raise RuntimeError(f"init failed: {init.stderr[-500:]}")
    assess = run_codestrata(
        installed,
        ["assess", "--repo", str(repo), "--no-ai", "--output", str(out)],
        cwd=repo,
    )
    if assess.returncode != 0:
        raise RuntimeError(f"assess failed: {assess.stderr[-800:]}")
    current = find_current_assessment_dir(out)
    canonical = current / "canonical-report.html"
    assessment_html = current / "assessment.html"
    findings = current / "findings.json"
    for path in (canonical, assessment_html, findings):
        if not path.is_file():
            raise FileNotFoundError(path)
    return AssessmentArtifacts(
        artifacts_root=out,
        current_dir=current,
        canonical_html=canonical,
        assessment_html=assessment_html,
        findings_json=findings,
        canonical_sha256=sha256_file(canonical),
        findings_sha256=sha256_file(findings),
    )


def assert_canonical_first_assessment(html: str, expectations: dict[str, Any]) -> None:
    from tests.reporting.html_claims import claim_text

    lowered = html.lower()
    claims = claim_text(html)
    claims_lower = claims.lower()
    for view_id in expectations.get("required_view_ids", ()):
        assert f'id="{view_id}"' in html, view_id
    for fragment in expectations.get("required_substrings", ()):
        assert fragment.lower() in lowered, fragment
    for fragment in expectations.get("forbidden_substrings", ()):
        # "Improved" in the OFL notice is license text, not an outcome claim.
        surface = claims if fragment.lower() == "improved" else html
        surface_lower = claims_lower if fragment.lower() == "improved" else lowered
        assert fragment not in surface, fragment
        assert fragment.lower() not in surface_lower, fragment
    for rule_id in expectations.get("required_finding_rule_ids", ()):
        assert rule_id in html, rule_id
    minimum = int(expectations.get("minimum_finding_rows") or 0)
    if minimum:
        rows = html.count("<tr><td id=\"finding-")
        assert rows >= minimum, f"expected >= {minimum} finding rows, got {rows}"
    trace = str(expectations.get("traceable_evidence_file") or "")
    if trace:
        assert trace in html
        assert 'id="evidence-' in html
    assert "health_score: none" in html
    assert ">0<" not in html.split("capability-coverage")[0]


def parse_compare_cli_output(text: str) -> dict[str, Any]:
    if _COMPARE_JSON_MARKER not in text:
        raise ValueError("compare output missing JSON payload")
    payload = json.loads(text[text.index(_COMPARE_JSON_MARKER) :])
    assert isinstance(payload, dict)
    return payload


def write_compare_reports(directory: Path, kind: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    finding = Finding(
        rule_id="technical_debt.deep-nesting",
        title="Deep nesting",
        description="Pinned E11.3 fixture finding",
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.MEDIUM,
        source=FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path="src/App.java", line_number=4)],
    )
    baseline = AnalysisResult(
        repository=Repository(name="baseline", path=Path("/data/baseline"), files=["src/App.java"]),
        findings=[finding],
        analyzer_version="0.2.1",
        ruleset_version="1.0.0",
    )
    if kind == "compatible_resolved":
        candidate = baseline.model_copy(update={"findings": []})
    elif kind == "incompatible_ruleset":
        candidate = baseline.model_copy(update={"ruleset_version": "2.0.0"})
    else:
        raise ValueError(kind)
    baseline_path = JsonFileReporter().write(baseline, directory / "baseline.json")
    candidate_path = JsonFileReporter().write(candidate, directory / "candidate.json")
    return baseline_path, candidate_path


def run_compare(
    installed: InstalledEngine,
    baseline: Path,
    candidate: Path,
    *,
    cwd: Path,
) -> dict[str, Any]:
    completed = run_codestrata(
        installed,
        [
            "compare",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ],
        cwd=cwd,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"compare failed: {completed.stderr[-500:]}")
    return parse_compare_cli_output(completed.stdout + completed.stderr)


def assert_compare_compatible_html(html: str) -> None:
    from tests.reporting.html_claims import claim_text

    lowered = claim_text(html).lower()
    assert "no baseline" not in lowered
    assert "delta unavailable" not in lowered
    assert "movement:" in lowered
    assert "class=\"healthy\"" not in html
    # A real movement label may say improved. An unavailable movement may not.
    if "outcome movement unavailable" in lowered:
        assert "improved" not in lowered.replace("outcome movement unavailable", "")


def assert_compare_incompatible_html(html: str) -> None:
    from tests.reporting.html_claims import claim_text

    lowered = claim_text(html).lower()
    assert "incompatible" in lowered or "insufficient" in lowered
    assert "compatible baseline" not in lowered
    assert "stable" not in lowered
    assert "improved" not in lowered


def assert_redacted(outputs: Iterable[str], canaries: Iterable[str]) -> None:
    for text in outputs:
        for canary in canaries:
            assert canary not in text, canary


def verify_wheel_packaged_assets(wheel: Path) -> None:
    result = verify_wheel_inventory(wheel)
    assert result.ok, result.detail


def assert_no_database_markers(version_output: str) -> None:
    assert "sqlalchemy" not in version_output.lower()
    assert "sqlite3" not in version_output.lower()
