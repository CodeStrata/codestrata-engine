"""Slice 17.15 report artifact lifecycle unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.artifacts.lifecycle import (
    LifecycleError,
    promote_assessment_run,
    promote_intelligence_run,
    staging_assessment_directory,
    staging_intelligence_directory,
)
from codestrata.artifacts.portfolio_identity import (
    RELEASE_VALIDATION_PORTFOLIO_ID,
    resolve_portfolio_artifact_id,
)
from codestrata.artifacts.repository_identity import (
    build_github_repository_artifact_id,
    resolve_repository_artifact_id,
)


def _stage_assessment(base: Path, run_id: str) -> Path:
    directory = staging_assessment_directory(run_id, base=base)
    (directory / "assessment.json").write_text(
        json.dumps({"assessment_id": run_id, "repository": "example"}),
        encoding="utf-8",
    )
    (directory / "assessment.html").write_text("<html></html>\n", encoding="utf-8")
    heads = directory / "heads"
    heads.mkdir(exist_ok=True)
    (heads / "architecture.json").write_text("{}", encoding="utf-8")
    return directory


def _stage_eir(base: Path, run_id: str, repos: list[str]) -> Path:
    directory = staging_intelligence_directory(run_id, base=base)
    (directory / "engineering-intelligence-report.json").write_text(
        json.dumps(
            {
                "portfolio_run_id": run_id,
                "repository_count": len(repos),
                "repository_artifact_ids": repos,
            }
        ),
        encoding="utf-8",
    )
    (directory / "engineering-intelligence-report.html").write_text(
        "<html></html>\n", encoding="utf-8"
    )
    return directory


def test_github_and_local_ids() -> None:
    assert build_github_repository_artifact_id("Org-A", "API") == "github-org-a-api"
    assert build_github_repository_artifact_id("Org-B", "API") == "github-org-b-api"
    assert resolve_repository_artifact_id(repository_name="My Repo") == "local-my-repo"
    assert (
        resolve_repository_artifact_id(
            repository_name="x",
            source_url="https://user:pass@github.com/o/r",
        )
        == "local-x"
    )


def test_portfolio_identity_stable() -> None:
    assert resolve_portfolio_artifact_id(suite_id="sv17-13") == RELEASE_VALIDATION_PORTFOLIO_ID
    assert (
        resolve_portfolio_artifact_id(portfolio_name="portfolio-sv17-13-20260809-194044")
        == RELEASE_VALIDATION_PORTFOLIO_ID
    )


def test_assessment_rotation_abc_fail_d(tmp_path: Path) -> None:
    rid = "github-codestrata-example"
    promote_assessment_run(
        repository_id=rid,
        staging_directory=_stage_assessment(tmp_path, "example-20260101-000001"),
        base=tmp_path,
    )
    assert (tmp_path / ".codestrata-artifacts/assessments" / rid / "current").is_dir()
    assert not (tmp_path / ".codestrata-artifacts/assessments" / rid / "previous").exists()

    promote_assessment_run(
        repository_id=rid,
        staging_directory=_stage_assessment(tmp_path, "example-20260101-000002"),
        base=tmp_path,
    )
    promote_assessment_run(
        repository_id=rid,
        staging_directory=_stage_assessment(tmp_path, "example-20260101-000003"),
        base=tmp_path,
    )
    current = json.loads(
        (
            tmp_path
            / ".codestrata-artifacts/assessments"
            / rid
            / "current"
            / "assessment.json"
        ).read_text(encoding="utf-8")
    )
    previous = json.loads(
        (
            tmp_path
            / ".codestrata-artifacts/assessments"
            / rid
            / "previous"
            / "assessment.json"
        ).read_text(encoding="utf-8")
    )
    assert current["assessment_run_id"] == "example-20260101-000003"
    assert previous["assessment_run_id"] == "example-20260101-000002"

    bad = _stage_assessment(tmp_path, "example-20260101-000004")
    (bad / "assessment.html").unlink()
    with pytest.raises(LifecycleError):
        promote_assessment_run(repository_id=rid, staging_directory=bad, base=tmp_path)
    current2 = json.loads(
        (
            tmp_path
            / ".codestrata-artifacts/assessments"
            / rid
            / "current"
            / "assessment.json"
        ).read_text(encoding="utf-8")
    )
    assert current2["assessment_run_id"] == "example-20260101-000003"


def test_portfolio_membership_change_preserves_identity(tmp_path: Path) -> None:
    pid = RELEASE_VALIDATION_PORTFOLIO_ID
    promote_intelligence_run(
        portfolio_id=pid,
        staging_directory=_stage_eir(tmp_path, "r1", ["a", "b", "c"]),
        base=tmp_path,
    )
    promote_intelligence_run(
        portfolio_id=pid,
        staging_directory=_stage_eir(tmp_path, "r2", ["a", "b", "c", "d"]),
        base=tmp_path,
    )
    promote_intelligence_run(
        portfolio_id=pid,
        staging_directory=_stage_eir(tmp_path, "r3", ["a", "b"]),
        base=tmp_path,
    )
    root = tmp_path / ".codestrata-artifacts/intelligence" / pid
    assert root.is_dir()
    current = json.loads(
        (root / "current" / "engineering-intelligence-report.json").read_text(encoding="utf-8")
    )
    previous = json.loads(
        (root / "previous" / "engineering-intelligence-report.json").read_text(encoding="utf-8")
    )
    assert current["portfolio_run_id"] == "r3"
    assert current["repository_artifact_ids"] == ["a", "b"]
    assert previous["portfolio_run_id"] == "r2"
    assert previous["repository_artifact_ids"] == ["a", "b", "c", "d"]
