"""R2-P05 first-parent selection and immutable snapshot materialization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.incremental.source_states import (
    SERIES_SLOT_COUNT,
    UNSUPPORTED_SOURCE_STATE_BEHAVIOR,
    SnapshotWorkspace,
    SourceStateUnavailableReason,
    capture_worktree_fingerprint,
    materialize_commit_tree,
    relative_assessment_path,
    select_first_parent_series,
    snapshot_assessment_root,
)
from codestrata.repository_auth.read_only_git import (
    ReadOnlyGitError,
    run_readonly_git,
    run_readonly_git_bytes,
)
from tests.application.incremental.git_repo_helpers import _git, commit_all, init_repo, write


def _tree_paths(repo: Path, sha: str) -> list[str]:
    raw = _git(repo, ["ls-tree", "-r", "--name-only", sha])
    return [line for line in raw.splitlines() if line]


def _blob_bytes(repo: Path, sha: str, path: str) -> bytes:
    return _git(repo, ["cat-file", "blob", f"{sha}:{path}"]).encode("utf-8")


def _five_commit_repo(root: Path) -> tuple[Path, list[str]]:
    repo = init_repo(root)
    shas: list[str] = []
    for index in range(1, 6):
        write(repo, "tracked.txt", f"state-{index}\n")
        write(repo, f"only-{index}.txt", f"only-{index}\n")
        shas.append(commit_all(repo, f"commit {index}"))
    return repo, shas


def test_five_commit_trees_match_each_sha(tmp_path: Path) -> None:
    repo, shas = _five_commit_repo(tmp_path / "repo")
    series = select_first_parent_series(repo)
    assert series.head_sha == shas[-1]
    assert [slot.sha for slot in series.slots] == shas
    assert all(slot.available for slot in series.slots)

    with SnapshotWorkspace(series) as workspace:
        assert len(workspace.snapshots) == SERIES_SLOT_COUNT
        for snapshot, sha in zip(workspace.snapshots, shas, strict=True):
            assert snapshot.slot.sha == sha
            assert snapshot.root is not None
            expected = _tree_paths(repo, sha)
            extracted = sorted(
                str(path.relative_to(snapshot.root))
                for path in snapshot.root.rglob("*")
                if path.is_file() or path.is_symlink()
            )
            assert extracted == sorted(expected)
            for relative in expected:
                target = snapshot.root / relative
                if target.is_symlink():
                    continue
                assert target.read_bytes() == _blob_bytes(repo, sha, relative)
            assert "only-5.txt" in extracted or sha != shas[-1]
            if sha == shas[0]:
                assert (snapshot.root / "only-1.txt").read_text(encoding="utf-8") == "only-1\n"
                assert not (snapshot.root / "only-5.txt").exists()


def test_dirty_uncommitted_file_never_appears_in_snapshots(tmp_path: Path) -> None:
    repo, shas = _five_commit_repo(tmp_path / "repo")
    write(repo, "dirty-uncommitted.txt", "should-not-extract\n")
    write(repo, "tracked.txt", "dirty-overwrite\n")
    series = select_first_parent_series(repo)
    assert series.head_sha == shas[-1]
    with SnapshotWorkspace(series) as workspace:
        head_root = workspace.snapshots[-1].root
        assert head_root is not None
        assert not (head_root / "dirty-uncommitted.txt").exists()
        assert (head_root / "tracked.txt").read_text(encoding="utf-8") == "state-5\n"


def test_worktree_index_and_status_unchanged_after_materialize(tmp_path: Path) -> None:
    repo, _shas = _five_commit_repo(tmp_path / "repo")
    dirty = write(repo, "local-only.txt", "keep-me\n")
    before = capture_worktree_fingerprint(repo)
    before_status = _git(repo, ["status", "--porcelain=v1"])
    before_head = _git(repo, ["rev-parse", "HEAD"]).strip()
    before_index = _git(repo, ["ls-files", "-s"])
    before_dirty = dirty.read_text(encoding="utf-8")
    series = select_first_parent_series(repo)
    with SnapshotWorkspace(series) as workspace:
        assert workspace.snapshots[-1].root is not None
    after = capture_worktree_fingerprint(repo)
    assert after == before
    assert _git(repo, ["status", "--porcelain=v1"]) == before_status
    assert _git(repo, ["rev-parse", "HEAD"]).strip() == before_head
    assert _git(repo, ["ls-files", "-s"]) == before_index
    assert dirty.read_text(encoding="utf-8") == before_dirty


def test_fewer_than_five_commits_keeps_missing_slots(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "short")
    write(repo, "a.txt", "one\n")
    first = commit_all(repo, "one")
    write(repo, "a.txt", "two\n")
    second = commit_all(repo, "two")
    series = select_first_parent_series(repo)
    assert len(series.slots) == SERIES_SLOT_COUNT
    assert [slot.available for slot in series.slots] == [False, False, False, True, True]
    assert [slot.sha for slot in series.slots] == [None, None, None, first, second]
    assert series.slots[-1].slot == 5
    assert series.slots[-1].sha == second == series.head_sha
    assert all(
        slot.unavailable_reason == SourceStateUnavailableReason.INSUFFICIENT_HISTORY.value
        for slot in series.slots[:3]
    )
    with SnapshotWorkspace(series) as workspace:
        assert workspace.snapshots[0].root is None
        assert workspace.snapshots[3].root is not None
        assert (workspace.snapshots[3].root / "a.txt").read_text(encoding="utf-8") == "one\n"
        assert (workspace.snapshots[4].root / "a.txt").read_text(encoding="utf-8") == "two\n"


def test_missing_git_marks_all_slots_unavailable(tmp_path: Path) -> None:
    root = tmp_path / "nogit"
    root.mkdir()
    (root / "file.txt").write_text("x\n", encoding="utf-8")
    series = select_first_parent_series(root)
    assert series.head_sha is None
    assert series.git_root is None
    assert all(not slot.available for slot in series.slots)
    assert all(
        slot.unavailable_reason == SourceStateUnavailableReason.MISSING_GIT.value
        for slot in series.slots
    )


def test_first_parent_series_excludes_merged_side_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "merge")
    write(repo, "base.txt", "base\n")
    _git(repo, ["add", "-A"])
    root = commit_all(repo, "root")
    write(repo, "main.txt", "main-1\n")
    main1 = commit_all(repo, "main-1")
    _git(repo, ["branch", "topic"])
    write(repo, "main.txt", "main-2\n")
    main2 = commit_all(repo, "main-2")
    _git(repo, ["checkout", "topic"])
    write(repo, "side-only.txt", "from-topic\n")
    side = commit_all(repo, "topic")
    _git(repo, ["checkout", "main"])
    _git(repo, ["merge", "--no-ff", "-m", "merge topic", "topic"])
    merge = _git(repo, ["rev-parse", "HEAD"]).strip()
    series = select_first_parent_series(repo)
    selected = [slot.sha for slot in series.slots if slot.sha]
    assert merge in selected
    assert side not in selected
    assert selected[-1] == merge
    assert root in selected and main1 in selected and main2 in selected
    with SnapshotWorkspace(series) as workspace:
        before_merge = next(
            snapshot for snapshot in workspace.snapshots if snapshot.slot.sha == main2
        )
        assert before_merge.root is not None
        assert not (before_merge.root / "side-only.txt").exists()


def test_escaping_symlink_skipped_relative_symlink_kept(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "links")
    write(repo, "target.txt", "inside\n")
    (repo / "safe-link").symlink_to("target.txt")
    (repo / "escape-link").symlink_to("../outside.txt")
    (tmp_path / "outside.txt").write_text("secret\n", encoding="utf-8")
    sha = commit_all(repo, "links")
    dest = tmp_path / "extracted"
    snapshot = materialize_commit_tree(repo, sha, dest)
    assert (dest / "safe-link").is_symlink()
    assert (dest / "safe-link").read_text(encoding="utf-8") == "inside\n"
    assert not (dest / "escape-link").exists()
    assert any(item.startswith("skipped_escaping_symlink:") for item in snapshot.limitations)
    assert (tmp_path / "outside.txt").read_text(encoding="utf-8") == "secret\n"


def test_submodule_gitlink_is_not_expanded(tmp_path: Path) -> None:
    other = init_repo(tmp_path / "other")
    write(other, "secret-module.py", "print('module')\n")
    other_sha = commit_all(other, "module")
    repo = init_repo(tmp_path / "super")
    write(repo, "app.py", "print('app')\n")
    commit_all(repo, "app")
    _git(
        repo,
        ["update-index", "--add", "--cacheinfo", f"160000,{other_sha},vendor/dep"],
    )
    _git(repo, ["commit", "-m", "add gitlink"])
    sha = _git(repo, ["rev-parse", "HEAD"]).strip()
    dest = tmp_path / "extracted-super"
    snapshot = materialize_commit_tree(repo, sha, dest)
    assert (dest / "app.py").read_text(encoding="utf-8") == "print('app')\n"
    assert not (dest / "vendor/dep/secret-module.py").exists()
    assert any(item.startswith("skipped_submodule:") for item in snapshot.limitations)
    assert "submodule_contents_not_materialized" in UNSUPPORTED_SOURCE_STATE_BEHAVIOR


def test_snapshot_workspace_cleans_up_on_success_and_failure(tmp_path: Path) -> None:
    repo, _shas = _five_commit_repo(tmp_path / "repo")
    series = select_first_parent_series(repo)
    kept: list[Path] = []
    with SnapshotWorkspace(series) as workspace:
        kept = [snapshot.root for snapshot in workspace.snapshots if snapshot.root]
        assert kept and all(path.exists() for path in kept)
    assert all(not path.exists() for path in kept)

    with patch(
        "codestrata.application.incremental.source_states.materialize_commit_tree",
        side_effect=RuntimeError("extract boom"),
    ):
        with pytest.raises(RuntimeError, match="extract boom"):
            with SnapshotWorkspace(series):
                pass


def test_materialize_never_uses_checkout_or_mutates_via_git(tmp_path: Path) -> None:
    repo, shas = _five_commit_repo(tmp_path / "repo")
    seen: list[list[str]] = []

    def track_text(arguments: list[str], **kwargs: object) -> str:
        seen.append(list(arguments))
        return run_readonly_git(arguments, **kwargs)  # type: ignore[arg-type]

    def track_bytes(arguments: list[str], **kwargs: object) -> bytes:
        seen.append(list(arguments))
        return run_readonly_git_bytes(arguments, **kwargs)  # type: ignore[arg-type]

    with (
        patch(
            "codestrata.application.incremental.source_states.run_readonly_git",
            side_effect=track_text,
        ),
        patch(
            "codestrata.application.incremental.source_states.run_readonly_git_bytes",
            side_effect=track_bytes,
        ),
    ):
        assert select_first_parent_series(repo).head_sha == shas[-1]
        materialize_commit_tree(repo, shas[-1], tmp_path / "one")
    verbs = {arguments[0] for arguments in seen if arguments}
    assert verbs <= {"rev-parse", "rev-list", "ls-tree", "cat-file"}
    assert "checkout" not in verbs
    assert "archive" not in verbs
    assert "submodule" not in verbs


def test_readonly_bytes_runner_refuses_checkout(tmp_path: Path) -> None:
    with pytest.raises(ReadOnlyGitError):
        run_readonly_git_bytes(["checkout", "HEAD"], cwd=tmp_path)


def test_subdirectory_request_keeps_containing_git_and_full_tree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "mono")
    write(repo, "target/src/app.js", "function app() { return 1; }\n")
    write(repo, "unrelated/secret.js", "function secret() { return 1; }\n")
    sha = commit_all(repo, "both trees")
    requested = repo / "target"
    series = select_first_parent_series(requested)
    assert series.git_root == repo.resolve()
    assert series.requested_root == requested.resolve()
    assert series.assessment_relpath == "target"
    assert series.head_sha == sha
    assert relative_assessment_path(repo, repo) == ""
    assert relative_assessment_path(requested, repo) == "target"
    with SnapshotWorkspace(series) as workspace:
        snapshot = workspace.snapshots[-1]
        assert snapshot.root is not None
        extracted = {
            path.relative_to(snapshot.root).as_posix()
            for path in snapshot.root.rglob("*")
            if path.is_file()
        }
        assert "target/src/app.js" in extracted
        assert "unrelated/secret.js" in extracted
        scoped = snapshot_assessment_root(snapshot.root, series.assessment_relpath)
        assert (scoped / "src/app.js").is_file()
        assert not (scoped / "unrelated").exists()
