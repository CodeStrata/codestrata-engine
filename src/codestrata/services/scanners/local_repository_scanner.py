"""Local file-system implementation of the repository scanner."""

from collections.abc import Iterable
from pathlib import Path

from codestrata.models import Repository
from codestrata.scan_boundary import (
    DEFAULT_EXCLUDED_DIRECTORY_NAMES,
    BoundaryDiagnostics,
    BoundaryPolicy,
    BoundaryService,
)


class LocalRepositoryScanner:
    """Scans a repository located on the local file system."""

    DEFAULT_EXCLUDED_DIRECTORIES = DEFAULT_EXCLUDED_DIRECTORY_NAMES

    # Align with AnalysisRuntimeSettings.max_source_files default.
    DEFAULT_MAX_FILES = 2000

    def __init__(
        self,
        excluded_directories: Iterable[str] | None = None,
        *,
        max_files: int | None = DEFAULT_MAX_FILES,
        boundary_policy: BoundaryPolicy | None = None,
    ) -> None:
        additional_exclusions = set(excluded_directories or [])
        if boundary_policy is None:
            excluded = frozenset(self.DEFAULT_EXCLUDED_DIRECTORIES | additional_exclusions)
            policy = BoundaryPolicy(excluded_directory_names=excluded)
        elif additional_exclusions:
            policy = BoundaryPolicy(
                excluded_directory_names=frozenset(
                    boundary_policy.excluded_directory_names | additional_exclusions
                ),
                include_paths=boundary_policy.include_paths,
                exclude_paths=boundary_policy.exclude_paths,
                production_roots=boundary_policy.production_roots,
                test_roots=boundary_policy.test_roots,
                example_roots=boundary_policy.example_roots,
                generated_roots=boundary_policy.generated_roots,
                vendor_roots=boundary_policy.vendor_roots,
                fixture_roots=boundary_policy.fixture_roots,
                documentation_roots=boundary_policy.documentation_roots,
                source_role_overrides=boundary_policy.source_role_overrides,
                ignore_path_markers=boundary_policy.ignore_path_markers,
                policy_version=boundary_policy.policy_version,
            )
        else:
            policy = boundary_policy

        self._boundary = BoundaryService(policy)
        self._excluded_directories = set(policy.excluded_directory_names)
        self._max_files = max_files
        self.last_diagnostics: BoundaryDiagnostics = self._boundary.diagnostics

    def scan(self, repository_path: Path) -> Repository:
        """Scan a local repository and return repository metadata."""

        resolved_path = repository_path.expanduser().resolve()

        self._validate_repository_path(resolved_path)

        files = self._collect_files(resolved_path)
        self.last_diagnostics = self._boundary.diagnostics

        return Repository(
            name=resolved_path.name,
            path=resolved_path,
            files=files,
            total_files=len(files),
        )

    def _validate_repository_path(self, repository_path: Path) -> None:
        """Validate that the repository path exists and is a directory."""

        if not repository_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repository_path}")

        if not repository_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {repository_path}")

        if repository_path.is_symlink():
            raise ValueError(
                f"Repository path must not be a symlink: {repository_path}"
            )

    def _collect_files(self, repository_path: Path) -> list[str]:
        """Collect repository files using the shared boundary service."""

        return self._boundary.collect_files(
            repository_path,
            max_files=self._max_files,
        )
