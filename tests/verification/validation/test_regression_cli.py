"""CLI writes docs; default path does not fetch remotes."""

from __future__ import annotations

from pathlib import Path

from verification.validation.regression.__main__ import main

REPO = Path(__file__).resolve().parents[4]


def test_cli_json_and_docs(tmp_path: Path) -> None:
    docs = tmp_path / "regression.md"
    code = main(["--repo-root", str(REPO), "--json", "--write-docs", str(docs)])
    assert code == 0
    text = docs.read_text(encoding="utf-8")
    assert "E15.2" in text
    assert "M33" in text
    assert "50 remotes" in text
