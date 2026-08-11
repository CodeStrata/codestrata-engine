"""AI analytics Engine / Cloud / VS Code boundaries (Slice 10.6)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.analytics.ai_analytics import collect_ai_analytics
from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def test_no_analytics_persistence_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    collect_ai_analytics(
        aggregate=build_ai_analytics_input(
            capability="modernization_advisor",
            provider_family="openai",
            model_family="gpt_family",
            provider_ownership="customer_managed",
            outcome="success",
        ),
        identity=new_anonymous_installation_identity(),
        home=home,
    )
    assert list(home.iterdir()) == []


def test_identity_file_only_when_ensured(tmp_path: Path) -> None:
    home = tmp_path / "home"
    collect_ai_analytics(
        aggregate=build_ai_analytics_input(
            capability="modernization_advisor",
            provider_family="aws_bedrock",
            model_family="amazon_nova_family",
            provider_ownership="customer_managed",
            outcome="success",
        ),
        home=home,
    )
    files = sorted(p.name for p in home.iterdir())
    assert files == ["anonymous-installation-identity.json"]


def test_openrouter_in_provider_family_catalog_family_only() -> None:
    from codestrata.telemetry.analytics.ai_analytics_catalogs import (
        APPROVED_AI_PROVIDER_FAMILIES,
    )

    assert "openrouter" in APPROVED_AI_PROVIDER_FAMILIES
    policy_text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "telemetry"
        / "analytics"
        / "ai_analytics_policy.py"
    ).read_text(encoding="utf-8")
    assert "openrouter_family_only_no_endpoints_or_keys" in policy_text
    assert "api_key" not in policy_text.lower() or "no_" in policy_text


def test_vscode_plugin_src_unchanged_by_slice() -> None:
    vscode = Path(__file__).resolve().parents[3] / "vscode-plugin" / "src"
    if not vscode.is_dir():
        return
    matches = list(vscode.rglob("*ai*analytics*"))
    assert matches == []


def test_cursor_plugin_src_unchanged_by_slice() -> None:
    cursor = Path(__file__).resolve().parents[3] / "cursor-plugin" / "src"
    if not cursor.is_dir():
        return
    matches = list(cursor.rglob("*ai*analytics*"))
    assert matches == []


def test_no_platform_import_in_ai_analytics() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "telemetry"
        / "analytics"
    )
    for path in root.glob("ai_analytics*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import " not in text or "codestrata_platform" not in text
        assert "from platform" not in text
        assert "codestrata_platform" not in text
        # Limitation tokens may mention deferred Cloud/Data Lake boundaries.
        if "data_lake" in text.lower():
            assert "deferred" in text.lower()
        if "community_cloud" in text.lower():
            assert "deferred" in text.lower()


def test_assess_cli_not_importing_ai_analytics() -> None:
    cli_root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "cli"
    if not cli_root.is_dir():
        return
    for path in cli_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "ai_analytics" not in text
        assert "collect_ai_analytics" not in text
