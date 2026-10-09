"""R2-P07 durable five-slot trend artifact bundle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from codestrata.application.incremental.trend_bundle import (
    COMPARISON_NAMES,
    RETENTION_POLICY,
    SLOT_NAMES,
    TREND_HTML_FILENAME,
    TREND_INDEX_FILENAME,
    TrendBundleError,
    hash_feed_bytes,
    resolve_series_directory,
    validate_bundle_segment,
)
from codestrata.application.incremental.trend_series import run_trend_series
from codestrata.artifacts.layout import ARTIFACT_ROOT_NAME, ASSESSMENTS_DIRNAME, TRENDS_DIRNAME
from codestrata.reporting.journey_observations import FEED_RELATIVE
from tests.application.incremental.git_repo_helpers import commit_dated, init_repo, write
from tests.application.incremental.test_r2_p06_trend_series import (
    _fake_assess_factory,
    _five_commit_adversarial,
    _settings,
)

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _index(root: Path) -> dict[str, Any]:
    return json.loads((root / TREND_INDEX_FILENAME).read_text(encoding="utf-8"))


def test_five_available_slots_are_addressable_after_the_run(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    result = run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    assert result.bundle_directory == series
    assert (series / TREND_INDEX_FILENAME).is_file()
    assert (series / TREND_HTML_FILENAME).is_file()
    index = _index(series)
    assert index["retention"]["policy"] == RETENTION_POLICY
    assert index["retention"]["rotates_current_previous"] is False
    assert [row["slot"] for row in index["slots"]] == [1, 2, 3, 4, 5]
    assert [row["status"] for row in index["slots"]] == ["available"] * 5
    for slot, sha in enumerate(shas, start=1):
        slot_dir = series / "snapshots" / f"s{slot}"
        payload = json.loads((slot_dir / "slot.json").read_text(encoding="utf-8"))
        assert slot_dir.is_dir()
        assert payload["source_revision"] == sha
        assert payload["engine_version"] == result.profile.engine_version
        assert payload["config_digest"] == result.profile.config_digest
        assert payload["feed_bytes_digest"] == result.profile.feed_digest
        assert payload["addressable"] is True
    assert {row["id"] for row in index["comparisons"]} == set(COMPARISON_NAMES)
    for name in COMPARISON_NAMES:
        comparison = json.loads(
            (series / "comparisons" / name / "comparison.json").read_text(encoding="utf-8")
        )
        assert comparison["id"] == name
        assert comparison["status"] == "not_computable"
        assert comparison["unavailable_reason"] == "missing_assessment_artifact"
        assert comparison["computed"] is False
        assert comparison["m27"] is not None
        assert comparison["m27"]["resolved_base"]
        assert comparison["m27"]["resolved_head"]
    assert not (series / ".staging").exists()
    assert not (series / "current").exists()
    assert not (series / "previous").exists()


def test_insufficient_history_slots_remain_explicit(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "short")
    write(repo, "src/app.js", "function app() { return 1; }\n")
    commit_dated(repo, "one", unix=1_700_000_000)
    write(repo, "src/app.js", "function app() { return 2; }\n")
    commit_dated(repo, "two", unix=1_700_000_100)
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    index = _index(series)
    assert [row["status"] for row in index["slots"]] == [
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "available",
        "available",
    ]
    for name in SLOT_NAMES:
        assert (series / "snapshots" / name / "slot.json").is_file()
    missing = json.loads((series / "snapshots" / "s1" / "slot.json").read_text(encoding="utf-8"))
    assert missing["unavailable_reason"] == "insufficient_history"
    assert missing["addressable"] is True
    first_compare = json.loads(
        (series / "comparisons" / "s1-s2" / "comparison.json").read_text(encoding="utf-8")
    )
    assert first_compare["status"] == "unavailable"


def test_failed_middle_slot_remains_addressable(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([], fail_slot_sha=shas[2]),
    )
    index = _index(series)
    assert [row["status"] for row in index["slots"]] == [
        "available",
        "available",
        "failed",
        "available",
        "available",
    ]
    failed = json.loads((series / "snapshots" / "s3" / "slot.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["source_revision"] == shas[2]
    assert (series / "snapshots" / "s1" / "slot.json").is_file()
    assert (series / "snapshots" / "s5" / "slot.json").is_file()
    adjacent = json.loads(
        (series / "comparisons" / "s2-s3" / "comparison.json").read_text(encoding="utf-8")
    )
    assert adjacent["status"] == "unavailable"


def test_rerun_keeps_prior_series(tmp_path: Path) -> None:
    repo, _shas = _five_commit_adversarial(tmp_path / "repo")
    artifact_root = tmp_path / ARTIFACT_ROOT_NAME
    first = run_trend_series(
        repo,
        artifact_root,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    second = run_trend_series(
        repo,
        artifact_root,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    assert first.bundle_directory is not None
    assert second.bundle_directory is not None
    assert first.bundle_directory != second.bundle_directory
    assert first.bundle_directory.is_dir()
    assert (first.bundle_directory / "snapshots" / "s1" / "slot.json").is_file()
    assert (second.bundle_directory / TREND_INDEX_FILENAME).is_file()
    series_dirs = list((artifact_root / TRENDS_DIRNAME).rglob(TREND_INDEX_FILENAME))
    assert len(series_dirs) == 2


def test_trend_bundle_does_not_collide_with_assess_current_previous(tmp_path: Path) -> None:
    repo, _shas = _five_commit_adversarial(tmp_path / "repo")
    artifact_root = tmp_path / ARTIFACT_ROOT_NAME
    assessments = artifact_root / ASSESSMENTS_DIRNAME / "local-repo"
    current = assessments / "current"
    previous = assessments / "previous"
    current.mkdir(parents=True)
    previous.mkdir(parents=True)
    (current / "assessment.json").write_text('{"slot":"current"}\n', encoding="utf-8")
    (previous / "assessment.json").write_text('{"slot":"previous"}\n', encoding="utf-8")
    run_trend_series(
        repo,
        artifact_root,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    assert (current / "assessment.json").read_text(encoding="utf-8") == '{"slot":"current"}\n'
    assert (previous / "assessment.json").read_text(encoding="utf-8") == '{"slot":"previous"}\n'
    assert not list(artifact_root.joinpath(TRENDS_DIRNAME).rglob("current"))


def test_feed_bytes_are_identical_across_available_slots(tmp_path: Path) -> None:
    repo, _shas = _five_commit_adversarial(tmp_path / "repo")
    feed = (tmp_path / "repo" / FEED_RELATIVE).read_bytes()
    expected = hash_feed_bytes(feed)
    series = tmp_path / "series"
    result = run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([]),
    )
    index = _index(series)
    assert index["profile"]["feed_bytes_digest"] == expected
    assert index["feed_bytes_identical_across_available_slots"] is True
    digests = {
        json.loads((series / "snapshots" / name / "slot.json").read_text(encoding="utf-8"))[
            "feed_bytes_digest"
        ]
        for name in SLOT_NAMES
        if json.loads((series / "snapshots" / name / "slot.json").read_text(encoding="utf-8"))[
            "status"
        ]
        == "available"
    }
    assert digests == {expected}
    assert {slot.feed_digest for slot in result.slots if slot.status == "available"} == {expected}


def test_path_safety_rejects_escape_and_unknown_names() -> None:
    with pytest.raises(TrendBundleError):
        validate_bundle_segment("../etc", kind="slot")
    with pytest.raises(TrendBundleError):
        validate_bundle_segment("s9", kind="slot")
    with pytest.raises(TrendBundleError):
        validate_bundle_segment("s1-s9", kind="comparison")
    with pytest.raises(TrendBundleError):
        validate_bundle_segment("s1/s2", kind="comparison")


def test_artifact_root_nests_trends_namespace(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    repo.mkdir()
    root = tmp_path / ARTIFACT_ROOT_NAME
    series = resolve_series_directory(root, repo)
    assert TRENDS_DIRNAME in series.parts
    assert ASSESSMENTS_DIRNAME not in series.parts
    assert series.is_relative_to(root / TRENDS_DIRNAME)
