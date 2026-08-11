"""Source-integrity checks for SV.10 — reuses SV.4 inventory comparison."""

from __future__ import annotations

from pathlib import Path

from verification.repository_assessment.workspace import (
    capture_inventory,
    compare_source_integrity,
)


def capture_source_inventory(repo_root: Path):
    return capture_inventory(repo_root)


def verify_source_integrity(before, after) -> tuple[bool, list[str]]:
    return compare_source_integrity(before, after)


def verify_checkout_unchanged(repo_root: Path, expected_sha: str) -> tuple[bool, str]:
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return False, "rev-parse failed"
    head = (proc.stdout or "").strip().lower()
    if head != expected_sha.lower():
        return False, f"checkout changed: expected {expected_sha} got {head}"
    return True, head
