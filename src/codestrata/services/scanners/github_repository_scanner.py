"""Scanner for public and private GitHub repositories."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from codestrata.models import Repository
from codestrata.repository_auth.exceptions import (
    RepositoryAccessCategory,
    RepositoryAccessError,
)
from codestrata.repository_auth.git_runner import run_git, verify_remote_origin_url
from codestrata.repository_auth.models import RepositoryAuthenticationConfig
from codestrata.repository_auth.service import RepositoryAuthenticationService
from codestrata.security.redaction import Redactor
from codestrata.services.scanners.local_repository_scanner import (
    LocalRepositoryScanner,
)

logger = logging.getLogger(__name__)


class GitHubRepositoryScanner:
    """Clone and scan a GitHub repository with optional authentication.

    When ``ephemeral`` is True (assess default), the clone is placed in a unique
    temporary directory and the returned :class:`Repository` is marked
    ``ephemeral=True`` so callers can delete it after the assessment finishes.
    Local filesystem repositories are never produced by this scanner.
    """

    def __init__(
        self,
        workspace_directory: Path,
        branch: str | None = None,
        clean_before_clone: bool = True,
        local_scanner: LocalRepositoryScanner | None = None,
        authentication: RepositoryAuthenticationConfig | None = None,
        authentication_service: RepositoryAuthenticationService | None = None,
        clone_timeout_seconds: float = 300,
        *,
        ephemeral: bool = False,
    ) -> None:
        self._workspace_directory = workspace_directory
        self._branch = branch
        self._clean_before_clone = clean_before_clone
        self._local_scanner = local_scanner or LocalRepositoryScanner()
        self._authentication = authentication
        self._authentication_service = authentication_service or RepositoryAuthenticationService()
        self._clone_timeout_seconds = clone_timeout_seconds
        self._ephemeral = ephemeral

    def scan(self, repository_url: str) -> Repository:
        """Clone a GitHub repository and scan its files."""

        parsed = self._authentication_service.validate_compatibility(
            repository_url,
            self._authentication,
        )
        clone_url = parsed.credential_free_url
        repository_name = parsed.repository_name

        if self._ephemeral:
            parent = Path(tempfile.gettempdir())
            clone_directory = Path(
                tempfile.mkdtemp(
                    prefix=f"codestrata-github-{repository_name}-",
                    dir=str(parent),
                )
            )
            logger.info(
                "Cloning GitHub repository %s/%s into ephemeral workspace %s",
                parsed.owner,
                parsed.repository,
                clone_directory,
            )
        else:
            clone_directory = self._workspace_directory / repository_name
            self._workspace_directory.mkdir(parents=True, exist_ok=True)
            if clone_directory.exists():
                if self._clean_before_clone:
                    shutil.rmtree(clone_directory)
                else:
                    raise FileExistsError(
                        f"Repository workspace already exists: {clone_directory}"
                    )
            logger.info(
                "Cloning GitHub repository %s/%s via %s into %s",
                parsed.owner,
                parsed.repository,
                parsed.transport,
                clone_directory,
            )

        try:
            with self._authentication_service.git_execution_context(
                clone_url,
                self._authentication,
            ) as auth_context:
                provider_id = auth_context.provider_id
                logger.info(
                    "Using authentication provider %s for clone",
                    provider_id,
                )
                self._clone_repository(
                    clone_url=clone_url,
                    clone_directory=clone_directory,
                    environment=auth_context.environment,
                    redactor=auth_context.redactor,
                )
                verify_remote_origin_url(
                    clone_directory,
                    expected_credential_free_url=clone_url,
                    redactor=auth_context.redactor,
                )
        except RepositoryAccessError:
            self._cleanup_partial_clone(clone_directory)
            raise
        except Exception:
            self._cleanup_partial_clone(clone_directory)
            raise

        repository = self._local_scanner.scan(clone_directory)
        return repository.model_copy(
            update={
                "name": repository_name,
                "source_url": clone_url,
                "default_branch": self._branch,
                "ephemeral": self._ephemeral,
            }
        )

    def _clone_repository(
        self,
        *,
        clone_url: str,
        clone_directory: Path,
        environment: dict[str, str],
        redactor: Redactor,
    ) -> None:
        # Ephemeral mkdtemp leaves an empty directory; remove it so git can create
        # the destination path on all supported Git versions.
        if self._ephemeral and clone_directory.is_dir() and not any(clone_directory.iterdir()):
            clone_directory.rmdir()

        arguments = [
            "clone",
            "--depth",
            "1",
        ]
        if self._branch:
            arguments.extend(
                [
                    "--branch",
                    self._branch,
                    "--single-branch",
                ]
            )
        arguments.extend([clone_url, str(clone_directory)])

        run_git(
            arguments,
            timeout_seconds=self._clone_timeout_seconds,
            environment=environment,
            redactor=redactor,
        )

    def _cleanup_partial_clone(self, clone_directory: Path) -> None:
        if not clone_directory.exists():
            return
        try:
            shutil.rmtree(clone_directory)
            logger.info("Removed partial GitHub clone at %s", clone_directory)
        except OSError as error:
            raise RepositoryAccessError(
                "Failed to clean up a partial repository clone.",
                category=RepositoryAccessCategory.WORKSPACE_CLEANUP_FAILED,
            ) from error


def dispose_ephemeral_repository(repository: Repository) -> bool:
    """Delete an ephemeral GitHub clone. Never touches local user repositories.

    Returns True when a directory was removed.
    """

    if not repository.ephemeral:
        return False
    path = Path(repository.path)
    if not path.exists():
        logger.info(
            "Ephemeral GitHub clone already absent (nothing to clean): %s",
            path,
        )
        return False
    shutil.rmtree(path)
    logger.info("Cleaned up ephemeral GitHub clone at %s", path)
    return True


__all__ = [
    "GitHubRepositoryScanner",
    "dispose_ephemeral_repository",
]
