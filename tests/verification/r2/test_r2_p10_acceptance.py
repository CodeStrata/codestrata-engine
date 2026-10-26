"""R2-P10 acceptance locks: boundary, matrix semantics, M29, no new product scope."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from tests.application.incremental.git_repo_helpers import commit_dated, init_repo, write
from tests.application.incremental.test_m29_graph_delta_blast_radius import (
    DummyEdge,
    DummyGraph,
    DummyNode,
)
from tests.application.incremental.test_r2_p06_trend_series import (
    LATER_MARKER,
    LATER_PATH,
    _five_commit_adversarial,
)

from codestrata import RULESET_VERSION, __version__
from codestrata.application.assessment import AssessmentCommandError
from codestrata.application.incremental.graph_delta import calculate_static_blast_radius
from codestrata.application.incremental.source_states import capture_worktree_fingerprint
from codestrata.application.incremental.trend_series import run_trend_series
from codestrata.cli.community_contract import PRIMARY_COMMANDS, UNSUPPORTED_RULE_COMMANDS
from codestrata.config import CodestrataSettings
from codestrata.domain.contracts.enums import OutcomeFamily

ENGINE = Path(__file__).resolve().parents[3]
SRC = ENGINE / "src" / "codestrata"
PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _settings(tmp_path: Path, repo: Path) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "knowledge": {"enabled": False, "directory": str(tmp_path / "knowledge")},
            "static_analysis": {"enabled": False},
        }
    )


def _fake_assess(calls: list[dict[str, Any]], *, fail_slot_sha: str | None = None):
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


def test_selected_package_keeps_four_outcomes_and_primary_commands() -> None:
    assert __version__ == "0.3.1"
    assert RULESET_VERSION == "1.2.0"
    assert [member.value for member in OutcomeFamily] == [
        "architecture",
        "security",
        "quality",
        "maintainability",
    ]
    assert PRIMARY_COMMANDS == ("init", "doctor", "assess", "compare", "trend")
    assert UNSUPPORTED_RULE_COMMANDS == ("create", "load", "new", "import")


def test_engine_src_still_has_no_platform_import() -> None:
    forbidden = ("import codestrata_platform", "from codestrata_platform")
    offenders = [
        str(path.relative_to(ENGINE))
        for path in SRC.rglob("*.py")
        if any(fragment in path.read_text(encoding="utf-8") for fragment in forbidden)
    ]
    assert offenders == []


def test_short_history_keeps_five_slots(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "short")
    write(repo, "src/app.js", "function score(n) { return 1; }\n")
    commit_dated(repo, "s1", unix=1_700_000_000)
    write(repo, "src/app.js", "function score(n) { return 2; }\n")
    commit_dated(repo, "s2", unix=1_700_000_100)
    write(repo, "src/app.js", "function score(n) { return 3; }\n")
    commit_dated(repo, "s3", unix=1_700_000_200)
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess(calls),
    )
    assert len(result.slots) == 5
    assert [slot.status for slot in result.slots] == [
        "unavailable",
        "unavailable",
        "available",
        "available",
        "available",
    ]


def test_failed_middle_and_dirty_and_leakage_remain_honest(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    write(repo, "dirty-uncommitted.js", f"function {LATER_MARKER}Dirty() {{}}\n")
    before = capture_worktree_fingerprint(repo)
    calls: list[dict[str, Any]] = []
    result = run_trend_series(
        repo,
        tmp_path / "out",
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess(calls, fail_slot_sha=shas[2]),
    )
    assert [slot.status for slot in result.slots] == [
        "available",
        "available",
        "failed",
        "available",
        "available",
    ]
    assert result.worktree_unchanged is True
    assert capture_worktree_fingerprint(repo) == before
    assert "dirty-uncommitted.js" not in result.slots[-1].file_paths
    oldest = result.slots[0]
    assert LATER_PATH not in oldest.file_paths
    assert LATER_MARKER not in " ".join(oldest.file_paths)


def test_m29_cutoff_lower_bound_unchanged() -> None:
    nodes = [DummyNode(name) for name in ["A", "B", "C", "D", "E", "F"]]
    edges = [
        DummyEdge("e1", "A", "B"),
        DummyEdge("e2", "B", "C"),
        DummyEdge("e3", "C", "D"),
        DummyEdge("e4", "D", "E"),
        DummyEdge("e5", "E", "F"),
    ]
    radius, _summary = calculate_static_blast_radius(
        seeds=["F"],
        graph=DummyGraph(nodes, edges),
        max_depth=2,
    )
    assert set(radius.affected_component_ids) == {"D", "E", "F"}
    assert radius.cutoff is True
    assert radius.cutoff_reason == "depth_bound_truncated"
    assert radius.lower_bound is True
