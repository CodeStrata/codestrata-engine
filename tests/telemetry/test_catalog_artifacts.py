"""Catalog artifact reconciliation, privacy, determinism, side effects (Slice 9.8)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_formatting import (
    format_catalog_json,
    format_catalog_markdown,
)
from codestrata.telemetry.catalog_write import (
    JSON_ARTIFACT_NAME,
    MARKDOWN_ARTIFACT_NAME,
    catalog_artifact_paths,
)
from codestrata.telemetry.service import reset_telemetry_singletons


ENGINE_DOCS = Path(__file__).resolve().parents[2] / "docs"
TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_committed_artifacts_match_builder() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    expected_json = format_catalog_json(catalog)
    expected_md = format_catalog_markdown(catalog)
    json_path, md_path = catalog_artifact_paths(docs_dir=ENGINE_DOCS)
    assert json_path.name == JSON_ARTIFACT_NAME
    assert md_path.name == MARKDOWN_ARTIFACT_NAME
    actual_json = json_path.read_text(encoding="utf-8")
    actual_md = md_path.read_text(encoding="utf-8")
    if actual_json != expected_json or actual_md != expected_md:
        raise AssertionError(
            "Committed telemetry catalog artifacts drifted from builder output. "
            "Regenerate with: python -m codestrata.telemetry.catalog_write"
        )


def test_determinism() -> None:
    a = build_privacy_first_telemetry_catalog()
    b = build_privacy_first_telemetry_catalog()
    assert a.to_stable_json() == b.to_stable_json()
    assert format_catalog_markdown(a) == format_catalog_markdown(b)
    assert [e.name for e in a.events] == sorted(e.name for e in a.events)
    assert [f.name for f in a.shared_fields] == sorted(f.name for f in a.shared_fields)


def test_privacy_scan_artifacts() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    for text in (format_catalog_json(catalog), format_catalog_markdown(catalog)):
        lowered = text.lower()
        for needle in (
            "/users/",
            "codeSTRATA_HOME".lower(),
            "https://",
            "sk-",
            "password=",
            "55555555-5555",
            "amazonaws",
            "boto3",
        ):
            assert needle not in lowered
        # Structural: no installation_id collectable field.
        assert '"name": "installation_id"' not in text
        assert "`installation_id`" not in text or "never" in lowered


def test_side_effect_free_build(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text("{bad", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    with patch("codestrata.telemetry.service.get_legacy_telemetry_service") as legacy:
        with patch("codestrata.telemetry.transport.send_payload") as send:
            catalog = build_privacy_first_telemetry_catalog()
            assert catalog.transmission_status == "not_operational"
            legacy.assert_not_called()
            send.assert_not_called()
    assert {p.name: p.read_bytes() for p in home.iterdir()} == before
    home.chmod(0o000)
    try:
        build_privacy_first_telemetry_catalog()
    finally:
        home.chmod(0o700)


def test_status_reports_catalog_available(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Anonymous Community telemetry" in result.stdout
    assert "Preference: Not configured" in result.stdout
    assert "Default: Disabled" in result.stdout
    assert "no source code" in result.stdout.lower()


def test_no_catalog_or_send_cli_commands() -> None:
    result = CliRunner().invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    assert "preview" in result.stdout.lower()
    for forbidden in ("  catalog ", "│ catalog", "  events ", "  fields ", "  send "):
        assert forbidden not in result.stdout


def test_no_platform_imports_in_catalog_modules() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.glob("catalog*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in (name or ""), f"{path}: {name}"
