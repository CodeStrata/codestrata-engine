"""SV.4A catalog selection / qualification integration with SV.4 loader."""

from __future__ import annotations

from pathlib import Path

from verification.repository_assessment.catalog import load_catalog, select_smoke_repository

REPO = Path(__file__).resolve().parents[4]


def test_selection_uses_catalog_not_hardcoded_repo() -> None:
    catalog = load_catalog(REPO)
    entry, reason = select_smoke_repository(catalog)
    assert entry is not None
    assert entry.qualified_revision is not None
    assert entry.qualified_revision.revision_type == "commit"
    assert len(entry.qualified_revision.value) == 40
    assert entry.enabled_for_smoke is True
    assert "smoke-enabled" in reason
    # Among Small+qualified+smoke, lexicographically smallest id wins.
    small = [
        e
        for e in catalog.entries
        if e.enabled_for_smoke
        and e.qualified_revision is not None
        and e.candidate_category == "Small"
    ]
    assert small
    expected = sorted(small, key=lambda e: e.id)[0]
    assert entry.id == expected.id
    assert entry.id == "cleanarchitecture"


def test_qualification_gap_closed() -> None:
    catalog = load_catalog(REPO)
    assert catalog.qualification_gap is False
