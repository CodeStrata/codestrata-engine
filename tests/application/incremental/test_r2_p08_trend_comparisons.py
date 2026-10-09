"""R2-P08 adjacent and span comparison wiring."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata.application.incremental.trend_bundle import (
    COMPARISON_NAMES,
    COMPARISON_PAIRS,
    TREND_HTML_FILENAME,
    TREND_INDEX_FILENAME,
    create_trend_bundle,
    repository_trend_id,
)
from codestrata.application.incremental.trend_comparisons import (
    PUBLIC_OUTCOME_FAMILIES,
    STATUS_AVAILABLE,
    STATUS_INCOMPATIBLE,
    STATUS_NOT_COMPUTABLE,
    STATUS_UNAVAILABLE,
    TESTING_MAPS_UNDER,
    TREND_COMPARISON_SCHEMA,
    pair_gate,
    write_trend_comparisons,
)
from codestrata.application.incremental.trend_series import run_trend_series
from tests.application.incremental.test_r2_p06_trend_series import (
    LATER_AUTHOR,
    LATER_MARKER,
    LATER_PATH,
    _fake_assess_factory,
    _five_commit_adversarial,
    _settings,
)

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _load_comparison(series: Path, name: str) -> dict[str, Any]:
    path = series / "comparisons" / name / "comparison.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _m27_paths(payload: dict[str, Any]) -> set[str]:
    m27 = payload.get("m27") or {}
    return {str(item.get("path")) for item in m27.get("files") or () if item.get("path")}


def _snapshot_digests(series: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    snapshots = series / "snapshots"
    for path in sorted(snapshots.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(snapshots).as_posix()
        digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_adversarial_pairs_contain_only_their_range(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    result = run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
    )
    assert [slot.status for slot in result.slots] == ["available"] * 5
    assert [slot.sha for slot in result.slots] == shas
    snapshot_before = _snapshot_digests(series)
    bundle = create_trend_bundle(
        series,
        repository_id=repository_trend_id(repo),
        series_id=series.name,
    )
    write_trend_comparisons(bundle, result)
    assert _snapshot_digests(series) == snapshot_before

    payloads = {name: _load_comparison(series, name) for name in COMPARISON_NAMES}
    for _name, payload in payloads.items():
        assert payload["schema_name"] == TREND_COMPARISON_SCHEMA
        assert payload["status"] == STATUS_AVAILABLE
        assert payload["computed"] is True
        assert payload["comparison"] is not None
        assert payload["public_outcome_families"] == list(PUBLIC_OUTCOME_FAMILIES)
        assert payload["testing_maps_under"] == TESTING_MAPS_UNDER
        assert set(payload["public_outcome_verdicts"]).issubset(PUBLIC_OUTCOME_FAMILIES)
        assert "testing" not in payload["public_outcome_verdicts"]

    s12 = payloads["s1-s2"]
    s23 = payloads["s2-s3"]
    s45 = payloads["s4-s5"]
    s15 = payloads["s1-s5"]
    assert s12["base_sha"] == shas[0]
    assert s12["candidate_sha"] == shas[1]
    assert s45["base_sha"] == shas[3]
    assert s45["candidate_sha"] == shas[4]
    assert s15["base_sha"] == shas[0]
    assert s15["candidate_sha"] == shas[4]
    assert s12["m27"]["resolved_base"] == shas[0]
    assert s12["m27"]["resolved_head"] == shas[1]
    assert s45["m27"]["resolved_base"] == shas[3]
    assert s45["m27"]["resolved_head"] == shas[4]
    assert s15["m27"]["resolved_base"] == shas[0]
    assert s15["m27"]["resolved_head"] == shas[4]

    s12_files = _m27_paths(s12)
    s23_files = _m27_paths(s23)
    s45_files = _m27_paths(s45)
    s15_files = _m27_paths(s15)
    assert s12_files == {"src/app.js"}
    assert LATER_PATH not in s12_files
    assert "src/pair.js" not in s12_files
    assert "src/pair.js" in s23_files
    assert LATER_PATH not in s23_files
    assert LATER_PATH in s45_files
    assert "src/pair.js" not in s45_files
    assert LATER_PATH in s15_files
    assert "src/app.js" in s15_files
    assert "src/pair.js" in s15_files

    s12_text = json.dumps(s12)
    s45_text = json.dumps(s45)
    assert LATER_PATH not in s12_text
    assert LATER_MARKER not in s12_text
    assert LATER_AUTHOR not in s12_text
    assert shas[4] not in s12_text
    assert LATER_PATH in s45_text
    assert shas[4] in s45_text
    assert shas[4] in json.dumps(s15)

    s12_attr = (s12.get("comparison") or {}).get("cause_attribution") or {}
    s45_attr = (s45.get("comparison") or {}).get("cause_attribution") or {}
    assert s12_attr.get("base_digests", {}).get("source") == result.slots[0].source_digest
    assert s12_attr.get("candidate_digests", {}).get("source") == result.slots[1].source_digest
    assert s45_attr.get("base_digests", {}).get("source") == result.slots[3].source_digest
    assert s45_attr.get("candidate_digests", {}).get("source") == result.slots[4].source_digest
    assert (series / TREND_HTML_FILENAME).is_file()
    html = (series / TREND_HTML_FILENAME).read_text(encoding="utf-8")
    assert "Five-commit health trend" in html
    assert "s1-s2" in html
    assert "oldest to HEAD" in html


def test_failed_middle_slot_keeps_adjacent_pairs_explicit(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([], fail_slot_sha=shas[2]),
    )
    index = json.loads((series / TREND_INDEX_FILENAME).read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in index["comparisons"]}
    assert by_id["s2-s3"]["status"] == STATUS_UNAVAILABLE
    assert by_id["s3-s4"]["status"] == STATUS_UNAVAILABLE
    assert by_id["s1-s2"]["status"] == STATUS_NOT_COMPUTABLE
    assert by_id["s4-s5"]["status"] == STATUS_NOT_COMPUTABLE
    assert by_id["s1-s5"]["status"] == STATUS_NOT_COMPUTABLE

    s23 = _load_comparison(series, "s2-s3")
    s34 = _load_comparison(series, "s3-s4")
    s12 = _load_comparison(series, "s1-s2")
    s45 = _load_comparison(series, "s4-s5")
    s15 = _load_comparison(series, "s1-s5")
    assert s23["status"] == STATUS_UNAVAILABLE
    assert s34["status"] == STATUS_UNAVAILABLE
    assert s23["computed"] is False
    assert s34["computed"] is False
    assert s23["comparison"] is None
    assert s34["comparison"] is None
    assert s23["m27"] is None
    assert s34["m27"] is None
    assert s23["unavailable_reason"] == "slot_unavailable_or_failed"
    assert s12["status"] == STATUS_NOT_COMPUTABLE
    assert s45["status"] == STATUS_NOT_COMPUTABLE
    assert s15["status"] == STATUS_NOT_COMPUTABLE
    assert s12["m27"] is not None
    assert s45["m27"] is not None
    assert s15["m27"] is not None
    assert _m27_paths(s12) == {"src/app.js"}
    assert LATER_PATH in _m27_paths(s45)
    assert LATER_PATH in _m27_paths(s15)
    assert LATER_PATH not in _m27_paths(s12)
    assert {row["id"] for row in index["comparisons"]} == set(COMPARISON_NAMES)


def test_incompatible_and_missing_pairs_stay_explicit(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    result = run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    mutated = replace(result.slots[1], engine_version="9.9.9-incompatible")
    slots = tuple(
        mutated if slot.slot == 2 else slot
        for slot in result.slots
    )
    result = replace(result, slots=slots)
    bundle = create_trend_bundle(
        series,
        repository_id=repository_trend_id(repo),
        series_id=series.name,
    )
    write_trend_comparisons(bundle, result)
    s12 = _load_comparison(series, "s1-s2")
    s23 = _load_comparison(series, "s2-s3")
    s45 = _load_comparison(series, "s4-s5")
    assert s12["status"] == STATUS_INCOMPATIBLE
    assert s23["status"] == STATUS_INCOMPATIBLE
    assert s12["computed"] is False
    assert s12["comparison"] is None
    assert s12["m27"] is None
    assert s12["unavailable_reason"] == "incompatible_profile"
    assert s12["base_engine_version"] == result.slots[0].engine_version
    assert s12["candidate_engine_version"] == "9.9.9-incompatible"
    assert s45["status"] == STATUS_NOT_COMPUTABLE
    assert s45["m27"] is not None
    assert pair_gate(result.slots[0], mutated)[0] == STATUS_INCOMPATIBLE


def test_comparison_pairs_are_exactly_the_required_five() -> None:
    assert COMPARISON_PAIRS == (
        (1, 2, "s1-s2"),
        (2, 3, "s2-s3"),
        (3, 4, "s3-s4"),
        (4, 5, "s4-s5"),
        (1, 5, "s1-s5"),
    )
