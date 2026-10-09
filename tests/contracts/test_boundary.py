"""Scope and negative fixtures for the E01.1 contract package."""

from __future__ import annotations

from pathlib import Path

ALLOWED_PREFIXES = (
    "engine/schemas/",
    "engine/src/codestrata/domain/",
    "engine/src/codestrata/resources/contracts/",
    "engine/docs/contracts/",
    "engine/tests/contracts/",
    "engine/docs/implementation/",
)


def test_story_paths_stay_inside_allowed_prefixes() -> None:
    engine = Path(__file__).resolve().parents[2]
    repo = engine.parent
    tracked = [
        engine / "docs" / "contracts",
        engine / "schemas" / "contracts",
        engine / "src" / "codestrata" / "domain" / "contracts",
        engine / "src" / "codestrata" / "resources" / "contracts",
        engine / "tests" / "contracts",
    ]
    for root in tracked:
        assert root.exists()
        for path in root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(repo).as_posix()
                assert any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES)
