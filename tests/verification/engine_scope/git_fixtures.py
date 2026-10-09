"""Tiny throwaway git repos for the scope guard.

``core.hooksPath=`` so the platform clone's identity hooks do not block fixture commits.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Scope Fixture",
            "-c",
            "user.email=scope-fixture@example.test",
            "-c",
            "core.hooksPath=",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {args} failed: {completed.stderr or completed.stdout}")
    return completed
