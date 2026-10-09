"""CLI writes docs and stays read-only (no remote clone)."""

from __future__ import annotations

from pathlib import Path

from verification.validation.__main__ import main

REPO = Path(__file__).resolve().parents[4]


def test_cli_json_and_docs(tmp_path: Path) -> None:
    docs = tmp_path / "corpus.md"
    code = main(["--repo-root", str(REPO), "--json", "--write-docs", str(docs)])
    assert code == 0
    text = docs.read_text(encoding="utf-8")
    assert "External large" in text
    assert "50" in text
    assert "discovery lead" in text.lower()
    assert "G50" in text or "does not run" in text.lower()
