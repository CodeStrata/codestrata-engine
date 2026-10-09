"""R2-G2 semantic config identity vs operational storage paths."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.incremental.trend_series import (
    freeze_evaluation_profile,
    run_trend_series,
    semantic_assessment_config,
)
from codestrata.config import CodestrataSettings
from tests.application.incremental.git_repo_helpers import commit_dated, init_repo, write
from tests.application.incremental.test_r2_p06_trend_series import (
    _fake_assess_factory,
    _five_commit_adversarial,
    _settings,
)

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def test_semantic_config_ignores_operational_directories() -> None:
    left = CodestrataSettings.model_validate(
        {
            "repository": {"path": "/tmp/series-a/repo"},
            "knowledge": {"enabled": False, "directory": "/tmp/series-a/knowledge"},
            "workspace": {"directory": "/tmp/series-a/workspace"},
            "static_analysis": {"enabled": False},
        }
    )
    right = CodestrataSettings.model_validate(
        {
            "repository": {"path": "/tmp/series-b/repo"},
            "knowledge": {"enabled": False, "directory": "/tmp/series-b/knowledge"},
            "workspace": {"directory": "/tmp/series-b/workspace"},
            "static_analysis": {"enabled": False},
        }
    )
    assert semantic_assessment_config(left) == semantic_assessment_config(right)
    assert freeze_evaluation_profile(
        Path("."), evaluation_time=PINNED, settings=left
    ).config_digest == freeze_evaluation_profile(
        Path("."), evaluation_time=PINNED, settings=right
    ).config_digest


def test_genuine_rules_change_changes_config_digest() -> None:
    base = CodestrataSettings.model_validate(
        {
            "repository": {"path": "/tmp/repo"},
            "knowledge": {"enabled": False, "directory": "/tmp/knowledge"},
            "static_analysis": {"enabled": False},
        }
    )
    changed = CodestrataSettings.model_validate(
        {
            "repository": {"path": "/tmp/repo"},
            "knowledge": {"enabled": False, "directory": "/tmp/knowledge"},
            "static_analysis": {"enabled": True},
        }
    )
    left = freeze_evaluation_profile(Path("."), evaluation_time=PINNED, settings=base)
    right = freeze_evaluation_profile(Path("."), evaluation_time=PINNED, settings=changed)
    assert left.config_digest != right.config_digest
    assert left.engine_version == right.engine_version
    assert left.ruleset_version == right.ruleset_version
    assert left.evaluation_time == right.evaluation_time
    assert left.feed_digest == right.feed_digest


def test_two_series_share_config_digest_and_m31_identity(tmp_path: Path) -> None:
    repo, _shas = _five_commit_adversarial(tmp_path / "repo")
    settings = _settings(tmp_path, repo)
    first = run_trend_series(
        repo,
        tmp_path / "series-a",
        evaluation_time=PINNED,
        settings=settings,
        assess=_fake_assess_factory([]),
    )
    second = run_trend_series(
        repo,
        tmp_path / "series-b",
        evaluation_time=PINNED,
        settings=settings,
        assess=_fake_assess_factory([]),
    )
    assert first.bundle_directory != second.bundle_directory
    assert first.profile.config_digest == second.profile.config_digest
    assert {slot.config_digest for slot in first.slots} == {first.profile.config_digest}
    assert {slot.config_digest for slot in second.slots} == {second.profile.config_digest}
    assert [slot.sha for slot in first.slots] == [slot.sha for slot in second.slots]
    assert [slot.status for slot in first.slots] == [slot.status for slot in second.slots]
    assert first.profile.engine_version == second.profile.engine_version
    assert first.profile.ruleset_version == second.profile.ruleset_version
    assert first.profile.feed_digest == second.profile.feed_digest
    assert first.profile.evaluation_time == second.profile.evaluation_time


def test_different_knowledge_directories_do_not_change_series_digest_identity(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "tiny")
    write(repo, "src/app.js", "function app() { return 1; }\n")
    commit_dated(repo, "one", unix=1_700_000_000)
    left_settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "knowledge": {"enabled": False, "directory": str(tmp_path / "k-a")},
            "static_analysis": {"enabled": False},
        }
    )
    right_settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "knowledge": {"enabled": False, "directory": str(tmp_path / "k-b")},
            "static_analysis": {"enabled": False},
        }
    )
    left = run_trend_series(
        repo,
        tmp_path / "out-a",
        evaluation_time=PINNED,
        settings=left_settings,
        assess=_fake_assess_factory([]),
    )
    right = run_trend_series(
        repo,
        tmp_path / "out-b",
        evaluation_time=PINNED,
        settings=right_settings,
        assess=_fake_assess_factory([]),
    )
    assert left.profile.config_digest == right.profile.config_digest
