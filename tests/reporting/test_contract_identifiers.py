"""Report contract identifier remapping tests (Phase 5.15)."""

from __future__ import annotations

from codestrata.reporting.contract.identifiers import (
    align_related_finding_ids,
    remap_related_finding_ids,
)


def test_remap_related_finding_ids_keeps_known_and_drops_unknown() -> None:
    id_map = {
        "runtime-a": "stable-a",
        "runtime-b": "stable-b",
    }
    assert remap_related_finding_ids(
        ["runtime-b", "SEC001", "runtime-a", "runtime-b"],
        id_map,
    ) == ("stable-a", "stable-b")
    assert remap_related_finding_ids(["SEC001"], id_map) == ()
    assert remap_related_finding_ids([], id_map) == ()


def test_align_related_finding_ids_keeps_valid_drops_invalid_and_aliases() -> None:
    allowed = {"keep-a", "keep-b"}
    aliases = {"dropped-runtime": "keep-a", "orphan": "missing"}
    assert align_related_finding_ids(
        ["keep-b", "unknown", "dropped-runtime", "keep-a", "orphan"],
        allowed_finding_ids=allowed,
        alias_to_allowed=aliases,
    ) == ("keep-a", "keep-b")
    assert align_related_finding_ids(
        ["unknown-only"],
        allowed_finding_ids=allowed,
    ) == ()
    assert align_related_finding_ids(
        [],
        allowed_finding_ids=allowed,
    ) == ()
