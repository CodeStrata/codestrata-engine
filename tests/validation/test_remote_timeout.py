"""Validation-harness remote git timeout maps to skip, not product failure."""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.models import ValidationVerdict
from validation.registry import load_all_repositories
from validation.remote import RemoteRepositoryError, _run
from validation.runner import run_repository_validation


def test_network_git_timeout_raises_remote_unavailable() -> None:
    with pytest.raises(RemoteRepositoryError, match="timed out"):
        _run(["sleep", "30"], network_sensitive=True, timeout=1)


def test_clone_timeout_does_not_retry_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from validation.models import RepositorySourceType, ValidationRepository
    from validation.remote import prepare_remote_repository

    calls: list[list[str]] = []

    def _timeout(command: list[str], *, network_sensitive: bool = False, timeout=None):
        calls.append(list(command))
        raise RemoteRepositoryError(
            "command timed out after 90s: git clone. "
            "Network appears unavailable or the remote is unreachable."
        )

    monkeypatch.setattr("validation.remote._run", _timeout)
    definition = ValidationRepository(
        repository_id="remote-timeout-probe",
        display_name="Timeout probe",
        source_type=RepositorySourceType.REMOTE,
        remote_url="https://github.com/example/repo.git",
        pinned_ref="v1.0.0",
        expected_results_path="expectations/remote.json",
    )
    with pytest.raises(RemoteRepositoryError, match="timed out"):
        prepare_remote_repository(definition, clone_root=tmp_path)
    assert len(calls) == 1


def test_remote_timeout_skips_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remote = next(
        item
        for item in load_all_repositories()
        if item.repository_id == "remote-java-spring-petclinic"
    )

    def _timeout_clone(*_args, **_kwargs):
        raise RemoteRepositoryError(
            "command timed out after 90s: git clone. "
            "Network appears unavailable or the remote is unreachable."
        )

    monkeypatch.setattr(
        "validation.runner.prepare_remote_repository",
        _timeout_clone,
    )
    result = run_repository_validation(
        remote,
        output_root=tmp_path / "out",
        include_remote=True,
        local_only=False,
    )
    assert result.verdict == ValidationVerdict.SKIPPED
    assert result.skip_reason
    assert "remote unavailable" in result.skip_reason
    assert "timed out" in result.skip_reason
