"""R2-P06 leakage-safe five-snapshot orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from codestrata.application.assessment import AssessmentCommandError
from codestrata.application.incremental.source_states import (
    SERIES_SLOT_COUNT,
    capture_worktree_fingerprint,
)
from codestrata.application.incremental.trend_series import (
    DIRTY_WORKTREE_NOTICE,
    run_trend_series,
)
from codestrata.config import CodestrataSettings
from codestrata.reporting.journey_observations import FEED_RELATIVE
from tests.application.incremental.git_repo_helpers import _git, commit_dated, init_repo, write

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
LATER_PATH = "src/later.js"
LATER_MARKER = "laterOnlyLeakageMarker"
LATER_AUTHOR = "Later Owner"


def _settings(tmp_path: Path, repo: Path) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "knowledge": {"enabled": False, "directory": str(tmp_path / "knowledge")},
            "static_analysis": {"enabled": False},
        }
    )


def _fake_assess_factory(calls: list[dict[str, Any]], *, fail_slot_sha: str | None = None):
    def assess(repo: str, output: Path, **kwargs: Any) -> MagicMock:
        calls.append({"repo": repo, "output": str(output), **kwargs})
        if fail_slot_sha and kwargs.get("history_head") == fail_slot_sha:
            raise AssessmentCommandError("forced slot failure")
        root = Path(repo)
        files = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        )
        analysis = MagicMock()
        analysis.metadata = {
            "source_revision": kwargs.get("history_head"),
            "git_head": kwargs.get("history_head"),
            "dirty": False,
            "feed_digest": "feed",
            "evaluation_time": "2026-10-03T12:00:00Z",
            "canonical_hotspots": [{"subject_id": path} for path in files if path.endswith(".js")],
            "canonical_cochange": [],
            "canonical_ownership": [{"history_profile_id": kwargs.get("history_head")}],
            "canonical_limitations": [],
        }
        analysis.repository.files = files
        analysis.findings = []
        result = MagicMock()
        result.analysis_result = analysis
        return result

    return assess


def _five_commit_adversarial(root: Path) -> tuple[Path, list[str]]:
    repo = init_repo(root)
    shas: list[str] = []
    write(repo, "src/app.js", "function app() { return 1; }\n")
    shas.append(commit_dated(repo, "s1", unix=1_700_000_000))
    write(repo, "src/app.js", "function app() { return 2; }\n")
    shas.append(commit_dated(repo, "s2", unix=1_700_000_100))
    write(repo, "src/app.js", "function app() { return 3; }\n")
    write(repo, "src/pair.js", "function pair() { return 1; }\n")
    shas.append(commit_dated(repo, "s3", unix=1_700_000_200))
    write(repo, "src/app.js", "function app() { return 4; }\n")
    write(repo, "src/pair.js", "function pair() { return 2; }\n")
    shas.append(commit_dated(repo, "s4", unix=1_700_000_300))
    write(repo, "src/app.js", "function app() { return 5; }\n")
    write(
        repo,
        LATER_PATH,
        (
            f"function {LATER_MARKER}() {{\n"
            "  const AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE';\n"
            "  let n = 0;\n"
            "  if (n) { n += 1; }\n"
            "  if (n) { n += 2; }\n"
            "  if (n) { n += 3; }\n"
            "  return n;\n"
            "}\n"
        ),
    )
    write(repo, FEED_RELATIVE, json.dumps({"provider_id": "osv.dev", "advisories": []}))
    shas.append(
        commit_dated(
            repo,
            "s5 later-only facts",
            unix=1_700_000_400,
            author_name=LATER_AUTHOR,
            author_email="later@example.test",
        )
    )
    return repo, shas


def test_five_slots_preserved_when_history_is_short(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "short")
    write(repo, "src/app.js", "function app() { return 1; }\n")
    commit_dated(repo, "one", unix=1_700_000_000)
    write(repo, "src/app.js", "function app() { return 2; }\n")
    commit_dated(repo, "two", unix=1_700_000_100)
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls),
    )
    assert len(result.slots) == SERIES_SLOT_COUNT
    assert [slot.status for slot in result.slots] == [
        "unavailable",
        "unavailable",
        "unavailable",
        "available",
        "available",
    ]
    assert result.slots[0].unavailable_reason == "insufficient_history"
    assert result.slots[2].unavailable_reason == "insufficient_history"
    assert len(calls) == 2
    assert all(item["history_head"] for item in calls)


def test_failed_middle_slot_stays_explicit(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls, fail_slot_sha=shas[2]),
    )
    assert [slot.status for slot in result.slots] == [
        "available",
        "available",
        "failed",
        "available",
        "available",
    ]
    assert result.slots[2].unavailable_reason == "assessment_failed"
    assert any("assessment_failed" in item for item in result.slots[2].limitations)
    assert len(result.slots) == 5


def test_dirty_worktree_is_excluded_and_left_untouched(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    write(repo, "dirty-uncommitted.js", f"function {LATER_MARKER}Dirty() {{}}\n")
    write(repo, "src/app.js", "function app() { return 'dirty'; }\n")
    before = capture_worktree_fingerprint(repo)
    assert before.dirty is True
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls),
    )
    assert result.dirty_worktree is True
    assert result.dirty_notice == DIRTY_WORKTREE_NOTICE
    assert result.worktree_unchanged is True
    after = capture_worktree_fingerprint(repo)
    assert after == before
    assert (repo / "dirty-uncommitted.js").is_file()
    head_files = result.slots[-1].file_paths
    assert "dirty-uncommitted.js" not in head_files
    assert result.slots[-1].sha == shas[-1]


def test_p05_skipped_submodule_is_surfaced(tmp_path: Path) -> None:
    other = init_repo(tmp_path / "other")
    write(other, "secret-module.py", "print('module')\n")
    other_sha = commit_dated(other, "module", unix=1_700_000_000)
    repo = init_repo(tmp_path / "super")
    write(repo, "src/app.js", "function app() { return 1; }\n")
    commit_dated(repo, "app", unix=1_700_000_100)
    _git(repo, ["update-index", "--add", "--cacheinfo", f"160000,{other_sha},vendor/dep"])
    _git(repo, ["commit", "-m", "add gitlink"])
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls),
    )
    head = result.slots[-1]
    assert head.status == "available"
    assert any(item.startswith("skipped_submodule:") for item in head.limitations)
    assert "secret-module.py" not in head.file_paths


def test_pinned_profile_is_shared_and_history_head_is_slot_sha(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory(calls),
    )
    assert [item["history_head"] for item in calls] == shas
    clocks = {item["clock"]() for item in calls}
    assert clocks == {PINNED}
    available = [slot for slot in result.slots if slot.status == "available"]
    assert len(available) == 5
    assert {slot.engine_version for slot in available} == {result.profile.engine_version}
    assert {slot.evaluation_time for slot in available} == {"2026-10-03T12:00:00Z"}
    assert {slot.config_digest for slot in available} == {result.profile.config_digest}
    assert all(slot.git_head == slot.sha for slot in available)
    assert all(slot.source_revision == slot.sha for slot in available)
    assert all(slot.dirty is False for slot in available)
    payload = json.loads((tmp_path / "out" / "trend-series.json").read_text(encoding="utf-8"))
    assert payload["schema_name"] == "codestrata.trend-series.v1"
    assert len(payload["slots"]) == 5


def test_adversarial_later_facts_do_not_leak_into_s1(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
    )
    assert [slot.sha for slot in result.slots] == shas
    assert all(slot.status == "available" for slot in result.slots)
    first, *_, last = result.slots
    assert first.source_revision == shas[0]
    assert first.git_head == shas[0]
    assert first.dirty is False
    assert last.source_revision == shas[-1]
    report_files = list(Path(first.output_directory or tmp_path).rglob("*.json"))
    report_text = "\n".join(path.read_text(encoding="utf-8") for path in report_files)
    assert LATER_PATH not in first.file_paths
    assert LATER_PATH not in first.hotspot_subjects
    assert LATER_PATH not in first.graph_node_ids
    assert all(
        LATER_PATH not in left and LATER_PATH not in right
        for left, right in first.cochange_pairs
    )
    assert LATER_PATH not in report_text
    assert LATER_MARKER not in report_text
    assert LATER_AUTHOR not in report_text
    assert shas[-1] not in (first.git_head, first.source_revision)
    assert shas[-1] not in first.ownership_profile_ids
    assert shas[-1] not in report_text
    assert LATER_PATH in last.file_paths
    assert first.evaluation_time == last.evaluation_time
    assert first.engine_version == last.engine_version
    assert first.config_digest == last.config_digest
    assert result.worktree_unchanged is True
    assert result.profile.evaluation_time == PINNED


def test_trend_cli_registers_fixed_five_and_requires_repo() -> None:
    runner = CliRunner()
    from codestrata.cli import app

    help_result = runner.invoke(app, ["trend", "--help"])
    assert help_result.exit_code == 0
    text = help_result.stdout + help_result.stderr
    assert "--repo" in text
    assert "--max-count" not in text
    missing = runner.invoke(app, ["trend"])
    assert missing.exit_code != 0
