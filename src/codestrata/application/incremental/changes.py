"""Change classification from repository manifests."""

from __future__ import annotations

import logging

from codestrata.application.incremental.fingerprints import planning_file_fingerprint
from codestrata.application.incremental.models import (
    FileChange,
    FileChangeDimensions,
    FileChangeKind,
    RepositoryChangeSet,
)
from codestrata.domain.repository.changes import RepositoryManifestDiffer
from codestrata.domain.repository.enums import RepositoryChangeType, RepositoryFileKind
from codestrata.domain.repository.manifests import RepositoryManifest

logger = logging.getLogger(__name__)

_SOURCE_LIKE = frozenset({RepositoryFileKind.SOURCE, RepositoryFileKind.TEST})
_BUILD_LIKE = frozenset({RepositoryFileKind.BUILD})


class ChangeClassifier:
    """Classify differences between previous and candidate manifests."""

    def classify(
        self,
        previous: RepositoryManifest,
        current: RepositoryManifest,
        *,
        previous_snapshot_id: str | None = None,
        candidate_snapshot_id: str | None = None,
    ) -> RepositoryChangeSet:
        diff = RepositoryManifestDiffer.diff(previous, current, include_unchanged=True)
        added: list[FileChange] = []
        modified: list[FileChange] = []
        deleted: list[FileChange] = []
        metadata_changed: list[FileChange] = []
        unknown: list[FileChange] = []
        unchanged_count = 0

        for change in sorted(diff.changes, key=lambda item: item.path.root):
            path = change.path.root
            previous_fp = (
                None if change.previous is None else planning_file_fingerprint(change.previous)
            )
            current_fp = (
                None if change.current is None else planning_file_fingerprint(change.current)
            )
            role = RepositoryFileKind.UNKNOWN
            if change.current is not None:
                role = change.current.file_kind
            elif change.previous is not None:
                role = change.previous.file_kind

            if change.change_type is RepositoryChangeType.UNCHANGED:
                unchanged_count += 1
                continue

            if change.change_type is RepositoryChangeType.ADDED:
                item = FileChange(
                    path=path,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                    kind=FileChangeKind.ADDED,
                    dimensions=FileChangeDimensions(content_changed=True),
                    role=role,
                    reasons=("path_added",),
                )
                added.append(item)
                continue

            if change.change_type is RepositoryChangeType.DELETED:
                item = FileChange(
                    path=path,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                    kind=FileChangeKind.DELETED,
                    dimensions=FileChangeDimensions(content_changed=True),
                    role=role,
                    reasons=("path_deleted",),
                )
                deleted.append(item)
                continue

            if change.change_type is RepositoryChangeType.METADATA_CHANGED:
                item = FileChange(
                    path=path,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                    kind=FileChangeKind.METADATA_CHANGED,
                    dimensions=FileChangeDimensions(metadata_changed=True),
                    role=role,
                    reasons=("metadata_changed",),
                )
                metadata_changed.append(item)
                continue

            if change.change_type is RepositoryChangeType.MODIFIED:
                dimensions = FileChangeDimensions(content_changed=True)
                reasons = ["content_changed"]
                # Structural/dependency hashes are unavailable in 2F.1 — mark unknown
                # when content changed for source-like files.
                if role in _SOURCE_LIKE:
                    dimensions = FileChangeDimensions(
                        content_changed=True,
                        structure_changed=False,
                        dependencies_changed=False,
                        unknown=True,
                    )
                    reasons.append("structural_hash_unavailable")
                if role is RepositoryFileKind.DEPENDENCY_MANIFEST:
                    dimensions = FileChangeDimensions(
                        content_changed=True,
                        dependencies_changed=True,
                    )
                    reasons.append("dependency_manifest_changed")
                item = FileChange(
                    path=path,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                    kind=FileChangeKind.MODIFIED,
                    dimensions=dimensions,
                    role=role,
                    reasons=tuple(reasons),
                )
                modified.append(item)
                continue

            unknown.append(
                FileChange(
                    path=path,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                    kind=FileChangeKind.UNKNOWN,
                    dimensions=FileChangeDimensions(unknown=True),
                    role=role,
                    reasons=("classification_unknown",),
                )
            )

        all_changed = (*added, *modified, *deleted, *metadata_changed, *unknown)
        has_source = any(item.role in _SOURCE_LIKE for item in all_changed)
        has_build = any(item.role in _BUILD_LIKE for item in all_changed)
        has_config = any(
            item.role in {RepositoryFileKind.CONFIGURATION, RepositoryFileKind.INFRASTRUCTURE}
            for item in all_changed
        )
        has_deps = any(item.role is RepositoryFileKind.DEPENDENCY_MANIFEST for item in all_changed)
        non_doc = [
            item for item in all_changed if item.role is not RepositoryFileKind.DOCUMENTATION
        ]
        has_doc_only = bool(all_changed) and not non_doc

        result = RepositoryChangeSet(
            previous_snapshot_id=previous_snapshot_id,
            candidate_snapshot_id=candidate_snapshot_id,
            added=tuple(added),
            modified=tuple(modified),
            deleted=tuple(deleted),
            metadata_changed=tuple(metadata_changed),
            unchanged_count=unchanged_count,
            unknown=tuple(unknown),
            change_count=len(all_changed),
            has_source_changes=has_source,
            has_build_changes=has_build,
            has_configuration_changes=has_config,
            has_dependency_manifest_changes=has_deps,
            has_documentation_only_changes=has_doc_only,
        )
        logger.info(
            "incremental.change_classified",
            extra={
                "change_count": result.change_count,
                "unchanged_count": result.unchanged_count,
                "has_source_changes": result.has_source_changes,
            },
        )
        return result
