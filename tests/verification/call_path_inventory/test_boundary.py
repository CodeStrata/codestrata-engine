"""Call-path inventory stays Engine-local and does not instruct outside edits."""

from __future__ import annotations

from pathlib import Path

SCAN = Path(__file__).resolve().parents[3] / "verification" / "call_path_inventory"


def test_does_not_instruct_platform_or_workers_copies() -> None:
    for path in SCAN.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "copy into platform" not in lowered
        assert "edit platform/" not in lowered
        assert "edit workers/" not in lowered


def test_no_production_secrets_in_scanner() -> None:
    forbidden = ("AKIA", "pypi-AgE", "-----BEGIN", "CODESTRATA_PLATFORM_TOKEN=")
    for path in SCAN.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden:
            assert fragment not in text
