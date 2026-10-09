"""Helpers to build throwaway Git repositories for E09.1 and E09.2 tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, ["init", "-b", "main"])
    _git(path, ["config", "user.email", "dev@example.test"])
    _git(path, ["config", "user.name", "Dev Example"])
    _git(path, ["config", "commit.gpgsign", "false"])
    _git(path, ["config", "core.autocrlf", "false"])
    return path


def write(repo: Path, relative: str, content: str | bytes) -> Path:
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8", newline="\n")
    return target


def commit_all(repo: Path, message: str) -> str:
    _git(repo, ["add", "-A"])
    _git(repo, ["commit", "-m", message])
    return _git(repo, ["rev-parse", "HEAD"]).strip()


def commit_dated(
    repo: Path,
    message: str,
    *,
    unix: int,
    author_name: str = "Dev Example",
    author_email: str = "dev@example.test",
    committer_name: str | None = None,
    committer_email: str | None = None,
) -> str:
    _git(repo, ["add", "-A"])
    stamp = f"{unix} +0000"
    env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_NAME": committer_name or author_name,
        "GIT_COMMITTER_EMAIL": committer_email or author_email,
        "GIT_COMMITTER_DATE": stamp,
    }
    _git(repo, ["commit", "-m", message], env=env)
    return _git(repo, ["rev-parse", "HEAD"]).strip()


def _git(repo: Path, arguments: list[str], env: dict[str, str] | None = None) -> str:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=merged,
    )
    return result.stdout or ""
