"""E09.2 bounded history index: M24 churn/recency, M25 concentration, M26 co-change."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codestrata.application.incremental.history_index import (
    ConcentrationScope,
    HistoryCoverage,
    HistoryIndexError,
    HistoryIndexRequest,
    RawCommitRecord,
    build_history_index,
    local_identity,
    select_included_commits,
    write_history_index,
)
from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.enums import FreshnessState, MetricStatus
from tests.application.incremental.git_repo_helpers import (
    _git,
    commit_dated,
    init_repo,
    write,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e09.2"
EVAL = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
EVAL_UNIX = int(EVAL.timestamp())
DAY = 86400


def _request(repo: Path, **overrides: object) -> HistoryIndexRequest:
    payload: dict[str, object] = {
        "repository_root": repo,
        "evaluation_time": EVAL,
    }
    payload.update(overrides)
    return HistoryIndexRequest(**payload)  # type: ignore[arg-type]


def _lines(text: str, count: int) -> str:
    return "".join(f"{text}{index}\n" for index in range(count))


def test_naive_evaluation_time_is_rejected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "a.txt", "a\n")
    commit_dated(repo, "base", unix=EVAL_UNIX - DAY)
    with pytest.raises(HistoryIndexError, match="pinned UTC"):
        build_history_index(
            HistoryIndexRequest(
                repository_root=repo,
                evaluation_time=datetime(2026, 9, 23, 12, 0),
            )
        )


def _alice(repo: Path, message: str, unix: int) -> str:
    return commit_dated(
        repo,
        message,
        unix=unix,
        author_name="Alice",
        author_email="alice@ex.test",
    )


def test_known_edits_rename_binary_and_jsonl_index(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", _lines("old", 4))
    _alice(repo, "known edits", EVAL_UNIX - 10 * DAY)
    _git(repo, ["mv", "src/app.py", "src/service.py"])
    _alice(repo, "rename file", EVAL_UNIX - 9 * DAY)
    write(repo, "src/service.py", _lines("new", 5))
    _alice(repo, "edit after rename", EVAL_UNIX - 8 * DAY)
    write(repo, "assets/logo.bin", b"\x00\xff\x00")
    _alice(repo, "binary blob", EVAL_UNIX - 7 * DAY)
    index = build_history_index(_request(repo))
    assert index.bounds.profile_id == "git.history.reachable-non-merge-180d-1000"
    assert index.bounds.first_parent_combined_with_skip_merges is False
    paths = {item.path: item for item in index.file_churn}
    assert "src/service.py" in paths
    assert "src/app.py" in paths["src/service.py"].renamed_from
    assert paths["src/service.py"].changed_lines is not None
    assert paths["src/service.py"].changed_lines > 0
    assert paths["assets/logo.bin"].binary_unknown is True
    assert paths["assets/logo.bin"].changed_lines is None
    written = write_history_index(index, tmp_path / "index")
    manifest = json.loads(written["index-manifest.json"].read_text(encoding="utf-8"))
    assert manifest["schema_name"] == "codestrata.git-history-index.v1"
    assert manifest["bugfix_markers_are_proven_defects"] is False
    commits = written["commits.jsonl"].read_text(encoding="utf-8").strip().splitlines()
    assert len(commits) == index.bounds.observed_included_count


def test_merge_only_integration_keeps_reachable_feature_commits(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "base.txt", "base\n")
    commit_dated(repo, "base", unix=EVAL_UNIX - 20 * DAY)
    _git(repo, ["checkout", "-b", "feature"])
    write(repo, "feature.txt", "feature-line\n")
    feature_sha = commit_dated(repo, "feature work", unix=EVAL_UNIX - 19 * DAY)
    _git(repo, ["checkout", "main"])
    _git(repo, ["merge", "--no-ff", "-m", "merge feature", "feature"])
    merge_sha = _git(repo, ["rev-parse", "HEAD"]).strip()
    index = build_history_index(_request(repo))
    included = {item.sha for item in index.included}
    assert feature_sha in included
    assert merge_sha not in included
    assert merge_sha in index.merge_shas
    assert "merge_commits_excluded" in index.limitations
    assert index.bounds.first_parent_combined_with_skip_merges is False


def test_squash_is_single_included_commit(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "keep.txt", "keep\n")
    commit_dated(repo, "base", unix=EVAL_UNIX - 12 * DAY)
    _git(repo, ["checkout", "-b", "topic"])
    write(repo, "topic.txt", "one\n")
    commit_dated(repo, "topic 1", unix=EVAL_UNIX - 11 * DAY)
    write(repo, "topic.txt", "one\ntwo\n")
    topic_sha = commit_dated(repo, "topic 2", unix=EVAL_UNIX - 10 * DAY)
    _git(repo, ["checkout", "main"])
    _git(repo, ["merge", "--squash", "topic"])
    squash_sha = commit_dated(repo, "squash topic", unix=EVAL_UNIX - 9 * DAY)
    index = build_history_index(_request(repo))
    included = {item.sha for item in index.included}
    assert squash_sha in included
    assert topic_sha not in included


def test_merge_conflict_only_edits_are_disclosed_and_excluded(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "conflict.txt", "shared\n")
    commit_dated(repo, "base", unix=EVAL_UNIX - 15 * DAY)
    _git(repo, ["checkout", "-b", "other"])
    write(repo, "conflict.txt", "branch-side\n")
    branch_sha = commit_dated(repo, "branch edit", unix=EVAL_UNIX - 14 * DAY)
    _git(repo, ["checkout", "main"])
    write(repo, "conflict.txt", "main-side\n")
    commit_dated(repo, "main edit", unix=EVAL_UNIX - 13 * DAY)
    merge = subprocess_merge_with_resolution(repo, "other", "resolved-only-in-merge\n")
    index = build_history_index(_request(repo))
    included = {item.sha for item in index.included}
    assert branch_sha in included
    assert merge not in included
    assert merge in index.merge_conflict_only_shas
    assert "merge_conflict_resolution_edits_excluded" in index.limitations
    churn = next(item for item in index.file_churn if item.path == "conflict.txt")
    assert churn.changed_lines is not None
    working = (repo / "conflict.txt").read_text(encoding="utf-8")
    assert working == "resolved-only-in-merge\n"


def subprocess_merge_with_resolution(repo: Path, branch: str, resolution: str) -> str:
    try:
        _git(repo, ["merge", "--no-ff", "--no-commit", branch])
    except subprocess.CalledProcessError:
        pass
    write(repo, "conflict.txt", resolution)
    _git(repo, ["add", "conflict.txt"])
    env = {
        "GIT_AUTHOR_DATE": f"{EVAL_UNIX - 12 * DAY} +0000",
        "GIT_COMMITTER_DATE": f"{EVAL_UNIX - 12 * DAY} +0000",
    }
    _git(repo, ["commit", "-m", "merge conflict"], env=env)
    return _git(repo, ["rev-parse", "HEAD"]).strip()


def test_future_timestamp_excluded_from_recency_and_window(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "ok.txt", "ok\n")
    past = commit_dated(repo, "past", unix=EVAL_UNIX - DAY)
    write(repo, "future.txt", "future\n")
    future = commit_dated(repo, "from the future", unix=EVAL_UNIX + 5 * DAY)
    index = build_history_index(_request(repo))
    included = {item.sha for item in index.included}
    assert past in included
    assert future not in included
    assert future in index.excluded_future_shas
    assert "future_timestamp_excluded_from_recency" in index.limitations
    assert index.bounds.observed_newest_committer_unix == EVAL_UNIX - DAY


def test_window_boundary_inclusive_on_start(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    start = EVAL_UNIX - 180 * DAY
    write(repo, "inside.txt", "in\n")
    inside = commit_dated(repo, "on boundary", unix=start)
    write(repo, "outside.txt", "out\n")
    outside = commit_dated(repo, "before window", unix=start - 1)
    index = build_history_index(_request(repo))
    included = {item.sha for item in index.included}
    assert inside in included
    assert outside not in included


def test_select_included_applies_latest_1000_after_180d() -> None:
    profile = load_launch_ratification().history.model_copy(update={"max_commits": 3})
    records = tuple(
        RawCommitRecord(
            sha=f"{index:040x}",
            parents=("parent",),
            committer_unix=EVAL_UNIX - index * DAY,
            author_name="A",
            author_email="a@ex.test",
            mapped_name="A",
            mapped_email="a@ex.test",
            subject="n",
            body="",
            files=(),
        )
        for index in range(5)
    )
    included, truncated = select_included_commits(
        records, profile=profile, evaluation_unix=EVAL_UNIX
    )
    assert truncated is True
    assert [item.sha for item in included] == [f"{index:040x}" for index in range(3)]


def test_tie_breaks_equal_timestamp_by_sha() -> None:
    profile = load_launch_ratification().history
    stamp = EVAL_UNIX - DAY
    records = (
        RawCommitRecord("b" * 40, ("p",), stamp, "A", "a@x", "A", "a@x", "b", "", ()),
        RawCommitRecord("a" * 40, ("p",), stamp, "A", "a@x", "A", "a@x", "a", "", ()),
    )
    included, truncated = select_included_commits(
        records, profile=profile, evaluation_unix=EVAL_UNIX
    )
    assert truncated is False
    assert [item.sha for item in included] == ["a" * 40, "b" * 40]


def test_shallow_history_advertises_observed_bounds(tmp_path: Path) -> None:
    source = init_repo(tmp_path / "source")
    write(source, "a.txt", "one\n")
    commit_dated(source, "old", unix=EVAL_UNIX - 40 * DAY)
    write(source, "a.txt", "one\ntwo\n")
    commit_dated(source, "new", unix=EVAL_UNIX - DAY)
    clone = tmp_path / "shallow"
    _git(
        tmp_path,
        ["clone", "--no-local", "--depth", "1", str(source), str(clone)],
    )
    index = build_history_index(_request(clone))
    assert index.local_state.shallow is True
    assert index.bounds.complete_window is False
    assert "git_history_shallow" in index.limitations or "shallow_history" in index.limitations
    m24 = next(item for item in index.capabilities if item.capability_id == "M24")
    assert m24.coverage is HistoryCoverage.PARTIAL
    assert "git_history_shallow" in m24.unknown_reasons
    assert m24.requested_window_days == 180
    assert m24.requested_max_commits == 1000
    assert m24.observed_commit_count >= 1
    assert m24.freshness is FreshnessState.NOT_APPLICABLE
    assert m24.freshness_reason == "not_time_sensitive"


def test_missing_history_is_unknown(tmp_path: Path) -> None:
    empty = tmp_path / "not-git"
    empty.mkdir()
    index = build_history_index(_request(empty))
    assert index.bounds.observed_included_count == 0
    m24 = next(item for item in index.capabilities if item.capability_id == "M24")
    assert m24.coverage is HistoryCoverage.MISSING
    assert "git_history_missing" in m24.unknown_reasons
    assert m24.freshness is FreshnessState.UNKNOWN


def test_bugfix_markers_are_context_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "a.py", "print(1)\n")
    positive = commit_dated(repo, "fixed login timeout", unix=EVAL_UNIX - 3 * DAY)
    write(repo, "a.py", "print(1)\nprint(2)\n")
    misleading = commit_dated(repo, "fix formatting only", unix=EVAL_UNIX - 2 * DAY)
    write(repo, "a.py", "print(1)\nprint(2)\nprint(3)\n")
    other = commit_dated(repo, "add logging", unix=EVAL_UNIX - DAY)
    index = build_history_index(_request(repo))
    marked = {item.sha for item in index.included if item.bugfix_marker}
    assert positive in marked
    assert misleading in marked
    assert other not in marked
    assert index.bugfix_markers.proven_defects is False
    assert index.bugfix_markers.productivity_claim is False
    assert index.bugfix_markers.intent_claim is False
    assert index.bugfix_markers.matched_commit_count == 2


def test_mailmap_two_contributors_and_expected_fixture(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, ".mailmap", "Alice Example <alice@ex.test> Ali Alias <ali@ex.test>\n")
    write(repo, "alpha.txt", _lines("a", 4))
    commit_dated(
        repo,
        "alice alpha",
        unix=EVAL_UNIX - 4 * DAY,
        author_name="Ali Alias",
        author_email="ali@ex.test",
    )
    write(repo, "beta.txt", _lines("b", 2))
    commit_dated(
        repo,
        "alice beta",
        unix=EVAL_UNIX - 3 * DAY,
        author_name="Ali Alias",
        author_email="ali@ex.test",
    )
    write(repo, "beta.txt", _lines("b", 4))
    commit_dated(
        repo,
        "bob beta",
        unix=EVAL_UNIX - 2 * DAY,
        author_name="Bob",
        author_email="bob@ex.test",
    )
    index = build_history_index(
        _request(
            repo,
            component_map={"alpha.txt": "comp-a", "beta.txt": "comp-b"},
        )
    )
    assert index.mailmap_applied is True
    repo_c = next(
        item
        for item in index.concentrations
        if item.scope is ConcentrationScope.REPOSITORY
    )
    expected_path = FIXTURE_DIR / "expected-two-contributors.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert repo_c.status is MetricStatus.VALUE
    assert repo_c.largest_share.serialized == expected["m25_repository"]["largest_share_serialized"]
    assert repo_c.contributors_to_50pct == expected["m25_repository"]["contributors_to_50pct"]
    assert repo_c.attributable_lines == expected["m25_repository"]["attributable_lines"]
    identities = {item.identity for item in repo_c.contributors}
    assert "Alice Example <alice@ex.test>" in identities
    assert "Ali Alias <ali@ex.test>" not in identities
    assert "not_organizational_bus_factor" in repo_c.notes
    alpha = next(item for item in index.concentrations if item.subject_id == "alpha.txt")
    beta = next(item for item in index.concentrations if item.subject_id == "beta.txt")
    assert alpha.largest_share.serialized == "1.000000"
    assert beta.largest_share.serialized == expected["m25_file_beta"]["largest_share_serialized"]
    assert repo_c.largest_share.serialized != "1.000000"
    comp_a = next(item for item in index.concentrations if item.subject_id == "comp-a")
    comp_b = next(item for item in index.concentrations if item.subject_id == "comp-b")
    assert comp_a.attributable_lines == 4
    assert comp_b.attributable_lines == 4


def test_weighted_component_aggregation_does_not_average_file_ratios(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "hot.py", _lines("h", 9))
    commit_dated(
        repo,
        "alice hot",
        unix=EVAL_UNIX - 3 * DAY,
        author_name="Alice",
        author_email="a@ex.test",
    )
    write(repo, "cold.py", "c0\n")
    commit_dated(
        repo,
        "bob cold",
        unix=EVAL_UNIX - 2 * DAY,
        author_name="Bob",
        author_email="b@ex.test",
    )
    index = build_history_index(
        _request(repo, component_map={"hot.py": "svc", "cold.py": "svc"})
    )
    component = next(item for item in index.concentrations if item.subject_id == "svc")
    assert component.attributable_lines == 10
    assert component.largest_share.serialized == "0.900000"
    assert component.contributors_to_50pct == 1


def test_zero_lines_not_applicable_and_missing_identity(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "empty.txt", "")
    commit_dated(
        repo,
        "empty add",
        unix=EVAL_UNIX - DAY,
        author_name="Ghost",
        author_email=" ",
    )
    index = build_history_index(_request(repo))
    repo_c = next(
        item
        for item in index.concentrations
        if item.scope is ConcentrationScope.REPOSITORY
    )
    assert repo_c.status is MetricStatus.NOT_APPLICABLE
    assert repo_c.unattributed_lines >= 0
    assert "missing_identity_visible" in repo_c.notes or repo_c.attributable_lines == 0


def test_declared_bots_only_when_listed(tmp_path: Path) -> None:
    bot_id = "dependabot[bot] <bot@ex.test>"
    repo = init_repo(tmp_path / "repo")
    write(repo, "a.txt", "a0\na1\n")
    commit_dated(
        repo,
        "bot bump",
        unix=EVAL_UNIX - DAY,
        author_name="dependabot[bot]",
        author_email="bot@ex.test",
    )
    unlabeled = build_history_index(_request(repo))
    labeled = build_history_index(_request(repo, declared_bot_identities=(bot_id,)))
    unlabeled_repo = next(
        item for item in unlabeled.concentrations if item.scope is ConcentrationScope.REPOSITORY
    )
    labeled_repo = next(
        item for item in labeled.concentrations if item.scope is ConcentrationScope.REPOSITORY
    )
    assert unlabeled_repo.contributors[0].bot_declared is False
    assert labeled_repo.contributors[0].bot_declared is True
    assert unlabeled_repo.contributors[0].identity == bot_id


def test_ambiguous_mapping_unknown_at_component_preserves_file_and_repo(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/old.py", "print(1)\n")
    commit_dated(
        repo,
        "add old",
        unix=EVAL_UNIX - 2 * DAY,
        author_name="Alice",
        author_email="a@ex.test",
    )
    _git(repo, ["mv", "src/old.py", "src/new.py"])
    commit_dated(
        repo,
        "rename",
        unix=EVAL_UNIX - DAY,
        author_name="Alice",
        author_email="a@ex.test",
    )
    index = build_history_index(
        _request(repo, component_map={"src/old.py": "legacy", "src/new.py": "modern"})
    )
    file_row = next(item for item in index.file_churn if item.path == "src/new.py")
    assert file_row.mapping_status == "unknown_ambiguous"
    repo_c = next(
        item for item in index.concentrations if item.scope is ConcentrationScope.REPOSITORY
    )
    assert repo_c.status is MetricStatus.VALUE
    file_c = next(item for item in index.concentrations if item.subject_id == "src/new.py")
    assert file_c.status is MetricStatus.VALUE
    ambiguous = [
        item
        for item in index.concentrations
        if item.mapping_status == "unknown_ambiguous" and item.scope is ConcentrationScope.COMPONENT
    ]
    assert ambiguous
    assert all(item.status is MetricStatus.UNKNOWN for item in ambiguous)


def test_cochange_always_together_unrelated_exact_support_and_bulk(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "pair_a.py", "a0\n")
    write(repo, "pair_b.py", "b0\n")
    commit_dated(repo, "together 1", unix=EVAL_UNIX - 6 * DAY)
    write(repo, "pair_a.py", "a0\na1\n")
    write(repo, "pair_b.py", "b0\nb1\n")
    commit_dated(repo, "together 2", unix=EVAL_UNIX - 5 * DAY)
    write(repo, "pair_a.py", "a0\na1\na2\n")
    write(repo, "pair_b.py", "b0\nb1\nb2\n")
    commit_dated(repo, "together 3", unix=EVAL_UNIX - 4 * DAY)
    write(repo, "solo.py", "s0\n")
    commit_dated(repo, "unrelated solo", unix=EVAL_UNIX - 3 * DAY)
    write(repo, "bulk1.py", "1\n")
    write(repo, "bulk2.py", "2\n")
    write(repo, "bulk3.py", "3\n")
    commit_dated(repo, "bulk formatting", unix=EVAL_UNIX - 2 * DAY)
    index = build_history_index(
        _request(
            repo,
            component_map={
                "pair_a.py": "paired",
                "pair_b.py": "paired",
                "solo.py": "lonely",
            },
        )
    )
    pair = next(
        item
        for item in index.cochange
        if item.scope == "file" and {item.left, item.right} == {"pair_a.py", "pair_b.py"}
    )
    assert pair.support == 3
    assert pair.supported_relation is True
    assert pair.jaccard.serialized == "1.000000"
    solo_pairs = [
        item
        for item in index.cochange
        if item.scope == "file" and "solo.py" in {item.left, item.right}
    ]
    assert all(item.supported_relation is False for item in solo_pairs)
    bulk = next(
        item
        for item in index.cochange
        if item.scope == "file" and {item.left, item.right} == {"bulk1.py", "bulk2.py"}
    )
    assert bulk.support == 1
    assert bulk.supported_relation is False
    assert bulk.union == 1


def test_observe_repository_history_uses_requested_head(tmp_path: Path) -> None:
    from codestrata.reporting.journey_observations import observe_repository

    repo = init_repo(tmp_path / "as-of")
    write(repo, "only_first.py", "x = 1\n")
    first = commit_dated(repo, "first", unix=1_700_000_000)
    write(repo, "only_second.py", "y = 2\n")
    commit_dated(repo, "second", unix=1_700_086_400)
    observed = observe_repository(
        repo,
        evaluation_time=datetime(2026, 9, 27, tzinfo=UTC),
        head=first,
    )
    heads = [row.git_head for row in observed.freshness if row.git_head]
    assert first in heads
    assert all("only_second.py" not in str(item.get("left", "")) for item in observed.cochange)
    assert all("only_second.py" not in str(item.get("right", "")) for item in observed.cochange)


def test_pinned_profile_and_local_identity_helpers() -> None:
    profile = load_launch_ratification().history
    assert profile.profile_id == "git.history.reachable-non-merge-180d-1000"
    assert "first-parent-only" in profile.merge_policy
    assert local_identity("A", "B@Ex.TEST") == "A <b@ex.test>"
    assert local_identity("A", "") is None
    assert timedelta(days=profile.window_days).days == 180
