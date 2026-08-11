"""SV.4 workspace / source-integrity tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification.repository_assessment.workspace import (
    assert_outside_codestrata_tree,
    capture_inventory,
    compare_source_integrity,
    create_minimal_python_repository,
)


def test_source_integrity_allows_codestrata_artifacts(tmp_path: Path) -> None:
    repo = create_minimal_python_repository(tmp_path / "repo")
    before = capture_inventory(repo)
    (repo / "codestrata.toml").write_text("[repository]\n", encoding="utf-8")
    out = repo / "reports" / "run1" / "report.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    after = capture_inventory(repo)
    ok, failures = compare_source_integrity(before, after)
    assert ok, failures


def test_source_integrity_flags_source_mutation(tmp_path: Path) -> None:
    repo = create_minimal_python_repository(tmp_path / "repo")
    before = capture_inventory(repo)
    (repo / "src" / "hello.py").write_text("changed\n", encoding="utf-8")
    after = capture_inventory(repo)
    ok, failures = compare_source_integrity(before, after)
    assert not ok
    assert any(f.startswith("modified:") for f in failures)


def test_source_integrity_allows_nested_codestrata_cache(tmp_path: Path) -> None:
    repo = create_minimal_python_repository(tmp_path / "repo")
    before = capture_inventory(repo)
    cache = repo / "pkg" / "deep" / ".codestrata" / "knowledge" / "x.json"
    cache.parent.mkdir(parents=True)
    cache.write_text("{}", encoding="utf-8")
    (repo / "pkg" / "deep" / "codestrata.toml").parent.mkdir(parents=True, exist_ok=True)
    (repo / "pkg" / "deep" / "codestrata.toml").write_text("[repository]\n", encoding="utf-8")
    after = capture_inventory(repo)
    ok, failures = compare_source_integrity(before, after)
    assert ok, failures


def test_clone_must_be_outside_tree(tmp_path: Path) -> None:
    root = tmp_path / "codestrata"
    root.mkdir()
    with pytest.raises(ValueError):
        assert_outside_codestrata_tree(root / "inside", root)
    assert_outside_codestrata_tree(tmp_path / "outside", root)
