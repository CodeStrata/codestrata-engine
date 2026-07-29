"""Safe repository filesystem traversal helpers."""

from __future__ import annotations

from pathlib import Path

from codestrata.scan_boundary import BoundaryPolicy, BoundaryService


def iter_repository_files(
    repository_root: Path,
    *,
    excluded_directories: set[str] | None = None,
    max_files: int | None = None,
    boundary_policy: BoundaryPolicy | None = None,
) -> list[str]:
    """Return sorted repo-relative file paths without following symlinks.

    Uses the shared :class:`BoundaryService`. When ``excluded_directories`` is
    provided (including an empty set), it becomes the complete directory-name
    exclusion set and ignore-path markers are cleared so callers can exercise
    traversal independently of default policy. Prefer ``boundary_policy`` for
    assessment paths.
    """

    if boundary_policy is not None:
        policy = boundary_policy
        if excluded_directories:
            policy = BoundaryPolicy(
                excluded_directory_names=frozenset(
                    policy.excluded_directory_names | set(excluded_directories)
                ),
                include_paths=policy.include_paths,
                exclude_paths=policy.exclude_paths,
                production_roots=policy.production_roots,
                test_roots=policy.test_roots,
                example_roots=policy.example_roots,
                generated_roots=policy.generated_roots,
                vendor_roots=policy.vendor_roots,
                fixture_roots=policy.fixture_roots,
                documentation_roots=policy.documentation_roots,
                source_role_overrides=policy.source_role_overrides,
                ignore_path_markers=policy.ignore_path_markers,
                policy_version=policy.policy_version,
            )
    elif excluded_directories is not None:
        policy = BoundaryPolicy(
            excluded_directory_names=frozenset(excluded_directories),
            ignore_path_markers=(),
        )
    else:
        policy = BoundaryPolicy()

    return BoundaryService(policy).collect_files(
        repository_root,
        max_files=max_files,
    )


def assert_path_within_root(candidate: Path, root: Path) -> Path:
    """Resolve ``candidate`` and ensure it stays under ``root``."""

    resolved_root = root.expanduser().resolve()
    resolved = candidate.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(
            f"path escapes allowed root {resolved_root}: {candidate}"
        ) from error
    return resolved


def safe_output_directory(path: Path, *, cwd: Path | None = None) -> Path:
    """Resolve an output directory under the process working directory by default.

    Absolute paths are allowed when they resolve successfully; the caller is
    responsible for user intent. Relative paths cannot escape via ``..`` beyond
    the resolved absolute location (resolve collapses ``..``).
    """

    base = (cwd or Path.cwd()).resolve()
    raw = path.expanduser()
    if not raw.is_absolute():
        candidate = (base / raw).resolve(strict=False)
    else:
        candidate = raw.resolve(strict=False)
    candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir():
        raise NotADirectoryError(f"output path is not a directory: {candidate}")
    return candidate
