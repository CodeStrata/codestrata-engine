"""R2-G2 subdirectory / monorepo assessment-scope proof."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.incremental.source_states import (
    SERIES_SLOT_COUNT,
    capture_worktree_fingerprint,
)
from codestrata.application.incremental.trend_bundle import COMPARISON_NAMES
from codestrata.application.incremental.trend_series import run_trend_series
from codestrata.reporting.journey_observations import FEED_RELATIVE
from tests.application.incremental.git_repo_helpers import commit_dated, init_repo, write
from tests.application.incremental.test_r2_p06_trend_series import _fake_assess_factory, _settings

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
UNRELATED_MARKER = "UNRELATED_LEAK"
UNRELATED_PATH = "unrelated/secret.js"
TARGET_APP = "src/app.js"


def _five_commit_monorepo(root: Path) -> tuple[Path, list[str]]:
    repo = init_repo(root)
    shas: list[str] = []
    for index in range(1, 6):
        write(repo, f"target/{TARGET_APP}", f"function app() {{ return {index}; }}\n")
        write(
            repo,
            UNRELATED_PATH,
            f"function {UNRELATED_MARKER}() {{ return {index}; }}\n",
        )
        if index == 5:
            write(
                repo,
                f"target/{FEED_RELATIVE}",
                json.dumps({"provider_id": "osv.dev", "advisories": []}),
            )
        shas.append(commit_dated(repo, f"s{index} both trees", unix=1_700_000_000 + index * 100))
    return repo, shas


def _assert_no_unrelated(text: str) -> None:
    assert UNRELATED_MARKER not in text
    assert "unrelated/" not in text
    assert "secret.js" not in text


def test_trend_repo_target_excludes_unrelated_evidence(tmp_path: Path) -> None:
    repo, shas = _five_commit_monorepo(tmp_path / "mono")
    before = capture_worktree_fingerprint(repo)
    target = repo / "target"
    series = tmp_path / "target-series"
    result = run_trend_series(
        target,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, target),
    )
    after = capture_worktree_fingerprint(repo)
    assert after == before
    assert result.worktree_unchanged is True
    assert result.git_root == repo.resolve()
    assert result.assessment_relpath == "target"
    assert [slot.sha for slot in result.slots] == shas
    assert [slot.status for slot in result.slots] == ["available"] * SERIES_SLOT_COUNT
    for slot in result.slots:
        assert slot.git_head == slot.sha
        assert slot.source_revision == slot.sha
        blob = "\n".join(
            [
                " ".join(slot.file_paths),
                " ".join(slot.hotspot_subjects),
                " ".join(slot.finding_titles),
                " ".join(slot.graph_node_ids),
                " ".join(f"{left} {right}" for left, right in slot.cochange_pairs),
                " ".join(slot.ownership_profile_ids),
            ]
        )
        _assert_no_unrelated(blob)
        assert TARGET_APP in slot.file_paths or any(
            path.endswith("app.js") for path in slot.file_paths
        )
        assert not any(
            path.startswith("unrelated/") or path.startswith("target/")
            for path in slot.file_paths
        )

    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in series.rglob("*")
        if path.is_file()
    )
    _assert_no_unrelated(persisted)
    html = (series / "five-commit-trend.html").read_text(encoding="utf-8")
    _assert_no_unrelated(html)
    for name in COMPARISON_NAMES:
        payload = json.loads((series / "comparisons" / name / "comparison.json").read_text())
        files = [item.get("path") for item in (payload.get("m27") or {}).get("files") or ()]
        _assert_no_unrelated(json.dumps(payload))
        assert all(path is None or not str(path).startswith("unrelated/") for path in files)


def test_root_level_trend_still_assesses_whole_repository(tmp_path: Path) -> None:
    repo, shas = _five_commit_monorepo(tmp_path / "mono")
    calls: list[dict[str, object]] = []
    result = run_trend_series(
        repo,
        tmp_path / "root-series",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls),
    )
    assert result.assessment_relpath == ""
    assert result.git_root == repo.resolve()
    head = result.slots[-1]
    assert head.sha == shas[-1]
    assert UNRELATED_PATH in head.file_paths
    assert f"target/{TARGET_APP}" in head.file_paths
    assert any(Path(str(item["repo"])).name == "s5" for item in calls)


def test_unrelated_only_change_is_not_a_target_m27_change(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "mono")
    shas: list[str] = []
    write(repo, f"target/{TARGET_APP}", "function app() { return 1; }\n")
    write(repo, UNRELATED_PATH, f"function {UNRELATED_MARKER}() {{ return 1; }}\n")
    shas.append(commit_dated(repo, "s1", unix=1_700_000_000))
    for index in range(2, 6):
        write(repo, UNRELATED_PATH, f"function {UNRELATED_MARKER}() {{ return {index}; }}\n")
        shas.append(
            commit_dated(repo, f"s{index} unrelated only", unix=1_700_000_000 + index * 100)
        )
    result = run_trend_series(
        repo / "target",
        tmp_path / "unrelated-only",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo / "target"),
    )
    assert [slot.sha for slot in result.slots] == shas
    for name in COMPARISON_NAMES:
        comparison = Path(result.bundle_directory or tmp_path) / "comparisons" / name
        payload = json.loads((comparison / "comparison.json").read_text())
        files = [item.get("path") for item in (payload.get("m27") or {}).get("files") or ()]
        assert files == []
        assert (payload.get("m27") or {}).get("changed_file_count") == 0
        _assert_no_unrelated(json.dumps(payload))
