"""Architecture boundaries for Engine ↔ Platform integration."""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE_INTEGRATION = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "codestrata"
    / "integration"
)


def test_engine_integration_does_not_import_platform_package() -> None:
    forbidden: list[str] = []
    for path in sorted(ENGINE_INTEGRATION.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("codestrata_platform") or alias.name.startswith(
                        "platform."
                    ):
                        forbidden.append(f"{path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("codestrata_platform") or node.module.startswith(
                    "platform."
                ):
                    forbidden.append(f"{path.name}:{node.module}")
    assert forbidden == []


def test_engine_depends_on_platform_client_abstraction() -> None:
    client_source = (ENGINE_INTEGRATION / "commercial" / "client.py").read_text(
        encoding="utf-8"
    )
    assert "class PlatformClient" in client_source
    assert "class RestPlatformClient" in client_source
    assert "class MockPlatformClient" in client_source
    assert "class OfflinePlatformClient" in client_source
