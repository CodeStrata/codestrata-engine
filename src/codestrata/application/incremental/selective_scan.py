"""Selective scan port and result models."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from codestrata.application.incremental.models import CandidateRepositoryState, RepositoryChangeSet
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.models import Repository


class SelectiveScanRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: str
    branch: str | None = None
    changes: RepositoryChangeSet
    previous_manifest: RepositoryManifest
    candidate: CandidateRepositoryState | None = None


class SelectiveScanResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scanned_files: tuple[str, ...] = ()
    deleted_files: tuple[str, ...] = ()
    updated_inventory_entries: tuple[RepositoryFileEntry, ...] = ()
    repository: Repository | None = None
    warnings: tuple[str, ...] = ()
    unsupported_paths: tuple[str, ...] = ()
    complete: bool = False
    supports_subset: bool = False


class SelectiveScanService(Protocol):
    """Rescan only plan-declared impacted files (or declare unsupported)."""

    def scan(self, request: SelectiveScanRequest) -> SelectiveScanResult:
        """Return selective scan output without running rules or persistence."""


class UnsupportedSelectiveScanService:
    """Default adapter: selective subset scanning is not supported."""

    def scan(self, request: SelectiveScanRequest) -> SelectiveScanResult:
        del request
        return SelectiveScanResult(
            complete=False,
            supports_subset=False,
            warnings=("selective_scan_unsupported",),
            unsupported_paths=(),
        )


class CandidateManifestSelectiveScanService:
    """Use trusted candidate manifest entries for changed paths (no filesystem).

    Suitable when the candidate was produced by a validated full inventory scan
    during planning. Does not open absolute paths beyond constructing a
    lightweight Repository for downstream stage rebuilds when ``repository_root``
    is provided via candidate warnings metadata (not used by default).
    """

    def scan(self, request: SelectiveScanRequest) -> SelectiveScanResult:
        if request.candidate is None:
            return SelectiveScanResult(
                complete=False,
                supports_subset=False,
                warnings=("candidate_required_for_manifest_scan",),
            )
        candidate_by_path = {entry.path.root: entry for entry in request.candidate.manifest.files}
        required = sorted(
            {
                *(item.path for item in request.changes.added),
                *(item.path for item in request.changes.modified),
                *(item.path for item in request.changes.metadata_changed),
            }
        )
        deleted = tuple(sorted(item.path for item in request.changes.deleted))
        updated: list[RepositoryFileEntry] = []
        unsupported: list[str] = []
        for path in required:
            entry = candidate_by_path.get(path)
            if entry is None:
                unsupported.append(path)
            else:
                updated.append(entry)
        complete = not unsupported
        files = [entry.path.root for entry in request.candidate.manifest.files]
        repository = Repository(
            name=request.candidate.display_name,
            path=Path(request.repository),
            default_branch=request.branch or request.candidate.branch,
            files=files,
            total_files=len(files),
            metadata={"incremental_selective_scan": "candidate_manifest"},
        )
        return SelectiveScanResult(
            scanned_files=tuple(required),
            deleted_files=deleted,
            updated_inventory_entries=tuple(updated),
            repository=repository,
            warnings=() if complete else ("missing_candidate_paths",),
            unsupported_paths=tuple(unsupported),
            complete=complete,
            supports_subset=True,
        )
