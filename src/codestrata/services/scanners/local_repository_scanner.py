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


def _sanitize_git_origin_url(raw_url: str) -> str | None:
    """Sanitize git origin URL by removing embedded credentials/tokens."""
    from urllib.parse import urlparse, urlunparse

    from codestrata.domain.repository.identities import normalize_source_location

    url = raw_url.strip()
    if not url:
        return None

    if "://" not in url:
        if url.startswith("git@"):
            if any(ch in url for ch in ("?", "#")):
                return None
            try:
                return normalize_source_location(url)
            except ValueError:
                return None
        return None

    try:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https", "ssh", "git"):
            return None

        if parsed.query or parsed.fragment:
            return None

        hostname = parsed.hostname
        if not hostname:
            return None

        if scheme == "ssh":
            if parsed.password:
                return None
            user = f"{parsed.username}@" if parsed.username else ""
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{user}{hostname}{port}"
        else:
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{hostname}{port}"

        cleaned = urlunparse((scheme, netloc, parsed.path, "", "", ""))
        return normalize_source_location(cleaned)
    except Exception:
        return None


def _git_discovery_env() -> dict[str, str]:
    """Subprocess environment for origin discovery.

    An explicit ``GIT_CEILING_DIRECTORIES`` value is kept so a nested export
    does not inherit an unrelated parent repository. Other Git configuration
    is not forwarded.
    """

    import os

    env = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    ceiling = os.environ.get("GIT_CEILING_DIRECTORIES", "").strip()
    if ceiling:
        env["GIT_CEILING_DIRECTORIES"] = ceiling
    return env


def _detect_git_origin_url(repository_path: Path) -> str | None:
    """Return credential-free origin URL when the path is inside its Git work tree.

    Subdirectories of that work tree keep the repository origin. A ceiling stops
    discovery before an unrelated parent repository.
    """

    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(repository_path), "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env=_git_discovery_env(),
        )
    except Exception:  # noqa: BLE001
        return None
    url = (proc.stdout or "").strip()
    if not url:
        return None
    return _sanitize_git_origin_url(url)


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

    def scan(self, repository_path: Path | str) -> Repository:
        """Scan a local repository and return repository metadata."""

        resolved_path = Path(repository_path).expanduser().resolve()

        self._validate_repository_path(resolved_path)

        files = self._collect_files(resolved_path)
        self.last_diagnostics = self._boundary.diagnostics

        repository = Repository(
            name=resolved_path.name,
            path=resolved_path,
            files=files,
            total_files=len(files),
            source_url=_detect_git_origin_url(resolved_path),
        )
        repository.metadata["scan_boundary"] = self.last_diagnostics.to_dict()
        return repository

    def _validate_repository_path(self, repository_path: Path) -> None:
        """Validate that the repository path exists and is a directory."""

        if not repository_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repository_path}")

        if not repository_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {repository_path}")

        if repository_path.is_symlink():
            raise ValueError(f"Repository path must not be a symlink: {repository_path}")

    def _collect_files(self, repository_path: Path) -> list[str]:
        """Collect repository files using the shared boundary service."""

        return self._boundary.collect_files(
            repository_path,
            max_files=self._max_files,
        )
