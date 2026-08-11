"""Registry and CLI tests for the validation harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.models import RepositorySourceType, ValidationRepository
from validation.registry import (
    RegistryError,
    filter_repositories,
    load_all_repositories,
    load_repository_definition,
)
from validation.run_validation import main


def test_load_committed_local_fixture_definition() -> None:
    definitions = load_all_repositories()
    ids = [item.repository_id for item in definitions]
    assert len(ids) == len(set(ids))
    local = next(item for item in definitions if item.repository_id == "local-sample-js")
    assert local.source_type == RepositorySourceType.LOCAL
    assert not Path(local.local_path or "").is_absolute()


def test_filter_skips_remote_without_include_flag() -> None:
    local = ValidationRepository(
        repository_id="local-one",
        display_name="Local",
        source_type=RepositorySourceType.LOCAL,
        local_path="fixtures/a",
        expected_results_path="expectations/a.json",
        tags=("smoke",),
    )
    remote = ValidationRepository(
        repository_id="remote-one",
        display_name="Remote",
        source_type=RepositorySourceType.REMOTE,
        remote_url="https://github.com/example/repo.git",
        pinned_ref="v1.0.0",
        expected_results_path="expectations/b.json",
        tags=("remote",),
    )
    selected = filter_repositories((local, remote), include_remote=False)
    assert [item.repository_id for item in selected] == ["local-one"]
    selected_remote = filter_repositories((local, remote), include_remote=True)
    assert {item.repository_id for item in selected_remote} == {"local-one", "remote-one"}


def test_filter_unknown_repository_id() -> None:
    with pytest.raises(RegistryError, match="unknown"):
        filter_repositories((), repository_ids={"missing-repo"})


def test_cli_list_and_json_summary_local_only(tmp_path: Path) -> None:
    assert main(["--list"]) == 0
    code = main(
        [
            "--repository",
            "local-sample-js",
            "--local-only",
            "--json-summary",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0


def test_load_repository_definition_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "repo.toml"
    path.write_text(
        "\n".join(
            [
                'repository_id = "fixture-roundtrip"',
                'display_name = "Roundtrip"',
                'source_type = "local"',
                'local_path = "fixtures/x"',
                'expected_results_path = "expectations/x.json"',
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_repository_definition(path)
    assert loaded.repository_id == "fixture-roundtrip"
