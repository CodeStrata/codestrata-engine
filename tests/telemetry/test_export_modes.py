"""E13.3 export mode manifests: full, restricted, no-export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.export_modes import (
    ExportCategoryManifest,
    ExportModeError,
    parse_export_mode,
    resolve_export_manifest,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "export_projection"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_mode_fixtures_resolve_allowed_and_withheld() -> None:
    for name in ("full-export.json", "restricted-withheld-graph.json", "no-export.json"):
        payload = _load(name)
        manifest = resolve_export_manifest(
            str(payload["mode"]),
            withheld_categories=tuple(str(item) for item in payload["withheld_categories"]),  # type: ignore[arg-type]
        )
        assert list(manifest.allowed_categories) == payload["expected_allowed"]
        assert list(manifest.withheld_categories) == payload["expected_withheld"]
        if name == "no-export.json":
            assert manifest.transfers is False
            assert manifest.mode is ExportMode.NONE


def test_no_export_aliases() -> None:
    for alias in ("no-export", "no_export", "none", "NONE"):
        assert parse_export_mode(alias) is ExportMode.NONE


def test_negative_mode_fixtures() -> None:
    with pytest.raises(ExportModeError, match="unsupported export mode"):
        resolve_export_manifest(str(_load("unsupported-mode.json")["mode"]))
    with pytest.raises(ExportModeError, match="withheld-category manifest"):
        resolve_export_manifest(
            str(_load("partial-restricted-empty.json")["mode"]),
            withheld_categories=(),
        )
    with pytest.raises(ExportModeError, match="unsupported export category"):
        resolve_export_manifest(
            "restricted",
            withheld_categories=tuple(
                str(item) for item in _load("unsupported-category.json")["withheld_categories"]  # type: ignore[arg-type]
            ),
        )


def test_full_cannot_withhold_and_restricted_cannot_withhold_all() -> None:
    with pytest.raises(ExportModeError, match="full export cannot withhold"):
        resolve_export_manifest(ExportMode.FULL, withheld_categories=("graph",))
    with pytest.raises(ExportModeError, match="no-export mode"):
        resolve_export_manifest("restricted", withheld_categories=("evidence", "graph"))
    with pytest.raises(ExportModeError, match="no-export cannot allow"):
        resolve_export_manifest("none", allowed_categories=("evidence",))


def test_restricted_allowed_complement_and_overlap_rejected() -> None:
    allowed_only = resolve_export_manifest("restricted", allowed_categories=("evidence",))
    assert allowed_only.withheld_categories == ("graph",)
    assert allowed_only.to_stable_dict()["transfers"] is True
    with pytest.raises(ExportModeError, match="must complement withheld"):
        resolve_export_manifest(
            "restricted",
            withheld_categories=("graph",),
            allowed_categories=("graph",),
        )
    with pytest.raises(ExportModeError, match="full export must allow"):
        resolve_export_manifest(ExportMode.FULL, allowed_categories=("evidence",))
    manifest = resolve_export_manifest("restricted", withheld_categories=("graph",))
    assert manifest.allows("evidence") is True
    assert manifest.allows("lake") is False
    with pytest.raises(ExportModeError, match="overlap"):
        ExportCategoryManifest(
            mode=ExportMode.RESTRICTED,
            allowed_categories=("graph",),
            withheld_categories=("graph",),
        )
