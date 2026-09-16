"""Scope-guard fixtures: in-scope, negative, partial, unsupported, budget."""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.verification.gitutil import git
from verification.git_changes import PathEvent, parse_name_status_z
from verification.inventory import InventoryEntry, WorkingTreeInventory
from verification.paths import is_under_engine
from verification.scope_guard import evaluate_events, evaluate_repository

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "scope_cases.yaml"


def expected_status(case_id: str) -> str:
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    for case in raw["cases"]:
        if case["id"] == case_id:
            return str(case["expect"])
    raise AssertionError(f"missing independent expected fixture for {case_id}")


def test_fixture_file_declares_negative_and_budget_cases() -> None:
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    ids = {case["id"] for case in raw["cases"]}
    assert "root_script_edit" in ids
    assert "budget_exceeded" in ids
    assert "not_a_git_repo" in ids


def test_engine_only_modify_passes(git_repo: Path) -> None:
    (git_repo / "engine" / "ok.md").write_text("updated\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("engine_only_modify")
    assert verdict.findings == ()


def test_untracked_engine_file_passes(git_repo: Path) -> None:
    (git_repo / "engine" / "new.md").write_text("new\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == "PASS"


def test_root_script_edit_fails(git_repo: Path) -> None:
    scripts = git_repo / "scripts"
    scripts.mkdir()
    (scripts / "publish.sh").write_text("echo publish\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("root_script_edit")
    assert any(finding.event.path.endswith("scripts/publish.sh") for finding in verdict.findings)


def test_workflow_and_lockfile_and_export_manifest_fail(git_repo: Path) -> None:
    workflow = git_repo / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (git_repo / "uv.lock").write_text("# lock\n", encoding="utf-8")
    (git_repo / "public-export-manifest.yaml").write_text("exports: []\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    paths = {finding.event.path for finding in verdict.findings}
    assert any(path.endswith(".github/workflows/ci.yml") for path in paths)
    assert "uv.lock" in paths
    assert "public-export-manifest.yaml" in paths
    assert verdict.status == "FAIL"


def test_root_deletion_fails(git_repo: Path) -> None:
    (git_repo / "README.md").unlink()
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("root_delete")
    assert any(finding.event.status == "deleted" for finding in verdict.findings)


def test_rename_engine_to_root_fails(git_repo: Path) -> None:
    git(git_repo, "mv", "engine/ok.md", "leaked.md")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("rename_out")
    assert any(finding.event.status == "renamed" for finding in verdict.findings)


def test_rename_root_into_engine_fails(git_repo: Path) -> None:
    git(git_repo, "mv", "README.md", "engine/README.md")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("rename_into_engine_from_root")


def test_staged_and_unstaged_root_edits_are_both_inspected(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text("[project]\nname='changed'\n", encoding="utf-8")
    git(git_repo, "add", "pyproject.toml")
    (git_repo / "README.md").write_text("unstaged\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    origins = {finding.event.origin for finding in verdict.findings}
    paths = {finding.event.path for finding in verdict.findings}
    assert "staged" in origins
    assert "unstaged" in origins
    assert "pyproject.toml" in paths
    assert "README.md" in paths


def test_partial_engine_and_root_fails_only_out_of_scope(git_repo: Path) -> None:
    (git_repo / "engine" / "ok.md").write_text("engine change\n", encoding="utf-8")
    (git_repo / "README.md").write_text("root change\n", encoding="utf-8")
    verdict = evaluate_repository(git_repo, base_ref="release/engine-next")
    assert verdict.status == expected_status("partial_engine_and_root")
    assert all(not is_under_engine(finding.event.path) for finding in verdict.findings)
    assert any(finding.event.path == "README.md" for finding in verdict.findings)


def test_preexisting_inventory_does_not_reset_unrelated_root_dirty(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("already dirty before this story\n", encoding="utf-8")
    inventory = WorkingTreeInventory(
        recorded_at="2026-09-16",
        checkout_sha="unused",
        branch="engine/story",
        entries=(InventoryEntry(status="M", path="README.md"),),
    )
    from verification.git_changes import collect_events

    events = collect_events(git_repo, "release/engine-next")
    verdict = evaluate_events(events, inventory=inventory)
    assert verdict.status == expected_status("preexisting_root_dirty_ignored")
    assert verdict.preexisting_ignored


def test_not_a_git_repo_is_error_not_pass(tmp_path: Path) -> None:
    verdict = evaluate_repository(tmp_path / "missing")
    assert verdict.status == expected_status("not_a_git_repo")
    assert not verdict.ok


def test_budget_failure_is_not_truncated_pass() -> None:
    events = tuple(
        PathEvent(origin="unstaged", status="modified", path=f"engine/f{index}.md")
        for index in range(5)
    )
    verdict = evaluate_events(events, max_events=2)
    assert verdict.status == expected_status("budget_exceeded")
    assert "exceeding budget" in verdict.message


def test_parse_rename_name_status_z() -> None:
    payload = b"R100\0src/old.py\0src/new.py\0"
    parsed = parse_name_status_z(payload)
    assert parsed == (("R100", "src/new.py", "src/old.py"),)


def test_path_escape_is_out_of_scope() -> None:
    events = (
        PathEvent(origin="untracked", status="untracked", path="../secret"),
    )
    verdict = evaluate_events(events)
    assert verdict.status == "FAIL"
