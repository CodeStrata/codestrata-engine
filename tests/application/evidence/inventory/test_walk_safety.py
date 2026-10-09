"""Symlink-escape and no-execution guarantees for inventory walk."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from codestrata.application.evidence.inventory.service import ExtractorInventoryService
from codestrata.application.evidence.inventory.walk import _is_escape, walk_repository
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass

FIXTURES = Path(__file__).parent / "fixtures"


def test_escape_helper_rejects_paths_outside_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    assert _is_escape(repo.resolve(), outside) is True
    inside = repo / "src.py"
    inside.write_text("x = 1\n", encoding="utf-8")
    assert _is_escape(repo.resolve(), inside) is False


def test_symlink_escape_is_recorded_and_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("x = 1\n", encoding="utf-8")
    link = repo / "escaped.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this host")
    walked = walk_repository(repo)
    assert "escaped.txt" in walked.symlink_escapes
    escaped = next(item for item in walked.files if item.relative_path == "escaped.txt")
    assert escaped.primary_class is InventoryPrimaryClass.UNKNOWN
    assert escaped.ignore_reason == "symlink-escape"
    assert escaped.content_digest == ""
    assert all(item.relative_path != "../outside.txt" for item in walked.files)


def test_walk_does_not_hash_node_modules(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.ts").write_text("export const n = 1;\n", encoding="utf-8")
    modules = repo / "node_modules" / "leftpad"
    modules.mkdir(parents=True)
    (modules / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    (repo / ".angular" / "cache").mkdir(parents=True)
    (repo / ".angular" / "cache" / "built.js").write_text("x\n", encoding="utf-8")

    (repo / "dist").mkdir(parents=True)
    (repo / "dist" / "bundle.js").write_text("bundle\n", encoding="utf-8")
    (repo / "build").mkdir(parents=True)
    (repo / "build" / "output.js").write_text("build\n", encoding="utf-8")
    (repo / "out").mkdir(parents=True)
    (repo / "out" / "main.js").write_text("out\n", encoding="utf-8")
    (repo / "coverage").mkdir(parents=True)
    (repo / "coverage" / "lcov.info").write_text("cov\n", encoding="utf-8")
    (repo / "target").mkdir(parents=True)
    (repo / "target" / "app.jar").write_text("jar\n", encoding="utf-8")

    read: list[str] = []

    def reader(path: Path) -> bytes:
        read.append(path.name)
        return path.read_bytes()

    walked = walk_repository(repo, read_bytes=reader)
    paths = {item.relative_path.replace("\\", "/") for item in walked.files}
    assert "src/app.ts" in paths
    assert "index.js" not in read
    assert "built.js" not in read
    assert "bundle.js" not in read
    assert "output.js" not in read
    assert "main.js" not in read
    assert "lcov.info" not in read
    assert "app.jar" not in read
    assert "node_modules/leftpad/index.js" not in paths
    excluded = [
        item for item in walked.files if item.ignore_reason == "default-exclude:node_modules"
    ]
    assert excluded
    for name in ("dist", "build", "out", "coverage", "target"):
        assert any(item.ignore_reason == f"default-exclude:{name}" for item in walked.files)


def test_inventory_does_not_run_package_scripts() -> None:
    root = FIXTURES / "npm_missing_lock"
    marker = root / "EXECUTED"
    if marker.exists():
        marker.unlink()
    snapshot = ExtractorInventoryService().inspect_tree(root)
    assert snapshot.executed_repository_code is False
    assert not marker.exists()
    npm = next(item for item in snapshot.manifests if item.relative_path.endswith("package.json"))
    assert npm.support.value == "structural"
    assert npm.declared_count >= 1
