"""E09.1 Git input resolver: working/staged/range/patch facts and untrusted PR context."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.incremental.git_inputs import (
    BoundarySpreadStatus,
    ComparisonCompleteness,
    FileChangeStatus,
    FileUnitClass,
    GitInputError,
    GitInputMode,
    GitInputRequest,
    resolve_git_inputs,
)
from codestrata.domain.contracts.enums import RevisionAgreement, SuppliedContextProvenance
from codestrata.domain.contracts.invocation import PR_TITLE_MAX, context_digest_for
from codestrata.infrastructure.knowledge_store.git_revision import observe_local_git_state
from codestrata.repository_auth.read_only_git import run_readonly_git
from tests.application.incremental.git_repo_helpers import commit_all, init_repo, write

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e09.1"


def _load_patch(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _context_payload(**overrides: object) -> dict[str, object]:
    fields = {
        "title": "local title",
        "description": "Local PR narrative. Not proof of behavior.",
        "base": None,
        "head": None,
        "labels": (),
        "linked_references": (),
        "provenance": SuppliedContextProvenance.LOCAL_FILE.value,
        "supplied_path": "./pr-context.json",
        "revision_agreement": RevisionAgreement.NOT_APPLICABLE.value,
        "conflict_reason": None,
        "narrative_only": True,
    }
    fields.update(overrides)
    payload = {
        "schema_name": "codestrata.supplied-pr-context.v1",
        "schema_version": "1.0.0",
        "title": fields["title"],
        "description": fields["description"],
        "base": fields["base"],
        "head": fields["head"],
        "labels": list(fields["labels"] or ()),
        "linked_references": list(fields["linked_references"] or ()),
        "provenance": fields["provenance"],
        "supplied_path": fields["supplied_path"],
        "context_digest": context_digest_for(**fields),
        "revision_agreement": fields["revision_agreement"],
        "conflict_reason": fields["conflict_reason"],
        "narrative_only": fields["narrative_only"],
        "enters_canonical_computation": False,
    }
    return payload


def test_staged_and_working_modes_differ(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print('base')\n")
    commit_all(repo, "base")
    write(repo, "src/app.py", "print('staged')\n")
    from tests.application.incremental.git_repo_helpers import _git

    _git(repo, ["add", "src/app.py"])
    write(repo, "src/app.py", "print('working')\n")
    write(repo, "src/unstaged.py", "print('only-working')\n")
    staged = resolve_git_inputs(GitInputRequest(repository_root=repo, mode=GitInputMode.STAGED))
    working = resolve_git_inputs(GitInputRequest(repository_root=repo, mode=GitInputMode.WORKING))
    assert {item.path for item in staged.files} == {"src/app.py"}
    assert {item.path for item in working.files} >= {"src/app.py", "src/unstaged.py"}
    assert staged.canonical_digest != working.canonical_digest
    assert staged.local_state.index_digest != staged.local_state.working_tree_digest
    assert staged.resolved_head == "INDEX"
    assert working.resolved_head == "WORKING_TREE"
    head = run_readonly_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).strip()
    assert head == "main"


def test_rename_add_delete_binary_and_test_touch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/legacy.py", "value = 1\n")
    write(repo, "src/gone.py", "gone = True\n")
    commit_all(repo, "base")
    from tests.application.incremental.git_repo_helpers import _git

    _git(repo, ["mv", "src/legacy.py", "src/renamed.py"])
    write(repo, "src/new.py", "added = True\n")
    (repo / "src/gone.py").unlink()
    write(repo, "assets/logo.bin", b"\x00\x01\x02\xff")
    write(repo, "tests/test_app.py", "def test_app():\n    assert True\n")
    commit_all(repo, "changes")
    base = run_readonly_git(["rev-parse", "HEAD~1"], cwd=repo).strip()
    head = run_readonly_git(["rev-parse", "HEAD"], cwd=repo).strip()
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=base,
            head=head,
            component_map={"src/renamed.py": "app", "src/new.py": "app"},
        )
    )
    statuses = {item.path: item.status for item in resolved.files}
    assert statuses.get("src/renamed.py") is FileChangeStatus.RENAMED
    assert statuses.get("src/new.py") is FileChangeStatus.ADDED
    assert statuses.get("src/gone.py") is FileChangeStatus.DELETED
    binary = next(item for item in resolved.files if item.path.endswith("logo.bin"))
    assert binary.binary is True
    assert resolved.comparison_completeness is ComparisonCompleteness.PARTIAL_BINARY
    assert resolved.change_summary.test_touch is True
    assert resolved.change_summary.unmapped_changed_file_count >= 1
    assert resolved.change_summary.boundary_spread_status is BoundarySpreadStatus.UNKNOWN
    assert resolved.change_summary.boundary_spread_count is None


def test_shallow_history_and_submodule_are_explicit(tmp_path: Path) -> None:
    source = init_repo(tmp_path / "source")
    write(source, "src/app.py", "print(1)\n")
    commit_all(source, "one")
    write(source, "src/app.py", "print(2)\n")
    commit_all(source, "two")
    shallow = tmp_path / "shallow"
    from tests.application.incremental.git_repo_helpers import _git

    _git(tmp_path, ["clone", "--no-local", "--depth", "1", str(source), str(shallow)])
    state = observe_local_git_state(shallow)
    assert state.shallow is True
    assert "shallow_history" in state.limitations
    assert state.observed_commit_count == 1

    nested = init_repo(tmp_path / "nested")
    write(nested, "lib.py", "x = 1\n")
    nested_sha = commit_all(nested, "lib")
    host = init_repo(tmp_path / "host")
    write(host, "src/app.py", "print(1)\n")
    write(
        host,
        ".gitmodules",
        '[submodule "vendor/lib"]\n\tpath = vendor/lib\n\turl = ./nested\n',
    )
    commit_all(host, "host")
    _git(
        host,
        ["update-index", "--add", "--cacheinfo", "160000", nested_sha, "vendor/lib"],
    )
    host_state = observe_local_git_state(host)
    assert "vendor/lib" in host_state.submodule_paths
    assert "submodules_present" in host_state.limitations
    assert run_readonly_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=host).strip() == "main"


def test_missing_base_does_not_fetch_or_switch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    missing = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with patch("codestrata.application.incremental.git_inputs.run_readonly_git") as mocked:
        mocked.side_effect = AssertionError("diff must not run when base is missing")
        resolved = resolve_git_inputs(
            GitInputRequest(
                repository_root=repo,
                mode=GitInputMode.RANGE,
                base=missing,
                head="HEAD",
            )
        )
    assert "missing_base" in resolved.limitations
    assert resolved.full_comparison is False
    assert run_readonly_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).strip() == "main"


def test_supplied_patch_missing_base_is_hunk_facts_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "README.md", "ok\n")
    commit_all(repo, "seed")
    expected = json.loads((FIXTURE_DIR / "expected-missing-base.json").read_text(encoding="utf-8"))
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("missing-base.patch"),
        )
    )
    assert resolved.full_comparison is False
    assert resolved.comparison_completeness is ComparisonCompleteness.PARTIAL_NO_BASE
    assert "no_fabricated_full_comparison" in resolved.limitations
    fact = resolved.files[0]
    assert fact.path == expected["path"]
    assert fact.status.value == expected["status"]
    assert fact.added_lines == expected["added_lines"]
    assert fact.deleted_lines == expected["deleted_lines"]
    assert fact.binary is expected["binary"]
    assert resolved.hunks
    rename = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("rename.patch"),
        )
    )
    assert rename.files[0].status is FileChangeStatus.RENAMED
    binary = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("binary.patch"),
        )
    )
    assert binary.files[0].binary is True
    add_delete = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("add-delete.patch"),
        )
    )
    statuses = {item.path: item.status for item in add_delete.files}
    assert statuses["src/new.py"] is FileChangeStatus.ADDED
    assert statuses["src/gone.py"] is FileChangeStatus.DELETED
    test_only = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("test-only.patch"),
        )
    )
    assert test_only.change_summary.test_touch is True
    assert any(item.unit_class is FileUnitClass.CONFIG_TEST for item in test_only.files)


def test_malformed_patch_and_absent_pr_metadata(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    malformed = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.PATCH,
            patch_text=_load_patch("malformed.patch"),
        )
    )
    assert "malformed_patch" in malformed.limitations
    absent = resolve_git_inputs(GitInputRequest(repository_root=repo, mode=GitInputMode.WORKING))
    assert absent.supplied_context is None
    assert absent.anonymous_telemetry["supplied_context_present"] is False


def test_oversized_and_malformed_pr_metadata_rejected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    oversized = _context_payload(title="x" * (PR_TITLE_MAX + 1))
    with pytest.raises(GitInputError, match="malformed supplied PR context"):
        resolve_git_inputs(
            GitInputRequest(
                repository_root=repo,
                mode=GitInputMode.WORKING,
                supplied_context=oversized,
            )
        )
    with pytest.raises(GitInputError, match="malformed supplied PR context"):
        resolve_git_inputs(
            GitInputRequest(
                repository_root=repo,
                mode=GitInputMode.WORKING,
                supplied_context={"not": "a context"},
            )
        )


def test_injection_escaped_and_excluded_from_telemetry(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    head = commit_all(repo, "base")
    payload = _context_payload(
        title='<script>alert("x")</script>',
        description="click <img src=x onerror=alert(1)>",
        labels=("<b>bold</b>",),
        head=head,
        base=head,
        revision_agreement=RevisionAgreement.AGREES.value,
    )
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.WORKING,
            supplied_context=payload,
        )
    )
    projection = resolved.escaped_projection["supplied_context"]
    assert "<script>" not in projection["title"]
    assert "&lt;script&gt;" in projection["title"]
    assert "<img" not in projection["description"]
    telemetry = json.dumps(resolved.anonymous_telemetry)
    assert "<script>" not in telemetry
    assert "alert" not in telemetry
    assert "local title" not in telemetry
    assert resolved.anonymous_telemetry["supplied_context_present"] is True
    assert "title" not in resolved.anonymous_telemetry


def test_sha_conflict_visible_and_context_only_does_not_change_canonical(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    head = commit_all(repo, "base")
    agreeing = _context_payload(
        title="one",
        head=head,
        base=head,
        revision_agreement=RevisionAgreement.AGREES.value,
    )
    other_narrative = _context_payload(
        title="two",
        head=head,
        base=head,
        revision_agreement=RevisionAgreement.AGREES.value,
    )
    first = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.WORKING,
            supplied_context=agreeing,
        )
    )
    second = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.WORKING,
            supplied_context=other_narrative,
        )
    )
    assert first.canonical_digest == second.canonical_digest
    assert first.change_summary.changed_file_count == second.change_summary.changed_file_count
    conflict = _context_payload(
        title="one",
        head="ffffffffffffffffffffffffffffffffffffffff",
        base=head,
        revision_agreement=RevisionAgreement.AGREES.value,
    )
    conflicting = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.WORKING,
            supplied_context=conflict,
        )
    )
    assert conflicting.supplied_context is not None
    assert conflicting.supplied_context.observed_agreement is RevisionAgreement.CONFLICT
    assert "supplied_context_revision_conflict" in conflicting.limitations


def test_declared_boundary_membership_is_not_inferred(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    write(repo, "src/app.py", "print(2)\n")
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.WORKING,
            component_map={"src/app.py": "app"},
            boundary_membership={"src/app.py": ("layer:application",)},
            boundary_dimension="layers",
        )
    )
    assert resolved.change_summary.boundary_spread_status is BoundarySpreadStatus.OBSERVED
    assert resolved.change_summary.boundary_spread_count == 1
    assert resolved.change_summary.changed_component_ids == ("app",)
    unknown = resolve_git_inputs(
        GitInputRequest(repository_root=repo, mode=GitInputMode.WORKING)
    )
    assert unknown.change_summary.boundary_spread_status is BoundarySpreadStatus.UNKNOWN
    assert unknown.change_summary.boundary_spread_count is None


def test_series_range_pairs_do_not_include_future_commits(tmp_path: Path) -> None:
    from tests.application.incremental.test_r2_p06_trend_series import (
        LATER_PATH,
        _five_commit_adversarial,
    )

    repo, shas = _five_commit_adversarial(tmp_path / "repo")

    def _paths(base: str, head: str) -> set[str]:
        resolved = resolve_git_inputs(
            GitInputRequest(
                repository_root=repo,
                mode=GitInputMode.RANGE,
                base=base,
                head=head,
            )
        )
        assert resolved.resolved_base == base
        assert resolved.resolved_head == head
        return {item.path for item in resolved.files}

    s12 = _paths(shas[0], shas[1])
    s45 = _paths(shas[3], shas[4])
    s15 = _paths(shas[0], shas[4])
    assert s12 == {"src/app.js"}
    assert LATER_PATH not in s12
    assert "src/pair.js" not in s12
    assert LATER_PATH in s45
    assert "src/pair.js" not in s45
    assert LATER_PATH in s15
    assert "src/pair.js" in s15
    missing = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            head=shas[1],
        )
    )
    assert missing.comparison_completeness is ComparisonCompleteness.PARTIAL_NO_BASE
    assert missing.full_comparison is False
