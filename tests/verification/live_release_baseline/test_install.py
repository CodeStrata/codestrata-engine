"""Install/rollback of hashed live artifacts; hash mismatch is FAIL."""

from __future__ import annotations

import pytest
from verification.live_release_baseline.install import (
    hashed_install_argv,
    hashed_requirements_line,
    interpret_rollback,
)
from verification.live_release_baseline.models import CheckStatus, DistributedFile, InstallAttempt

WHEEL = DistributedFile(
    filename="codestrata-9.9.9-py3-none-any.whl",
    packagetype="bdist_wheel",
    sha256="ab" * 32,
    size=10,
    url="https://example.test/codestrata-9.9.9-py3-none-any.whl",
)


def _attempt(
    *,
    exit_code: int = 0,
    version: str | None = "9.9.9",
    digest: str | None = "ab" * 32,
) -> InstallAttempt:
    return InstallAttempt(
        argv=("python", "-m", "pip", "install"),
        exit_code=exit_code,
        stdout="",
        stderr="",
        installed_version=version,
        observed_sha256=digest,
    )


def test_hash_pin_uses_require_hashes_file() -> None:
    argv = hashed_install_argv(WHEEL)
    assert "--require-hashes" in argv
    assert "-r" in argv
    line = hashed_requirements_line(WHEEL)
    assert line.startswith(WHEEL.url)
    assert WHEEL.sha256 in line
    assert "0.2.1" not in line


def test_missing_digest_cannot_build_an_install_plan() -> None:
    broken = DistributedFile(
        filename="x.whl",
        packagetype="bdist_wheel",
        sha256="",
        size=1,
        url="https://example.test/x.whl",
    )
    with pytest.raises(ValueError, match="sha256"):
        hashed_install_argv(broken)


def test_successful_install_uninstall_reinstall() -> None:
    evidence = interpret_rollback(
        install=_attempt(),
        uninstall=_attempt(version=None, digest=None),
        reinstall=_attempt(),
        expected_version="9.9.9",
        expected_sha256="ab" * 32,
    )
    assert evidence.status is CheckStatus.PASS


def test_digest_mismatch_is_fail() -> None:
    evidence = interpret_rollback(
        install=_attempt(digest="00" * 32),
        uninstall=_attempt(version=None, digest=None),
        reinstall=_attempt(),
        expected_version="9.9.9",
        expected_sha256="ab" * 32,
    )
    assert evidence.status is CheckStatus.FAIL
    assert any("digest" in note for note in evidence.notes)


def test_version_mismatch_is_not_relabeled_from_pyproject() -> None:
    evidence = interpret_rollback(
        install=_attempt(version="0.2.1"),
        uninstall=_attempt(version=None, digest=None),
        reinstall=_attempt(),
        expected_version="9.9.9",
        expected_sha256="ab" * 32,
    )
    assert evidence.status is CheckStatus.FAIL


def test_missing_expected_live_identity_is_blocked() -> None:
    evidence = interpret_rollback(
        install=_attempt(),
        uninstall=_attempt(),
        reinstall=_attempt(),
        expected_version="",
        expected_sha256="",
    )
    assert evidence.status is CheckStatus.BLOCKED


def test_nonzero_install_exit_is_fail() -> None:
    evidence = interpret_rollback(
        install=_attempt(exit_code=1),
        uninstall=_attempt(version=None, digest=None),
        reinstall=_attempt(),
        expected_version="9.9.9",
        expected_sha256="ab" * 32,
    )
    assert evidence.status is CheckStatus.FAIL
