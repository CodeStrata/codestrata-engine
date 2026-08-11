"""Workspace fixtures and source-integrity inventory for SV.4."""

from __future__ import annotations

import hashlib
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

# Approved CodeStrata mutations relative to assessed repository root.
APPROVED_CONFIG = "codestrata.toml"
APPROVED_OUTPUT_PREFIXES = ("reports/", ".codestrata/")

IGNORE_PREFIXES = (".git/",)


@dataclass
class SourceInventory:
    digests: dict[str, str] = field(default_factory=dict)
    modes: dict[str, int] = field(default_factory=dict)

    def relative_paths(self) -> set[str]:
        return set(self.digests)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _should_ignore(rel: str) -> bool:
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in IGNORE_PREFIXES)


def capture_inventory(root: Path) -> SourceInventory:
    digests: dict[str, str] = {}
    modes: dict[str, int] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _should_ignore(rel):
            continue
        digests[rel] = file_digest(path)
        modes[rel] = path.stat().st_mode & 0o777
    return SourceInventory(digests=digests, modes=modes)


def _is_approved_mutation(rel: str) -> bool:
    # Init may write codestrata.toml at repo root or nested cwd (no root discovery).
    if rel == APPROVED_CONFIG or rel.endswith("/codestrata.toml"):
        return True
    if any(rel.startswith(prefix) for prefix in APPROVED_OUTPUT_PREFIXES):
        return True
    parts = rel.split("/")
    # Documented CodeStrata knowledge/cache directory at any cwd depth.
    if ".codestrata" in parts:
        return True
    # Configured output trees (default reports/).
    if "reports" in parts:
        return True
    return False


def compare_source_integrity(
    before: SourceInventory,
    after: SourceInventory,
) -> tuple[bool, list[str]]:
    """Compare inventories; CodeStrata config/output paths are classified separately."""

    failures: list[str] = []
    for rel, digest in before.digests.items():
        if _is_approved_mutation(rel):
            continue
        if rel not in after.digests:
            failures.append(f"deleted:{rel}")
            continue
        if after.digests[rel] != digest:
            failures.append(f"modified:{rel}")
        if after.modes.get(rel) != before.modes.get(rel):
            failures.append(f"mode_changed:{rel}")
    for rel in after.digests:
        if rel in before.digests:
            continue
        if _is_approved_mutation(rel):
            continue
        failures.append(f"unexpected_new:{rel}")
    return (not failures), failures


def assert_outside_codestrata_tree(path: Path, codestrata_root: Path) -> None:
    resolved = path.resolve()
    root = codestrata_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise ValueError("clone/workspace must remain outside the CodeStrata source tree")


def copy_fixture(source: Path, destination: Path) -> Path:
    """Copy an existing controlled fixture into a temporary workspace."""

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def create_empty_repository(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# empty fixture\n", encoding="utf-8")
    return root


def create_minimal_python_repository(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    src = root / "src" / "hello.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("def hello() -> str:\n    return 'ok'\n", encoding="utf-8")
    (root / "README.md").write_text("# minimal\n", encoding="utf-8")
    return root


def create_unsupported_repository(root: Path) -> Path:
    """Repository with no recognizable language/build signals."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.txt").write_text("plain text only\n", encoding="utf-8")
    return root


def create_space_path_repository(parent: Path, fixture_source: Path | None = None) -> Path:
    root = parent / "repo with spaces"
    if fixture_source is not None and fixture_source.is_dir():
        return copy_fixture(fixture_source, root)
    return create_minimal_python_repository(root)


def create_nested_layout(root: Path) -> tuple[Path, Path]:
    create_minimal_python_repository(root)
    nested = root / "pkg" / "deep"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "note.txt").write_text("nested\n", encoding="utf-8")
    return root, nested


def resolve_local_fixture(repo_root: Path, relative: str) -> Path:
    """Resolve fixture from monorepo or engine-adjacent locations."""

    candidates = [
        repo_root / relative,
        repo_root.parent / relative,
        repo_root / ".." / relative,
    ]
    for path in candidates:
        resolved = path.resolve()
        if resolved.is_dir():
            return resolved
    raise FileNotFoundError(f"local fixture not found: {relative}")


def make_unwritable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
