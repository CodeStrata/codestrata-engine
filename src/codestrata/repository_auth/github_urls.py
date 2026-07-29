"""Parse and validate GitHub repository URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError

_SCP_PATTERN = re.compile(
    r"^git@(?P<host>[^:]+):(?P<path>.+)$",
)
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})


@dataclass(frozen=True)
class ParsedGitHubUrl:
    """Normalized GitHub repository URL components."""

    original: str
    transport: str  # "https" or "ssh"
    host: str
    owner: str
    repository: str
    credential_free_url: str

    @property
    def repository_name(self) -> str:
        return self.repository


def parse_github_repository_url(repository_url: str) -> ParsedGitHubUrl:
    """Validate and normalize a GitHub HTTPS or SSH repository URL."""

    compact = repository_url.strip()
    if not compact:
        raise UnsupportedRepositoryUrlError("Repository URL must not be empty.")

    if "://" not in compact and compact.startswith("git@"):
        return _parse_scp_url(compact)

    parsed = urlparse(compact)
    scheme = (parsed.scheme or "").lower()

    if scheme in {"http", "https"}:
        return _parse_https_url(compact, parsed)
    if scheme == "ssh":
        return _parse_ssh_uri(compact, parsed)

    raise UnsupportedRepositoryUrlError(
        "Unsupported repository URL scheme. Use HTTPS or SSH GitHub URLs."
    )


def _parse_https_url(original: str, parsed: object) -> ParsedGitHubUrl:
    hostname = getattr(parsed, "hostname", None)
    if hostname is None or hostname.lower() not in _GITHUB_HOSTS:
        raise UnsupportedRepositoryUrlError("Only GitHub repositories are supported.")

    if getattr(parsed, "username", None) or getattr(parsed, "password", None):
        raise UnsupportedRepositoryUrlError(
            "Repository URLs must not include embedded credentials."
        )

    owner, repository = _owner_and_repo(getattr(parsed, "path", "") or "")
    credential_free = urlunparse(
        (
            "https",
            "github.com",
            f"/{owner}/{repository}.git",
            "",
            "",
            "",
        )
    )
    return ParsedGitHubUrl(
        original=original,
        transport="https",
        host="github.com",
        owner=owner,
        repository=repository,
        credential_free_url=credential_free,
    )


def _parse_ssh_uri(original: str, parsed: object) -> ParsedGitHubUrl:
    hostname = getattr(parsed, "hostname", None)
    if hostname is None or hostname.lower() not in _GITHUB_HOSTS:
        raise UnsupportedRepositoryUrlError("Only GitHub repositories are supported.")

    owner, repository = _owner_and_repo(getattr(parsed, "path", "") or "")
    credential_free = f"ssh://git@github.com/{owner}/{repository}.git"
    return ParsedGitHubUrl(
        original=original,
        transport="ssh",
        host="github.com",
        owner=owner,
        repository=repository,
        credential_free_url=credential_free,
    )


def _parse_scp_url(original: str) -> ParsedGitHubUrl:
    match = _SCP_PATTERN.match(original)
    if match is None:
        raise UnsupportedRepositoryUrlError("Malformed GitHub SSH repository URL.")

    host = match.group("host").lower()
    if host not in _GITHUB_HOSTS:
        raise UnsupportedRepositoryUrlError("Only GitHub repositories are supported.")

    owner, repository = _owner_and_repo(match.group("path"))
    credential_free = f"git@github.com:{owner}/{repository}.git"
    return ParsedGitHubUrl(
        original=original,
        transport="ssh",
        host="github.com",
        owner=owner,
        repository=repository,
        credential_free_url=credential_free,
    )


def _owner_and_repo(path: str) -> tuple[str, str]:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise UnsupportedRepositoryUrlError("GitHub URL must contain an owner and repository name.")

    owner = parts[0]
    repository = parts[1]
    if repository.endswith(".git"):
        repository = repository[:-4]

    if not owner or not repository:
        raise UnsupportedRepositoryUrlError("Unable to determine repository name from URL.")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
        raise UnsupportedRepositoryUrlError("Invalid GitHub organization or owner name.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise UnsupportedRepositoryUrlError("Invalid GitHub repository name.")

    return owner, repository
