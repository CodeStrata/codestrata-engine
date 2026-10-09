"""Install and rollback plans for the *published* Engine artifact."""

from __future__ import annotations

from verification.live_release_baseline.models import (
    CheckStatus,
    DistributedFile,
    InstallAttempt,
    InstallRollbackEvidence,
)


def hashed_install_argv(
    wheel: DistributedFile,
    *,
    requirements_path: str = "pypi-live.hashes.txt",
) -> tuple[str, ...]:
    if not wheel.sha256 or not wheel.url:
        raise ValueError("wheel is missing url or sha256; cannot pin an install")
    return (
        "python",
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--require-hashes",
        "-r",
        requirements_path,
    )


def hashed_requirements_line(wheel: DistributedFile) -> str:
    if not wheel.sha256 or not wheel.url:
        raise ValueError("wheel is missing url or sha256")
    return f"{wheel.url} --hash=sha256:{wheel.sha256}"


def interpret_rollback(
    *,
    install: InstallAttempt,
    uninstall: InstallAttempt,
    reinstall: InstallAttempt,
    expected_version: str,
    expected_sha256: str,
) -> InstallRollbackEvidence:
    notes: list[str] = []
    if not expected_version or not expected_sha256:
        return InstallRollbackEvidence(
            install=install,
            uninstall=uninstall,
            reinstall=reinstall,
            status=CheckStatus.BLOCKED,
            notes=("expected live version/digest missing; refusing pyproject fallback",),
        )
    for name, attempt in (("install", install), ("reinstall", reinstall)):
        if attempt.exit_code != 0:
            notes.append(f"{name} exited {attempt.exit_code}")
            return InstallRollbackEvidence(
                install=install,
                uninstall=uninstall,
                reinstall=reinstall,
                status=CheckStatus.FAIL,
                notes=tuple(notes),
            )
        if attempt.installed_version != expected_version:
            notes.append(
                f"{name} version {attempt.installed_version!r} != live {expected_version!r}"
            )
            return InstallRollbackEvidence(
                install=install,
                uninstall=uninstall,
                reinstall=reinstall,
                status=CheckStatus.FAIL,
                notes=tuple(notes),
            )
        if attempt.observed_sha256 and attempt.observed_sha256 != expected_sha256:
            notes.append(f"{name} digest mismatch")
            return InstallRollbackEvidence(
                install=install,
                uninstall=uninstall,
                reinstall=reinstall,
                status=CheckStatus.FAIL,
                notes=tuple(notes),
            )
    if uninstall.exit_code != 0:
        notes.append(f"uninstall exited {uninstall.exit_code}")
        return InstallRollbackEvidence(
            install=install,
            uninstall=uninstall,
            reinstall=reinstall,
            status=CheckStatus.FAIL,
            notes=tuple(notes),
        )
    notes.append(
        "Installed the hashed live wheel, uninstalled it, and reinstalled the same digest "
        "in an isolated venv (not the story working tree)."
    )
    return InstallRollbackEvidence(
        install=install,
        uninstall=uninstall,
        reinstall=reinstall,
        status=CheckStatus.PASS,
        notes=tuple(notes),
    )
