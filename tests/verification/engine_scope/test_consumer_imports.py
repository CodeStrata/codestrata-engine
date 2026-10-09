"""Consumer import scan is read-only and does not rewrite Platform trees."""

from __future__ import annotations

from pathlib import Path

from verification.engine_scope.consumer_imports import (
    collect_consumer_imports,
    summarize_imports,
)


def test_consumer_scan_is_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    consumer = repo / "platform" / "pkg"
    consumer.mkdir(parents=True)
    target = consumer / "uses_engine.py"
    original = "from codestrata.reporting.contract.constants import X\n"
    target.write_text(original, encoding="utf-8")
    marker = repo / "platform" / "do-not-touch.txt"
    marker.write_text("keep\n", encoding="utf-8")
    records = collect_consumer_imports(repo, consumer_roots=("platform",))
    assert records
    assert records[0].module.startswith("codestrata")
    assert target.read_text(encoding="utf-8") == original
    assert marker.read_text(encoding="utf-8") == "keep\n"
    summary = summarize_imports(records)
    assert summary["read_only"] is True
    assert summary["import_count"] == 1


def test_missing_consumer_root_is_empty_not_failure(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    repo.mkdir()
    records = collect_consumer_imports(repo, consumer_roots=("vscode-plugin",))
    assert records == ()


def test_syntax_error_and_non_engine_imports_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    root = repo / "verification"
    root.mkdir(parents=True)
    (root / "broken.py").write_text("def (\n", encoding="utf-8")
    (root / "other.py").write_text(
        "import os\nfrom codestrata_platform.x import y\n",
        encoding="utf-8",
    )
    (root / "ok.py").write_text("import codestrata.cli\n", encoding="utf-8")
    records = collect_consumer_imports(repo, consumer_roots=("verification",))
    assert [item.module for item in records] == ["codestrata.cli"]


def test_recorded_inventory_document_exists() -> None:
    inventory = (
        Path(__file__).resolve().parents[3] / "docs" / "release" / "consumer-import-inventory.md"
    )
    text = inventory.read_text(encoding="utf-8")
    assert "read-only" in text.lower()
    assert "platform:" in text
    assert "vscode-plugin:" in text


def test_live_platform_consumer_imports_are_readable() -> None:
    repo = Path(__file__).resolve().parents[4]
    platform = repo / "platform"
    if not platform.is_dir():
        return
    records = collect_consumer_imports(repo, consumer_roots=("platform",))
    modules = {item.module for item in records}
    assert any(name.startswith("codestrata.") or name == "codestrata" for name in modules)
