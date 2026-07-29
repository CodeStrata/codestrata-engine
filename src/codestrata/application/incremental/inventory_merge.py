"""Deterministic inventory merge for incremental execution."""

from __future__ import annotations

from codestrata.application.incremental.errors import IncrementalArtifactMergeError
from codestrata.application.incremental.models import RepositoryChangeSet
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.domain.repository.paths import RepositoryPath


def merge_inventory(
    previous: RepositoryManifest,
    *,
    changes: RepositoryChangeSet,
    updated_entries: tuple[RepositoryFileEntry, ...],
    candidate_identity_manifest: RepositoryManifest | None = None,
) -> RepositoryManifest:
    """Merge previous inventory with selective updates into a complete inventory.

    Never mutates ``previous``. Raises on missing required updates or duplicates.
    """

    by_path: dict[str, RepositoryFileEntry] = {entry.path.root: entry for entry in previous.files}
    updated = {entry.path.root: entry for entry in updated_entries}
    if len(updated) != len(updated_entries):
        raise IncrementalArtifactMergeError(
            "Duplicate paths in selective scan updates",
            reason_code="duplicate_scan_paths",
        )

    required_current = sorted(
        {
            *(item.path for item in changes.added),
            *(item.path for item in changes.modified),
            *(item.path for item in changes.metadata_changed),
        }
    )
    for path in required_current:
        _assert_safe_relative_path(path)
        if path not in updated:
            raise IncrementalArtifactMergeError(
                "Missing selective scan output for required changed path",
                reason_code="missing_scan_output",
                failed_step="inventory_merge",
            )
        by_path[path] = updated[path]

    for item in changes.deleted:
        _assert_safe_relative_path(item.path)
        by_path.pop(item.path, None)

    # Unchanged paths remain from previous; extras from updated that aren't changes
    # are ignored unless they replace existing keys (already handled).
    identity = (
        candidate_identity_manifest.identity
        if candidate_identity_manifest is not None
        else previous.identity
    )
    revision = (
        candidate_identity_manifest.revision
        if candidate_identity_manifest is not None
        else previous.revision
    )
    files = tuple(by_path[key] for key in sorted(by_path))
    paths = [entry.path.root for entry in files]
    if len(paths) != len(set(paths)):
        raise IncrementalArtifactMergeError(
            "Merged inventory contains duplicate normalized paths",
            reason_code="duplicate_inventory_paths",
            failed_step="inventory_merge",
        )
    return RepositoryManifest(identity=identity, revision=revision, files=files)


def _assert_safe_relative_path(path: str) -> None:
    compact = path.strip().replace("\\", "/")
    if not compact or compact.startswith("/") or compact.startswith("../") or "/../" in compact:
        raise IncrementalArtifactMergeError(
            "Unsafe or absolute path rejected during inventory merge",
            reason_code="unsafe_path",
            failed_step="inventory_merge",
        )
    # Validate via domain path object.
    _ = RepositoryPath(compact)
