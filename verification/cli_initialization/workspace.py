"""Temporary repository fixtures for SV.3."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path


MINIMAL_SOURCE = """\
# minimal supported fixture for SV.3
def hello() -> str:
    return "codestrata"
"""


@dataclass
class WorkspaceSnapshot:
    """Digest map of files under a repository (relative paths)."""

    digests: dict[str, str] = field(default_factory=dict)
    modes: dict[str, int] = field(default_factory=dict)

    def digest_for(self, relative: str) -> str | None:
        return self.digests.get(relative)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_workspace(root: Path) -> WorkspaceSnapshot:
    digests: dict[str, str] = {}
    modes: dict[str, int] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digests[rel] = file_digest(path)
        modes[rel] = path.stat().st_mode & 0o777
    return WorkspaceSnapshot(digests=digests, modes=modes)


def compare_snapshots(
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
    *,
    allowed_new: set[str] | None = None,
) -> tuple[bool, list[str]]:
    """Return ok and failure messages for source-integrity checks."""

    allowed = allowed_new or set()
    failures: list[str] = []
    for rel, digest in before.digests.items():
        if rel not in after.digests:
            failures.append(f"deleted:{rel}")
            continue
        if after.digests[rel] != digest:
            failures.append(f"modified:{rel}")
        if after.modes.get(rel) != before.modes.get(rel):
            failures.append(f"mode_changed:{rel}")
    for rel in after.digests:
        if rel not in before.digests and rel not in allowed:
            failures.append(f"unexpected_new:{rel}")
    return (not failures), failures


def create_minimal_repository(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "src" / "hello.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(MINIMAL_SOURCE, encoding="utf-8")
    (root / "README.md").write_text("# SV.3 fixture\n", encoding="utf-8")
    return root


def create_empty_repository(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_space_path_repository(parent: Path) -> Path:
    root = parent / "repo with spaces"
    return create_minimal_repository(root)


def create_nested_repository(root: Path) -> tuple[Path, Path]:
    """Return (repo_root, nested_cwd)."""

    create_minimal_repository(root)
    nested = root / "pkg" / "deep"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "note.txt").write_text("nested\n", encoding="utf-8")
    return root, nested


def create_unrelated_files_repository(root: Path) -> Path:
    create_minimal_repository(root)
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "notes.txt").write_text("keep me\n", encoding="utf-8")
    return root


def create_unsupported_shape_repository(root: Path) -> Path:
    """Repository with only a non-source binary-like blob (init still scaffolds)."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "blob.bin").write_bytes(b"\x00\x01\x02\xffUNSUPPORTED")
    return root


def make_unwritable(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IXUSR)


def restore_writable(path: Path) -> None:
    path.chmod(stat.S_IRWXU)


def list_relative_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(path.relative_to(root).as_posix())
    return files


def ensure_no_codestrata_config(root: Path) -> bool:
    return not (root / "codestrata.toml").exists()
