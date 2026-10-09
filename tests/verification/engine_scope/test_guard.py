"""Scope-guard behavior: Engine-only PASS, outside-Engine FAIL, inventory, renames."""

from __future__ import annotations

from pathlib import Path

from tests.verification.engine_scope.git_fixtures import run_git
from verification.engine_scope.git_changes import (
    collect_cumulative,
    collect_working_tree,
    parse_name_status_z,
    parse_porcelain_v1,
)
from verification.engine_scope.guard import evaluate_scope
from verification.engine_scope.inventory import dump_inventory, in_inventory, write_inventory
from verification.engine_scope.models import ChangeKind, ChangeOrigin, InventoryEntry
from verification.engine_scope.paths import is_engine_owned


def test_engine_only_edit_passes(git_repo: Path) -> None:
    target = git_repo / "engine" / "ok.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert report.ok
    assert report.violations == ()
    assert any(change.path == "engine/ok.py" for change in report.changes)


def test_root_script_edit_fails(git_repo: Path) -> None:
    script = git_repo / "scripts" / "release.sh"
    script.write_text("echo leaked\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert not report.ok
    assert any("scripts/" in item.reason for item in report.violations)


def test_workflow_edit_fails(git_repo: Path) -> None:
    workflow = git_repo / ".github" / "workflows" / "ci.yml"
    workflow.write_text("name: publish\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert not report.ok
    assert any(".github/workflows/" in (item.named_surface or "") for item in report.violations)


def test_lockfile_and_export_manifest_edits_fail(git_repo: Path) -> None:
    (git_repo / "package-lock.json").write_text('{"lock": true}\n', encoding="utf-8")
    (git_repo / "public-export-manifest.yaml").write_text("version: 2\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    surfaces = {item.named_surface for item in report.violations}
    assert "package-lock.json" in surfaces
    assert "public-export-manifest.yaml" in surfaces


def test_deletion_outside_engine_fails(git_repo: Path) -> None:
    (git_repo / "scripts" / "release.sh").unlink()
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert not report.ok
    assert any(item.change.kind is ChangeKind.DELETED for item in report.violations)


def test_rename_engine_to_root_fails_on_source_and_destination(git_repo: Path) -> None:
    # Moving out of engine/ is a violation even if the destination is new.
    src = git_repo / "engine" / "README.md"
    dest = git_repo / "scripts" / "README.md"
    run_git(git_repo, "mv", str(src), str(dest))
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert not report.ok
    assert any(item.change.kind is ChangeKind.RENAMED for item in report.violations)
    assert any(
        item.change.old_path == "engine/README.md" and item.change.path == "scripts/README.md"
        for item in report.violations
    )


def test_rename_inside_engine_passes(git_repo: Path) -> None:
    src = git_repo / "engine" / "README.md"
    dest = git_repo / "engine" / "README.txt"
    run_git(git_repo, "mv", str(src), str(dest))
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert report.ok
    assert any(change.kind is ChangeKind.RENAMED for change in report.changes)


def test_untracked_outside_engine_fails(git_repo: Path) -> None:
    (git_repo / "root-secret.env").write_text("nope\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert not report.ok
    assert any(item.change.kind is ChangeKind.UNTRACKED for item in report.violations)


def test_preexisting_inventory_is_grandfathered_without_reset(git_repo: Path) -> None:
    # Unrelated dirty files listed in the start inventory must still exist after the check.
    leaked = git_repo / "platform-local.txt"
    leaked.write_text("unrelated\n", encoding="utf-8")
    inventory = (InventoryEntry(path="platform-local.txt", kind=ChangeKind.UNTRACKED),)
    before = leaked.read_text(encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD", inventory=inventory)
    assert report.ok
    assert any(change.path == "platform-local.txt" for change in report.grandfathered)
    assert leaked.read_text(encoding="utf-8") == before
    assert leaked.exists()


def test_new_untracked_outside_is_not_covered_by_unrelated_inventory(git_repo: Path) -> None:
    inventory = (InventoryEntry(path="other.txt", kind=ChangeKind.UNTRACKED),)
    (git_repo / "fresh-outside.py").write_text("x\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD", inventory=inventory)
    assert not report.ok


def test_staged_and_unstaged_engine_edits_are_both_inspected(git_repo: Path) -> None:
    staged = git_repo / "engine" / "staged.py"
    staged.write_text("staged\n", encoding="utf-8")
    run_git(git_repo, "add", "engine/staged.py")
    unstaged = git_repo / "engine" / "unstaged.py"
    unstaged.write_text("unstaged\n", encoding="utf-8")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    paths = {change.path for change in report.changes}
    assert "engine/staged.py" in paths
    assert "engine/unstaged.py" in paths
    assert report.ok


def test_committed_cumulative_diff_rejects_outside_engine(git_repo: Path) -> None:
    (git_repo / "scripts" / "release.sh").write_text("echo committed\n", encoding="utf-8")
    run_git(git_repo, "add", "scripts/release.sh")
    run_git(git_repo, "commit", "-m", "break scope")
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD~1")
    assert not report.ok
    assert any(item.change.origin is ChangeOrigin.CUMULATIVE for item in report.violations)


def test_committed_outside_change_is_not_grandfathered(git_repo: Path) -> None:
    # Once the leak is committed, inventory cannot hide it from the cumulative diff.
    (git_repo / "scripts" / "release.sh").write_text("echo committed\n", encoding="utf-8")
    run_git(git_repo, "add", "scripts/release.sh")
    run_git(git_repo, "commit", "-m", "break scope")
    inventory = (InventoryEntry(path="scripts/release.sh", kind=ChangeKind.MODIFIED),)
    report = evaluate_scope(
        repo_root=git_repo,
        baseline_ref="HEAD~1",
        inventory=inventory,
    )
    assert not report.ok


def test_inventory_roundtrip(tmp_path: Path) -> None:
    entries = (
        InventoryEntry(path="scripts/x.sh", kind=ChangeKind.MODIFIED, old_path=None, status=" U"),
    )
    path = tmp_path / "inventory.json"
    write_inventory(path, dump_inventory(entries, baseline_ref="origin/main"))
    loaded = dump_inventory(entries)
    assert loaded["schema"].endswith("v1")
    assert in_inventory(entries, "scripts/x.sh", None)


def test_porcelain_rename_parses_source_and_destination() -> None:
    payload = "R  engine/a.py -> scripts/a.py\n"
    changes = parse_porcelain_v1(payload)
    assert len(changes) == 1
    assert changes[0].old_path == "engine/a.py"
    assert changes[0].path == "scripts/a.py"
    assert changes[0].kind is ChangeKind.RENAMED
    assert not is_engine_owned(changes[0].path)


def test_name_status_z_rename_and_delete() -> None:
    payload = "R100\0engine/old.py\0engine/new.py\0D\0scripts/gone.sh\0"
    changes = parse_name_status_z(payload, ChangeOrigin.CUMULATIVE)
    kinds = {item.kind: item for item in changes}
    assert kinds[ChangeKind.RENAMED].old_path == "engine/old.py"
    assert kinds[ChangeKind.RENAMED].path == "engine/new.py"
    assert kinds[ChangeKind.DELETED].path == "scripts/gone.sh"


def test_missing_git_repo_is_fail_not_pass(tmp_path: Path) -> None:
    report = evaluate_scope(repo_root=tmp_path, baseline_ref="HEAD")
    assert not report.ok
    assert report.violations


def test_collect_working_tree_sees_untracked(git_repo: Path) -> None:
    (git_repo / "engine" / "new.txt").write_text("n\n", encoding="utf-8")
    changes = collect_working_tree(git_repo)
    assert any(change.path == "engine/new.txt" for change in changes)
    assert collect_cumulative(git_repo, "HEAD") is not None


def test_unsupported_partial_inventory_path(git_repo: Path) -> None:
    (git_repo / "engine" / "ok.py").write_text("ok\n", encoding="utf-8")
    bogus = (InventoryEntry(path="", kind=ChangeKind.UNKNOWN),)
    # Empty path cannot match a real change; engine edit still passes.
    matched = in_inventory(bogus, "engine/ok.py", None)
    assert matched is False
    report = evaluate_scope(repo_root=git_repo, baseline_ref="HEAD")
    assert report.ok
