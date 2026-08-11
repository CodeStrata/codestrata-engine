"""SV.4 catalog loader tests (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from verification.repository_assessment.catalog import (
    load_catalog,
    select_smoke_repository,
)

REPO = Path(__file__).resolve().parents[4]


def test_loads_permanent_catalog() -> None:
    catalog = load_catalog(REPO)
    assert catalog.schema_name == "codestrata-repository-catalog"
    assert catalog.catalog_id == "codestrata-smoke-regression-catalog"
    assert catalog.path == "validation/repository-catalog/catalog.json"
    assert len(catalog.entries) > 0


def test_qualification_gap_when_all_null() -> None:
    catalog = load_catalog(REPO)
    data = json.loads(
        (REPO / "validation" / "repository-catalog" / "catalog.json").read_text(encoding="utf-8")
    )
    if all(item.get("qualified_revision") is None for item in data["repositories"]):
        assert catalog.qualification_gap is True
        entry, reason = select_smoke_repository(catalog)
        assert entry is None
        assert "qualified" in reason.lower()
    else:
        assert catalog.qualification_gap is False
        entry, reason = select_smoke_repository(catalog)
        assert entry is not None
        assert entry.qualified_revision is not None
        assert entry.qualified_revision.revision_type == "commit"
        assert len(entry.qualified_revision.value) == 40


def test_selection_prefers_smoke_small_qualified(tmp_path: Path) -> None:
    payload = {
        "schema_name": "codestrata-repository-catalog",
        "schema_version": "1.0.0",
        "catalog_id": "test-catalog",
        "repositories": [
            {
                "id": "zzz-large",
                "project_name": "Z",
                "github_repository": "org/z",
                "github_url": "https://github.com/org/z",
                "language_group": "JS/TS",
                "candidate_category": "Large",
                "license": "MIT",
                "qualified_revision": {"type": "commit", "value": "a" * 40},
                "enabled_for": {"smoke": True},
            },
            {
                "id": "aaa-small",
                "project_name": "A",
                "github_repository": "org/a",
                "github_url": "https://github.com/org/a",
                "language_group": "JS/TS",
                "candidate_category": "Small",
                "license": "MIT",
                "qualified_revision": {"type": "tag", "value": "v1.0.0"},
                "enabled_for": {"smoke": True},
            },
            {
                "id": "bbb-unqualified",
                "project_name": "B",
                "github_repository": "org/b",
                "github_url": "https://github.com/org/b",
                "language_group": "JS/TS",
                "candidate_category": "Small",
                "license": "MIT",
                "qualified_revision": None,
                "enabled_for": {"smoke": True},
            },
        ],
    }
    root = tmp_path / "validation" / "repository-catalog"
    root.mkdir(parents=True)
    (root / "catalog.json").write_text(json.dumps(payload), encoding="utf-8")
    catalog = load_catalog(tmp_path)
    entry, reason = select_smoke_repository(catalog)
    assert entry is not None
    assert entry.id == "aaa-small"
    assert "smoke-enabled" in reason
    assert entry.qualified_revision is not None
    assert entry.qualified_revision.revision_type == "tag"


def test_rejects_floating_branch_in_revision_object(tmp_path: Path) -> None:
    payload = {
        "schema_name": "codestrata-repository-catalog",
        "schema_version": "1.0.0",
        "catalog_id": "test-catalog",
        "repositories": [
            {
                "id": "floating",
                "project_name": "F",
                "github_repository": "org/f",
                "github_url": "https://github.com/org/f",
                "language_group": "Python",
                "candidate_category": "Small",
                "license": "MIT",
                "qualified_revision": {"type": "commit", "value": "main"},
                "enabled_for": {"smoke": True},
            }
        ],
    }
    root = tmp_path / "validation" / "repository-catalog"
    root.mkdir(parents=True)
    (root / "catalog.json").write_text(json.dumps(payload), encoding="utf-8")
    catalog = load_catalog(tmp_path)
    entry, _ = select_smoke_repository(catalog)
    assert entry is None
