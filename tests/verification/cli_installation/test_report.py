"""SV.2 report model tests."""

from __future__ import annotations

import json
from pathlib import Path

from verification.cli_installation.models import (
    VerificationCheck,
    build_report,
)


def test_report_is_deterministic_and_sorted(tmp_path: Path) -> None:
    report = build_report(
        ok=True,
        checks=[
            VerificationCheck(name="b_check", ok=True, detail="ok"),
            VerificationCheck(name="a_check", ok=True, detail="ok"),
        ],
        environment={"z": "1", "a": "2"},
        commands=[{"name": "codestrata_version_flag", "ok": True}],
        codestrata_version="0.1.0",
        elapsed_ms=12.5,
        report_path=str(tmp_path / "cli-installation-verification.json"),
    )
    payload = report.to_dict()
    assert list(payload.keys()) == sorted(payload.keys())
    assert list(payload["environment"].keys()) == ["a", "z"]
    assert payload["schema_name"] == "cli-installation-verification"
    assert payload["schema_version"] == "1.0.0"
    assert payload["ok"] is True
    assert payload["failures"] == []

    path = report.write_json(tmp_path / "cli-installation-verification.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    # Rewrite is byte-stable for identical payload.
    again = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    assert path.read_text(encoding="utf-8") == again


def test_report_records_failures() -> None:
    report = build_report(
        ok=True,
        checks=[
            VerificationCheck(name="pip_install", ok=True),
            VerificationCheck(name="codestrata_init", ok=False, detail="boom"),
        ],
        environment={},
        commands=[],
        codestrata_version=None,
        elapsed_ms=1.0,
    )
    assert report.ok is False
    assert report.failures == ("codestrata_init",)
    assert "codestrata_init" in report.summary
