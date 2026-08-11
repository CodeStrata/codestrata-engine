"""Assessment analytics filesystem and Cloud/VS Code boundary (Slice 10.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.analytics.assessment_analytics import collect_assessment_analytics
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def test_no_analytics_queue_or_event_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    collect_assessment_analytics(
        home=home,
        identity=new_anonymous_installation_identity(),
        outcome="success",
        duration_ms=100,
    )
    # Provided identity → no identity file either.
    assert list(home.iterdir()) == []


def test_identity_file_only_when_ensured(tmp_path: Path) -> None:
    home = tmp_path / "home"
    collect_assessment_analytics(
        home=home,
        outcome="success",
        duration_bucket="lt_1s",
    )
    files = sorted(p.name for p in home.iterdir())
    assert files == ["anonymous-installation-identity.json"]


def test_vscode_plugin_src_unchanged_by_slice() -> None:
    # Boundary check: this slice must not add assessment analytics under vscode-plugin.
    vscode = Path(__file__).resolve().parents[3] / "vscode-plugin" / "src"
    if not vscode.is_dir():
        return
    matches = list(vscode.rglob("*assessment*analytics*"))
    assert matches == []
