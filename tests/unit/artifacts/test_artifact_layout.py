"""Unit tests for Slice 17.12 artifact layout."""

from __future__ import annotations

from pathlib import Path

from codestrata.artifacts.heads import head_basename_for_legacy_filename, resolve_head_path
from codestrata.artifacts.layout import create_assessment_run_paths, ensure_artifact_tree
from codestrata.artifacts.manifest import build_assessment_manifest, write_assessment_manifest
from codestrata.reporters.report_paths import (
    DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    is_completed_report_run,
)


def test_default_assess_output_directory() -> None:
    assert DEFAULT_ASSESS_OUTPUT_DIRECTORY.as_posix() == ".codestrata-artifacts/assessments"


def test_create_assessment_run_paths(tmp_path: Path) -> None:
    ensure_artifact_tree(tmp_path)
    run = create_assessment_run_paths(
        repository_name="Demo Repo",
        base=tmp_path,
        timestamp="20260809-120000",
    )
    assert run.run_id == "demo-repo-20260809-120000"
    assert run.assessment_html.name == "assessment.html"
    assert run.assessment_json.name == "assessment.json"
    assert run.heads_directory.name == "heads"
    assert run.directory.is_dir()


def test_head_mapping_and_manifest(tmp_path: Path) -> None:
    assert head_basename_for_legacy_filename("architecture-assessment.json") == "architecture.json"
    run = create_assessment_run_paths(
        repository_name="app",
        base=tmp_path,
        timestamp="20260809-120001",
    )
    head = resolve_head_path(run.directory, legacy_filename="security-assessment.json")
    head.write_text("{}", encoding="utf-8")
    manifest = build_assessment_manifest(
        assessment_id=run.run_id,
        repository="app",
        run_directory=run.directory,
        overall_summary="ok",
    )
    assert manifest["schema"].startswith("codestrata-assessment-manifest")
    assert any(item["head_id"] == "security" for item in manifest["completed_heads"])
    write_assessment_manifest(run.assessment_json, manifest)
    run.assessment_html.write_text("<html></html>", encoding="utf-8")
    assert is_completed_report_run(run.directory)
