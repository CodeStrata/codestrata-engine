"""Canonical repository identity and alias normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from codestrata.application.knowledge.errors import RepositoryIdentityError
from codestrata.application.knowledge.models import (
    RepositoryAliasType,
    RepositoryIdentityHints,
)
from codestrata.domain.repository.enums import RepositorySourceType
from codestrata.domain.repository.identities import normalize_source_location
from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError
from codestrata.repository_auth.github_urls import ParsedGitHubUrl, parse_github_repository_url


@dataclass(frozen=True, slots=True)
class NormalizedAlias:
    """A normalized alias ready for persistence or lookup."""

    alias_type: RepositoryAliasType
    alias_value: str


@dataclass(frozen=True, slots=True)
class NormalizedRepositoryIdentity:
    """Resolved identity plan derived from registration hints."""

    source_type: RepositorySourceType
    display_name: str
    canonical_key: str | None
    """GitHub canonical key when known; ``None`` means allocate ``local:{uuid}``."""

    github: ParsedGitHubUrl | None
    aliases: tuple[NormalizedAlias, ...]


def build_github_canonical_key(owner: str, repository: str) -> str:
    """Return ``github:{owner}/{repository}`` with lowercase owner and repo.

    GitHub owner/repository names are matched case-insensitively for identity.
    """

    owner_key = owner.strip().lower()
    repo_key = repository.strip().lower()
    if not owner_key or not repo_key:
        raise RepositoryIdentityError("GitHub owner and repository are required")
    return f"github:{owner_key}/{repo_key}"


def build_local_canonical_key(repository_id: str) -> str:
    """Return a local canonical key bound to a durable store UUID."""

    compact = repository_id.strip()
    if not compact:
        raise RepositoryIdentityError("repository_id is required for local canonical key")
    return f"local:{compact}"


def normalize_github_url_alias(parsed: ParsedGitHubUrl) -> str:
    """Stable credential-free HTTPS alias for GitHub repositories."""

    return (
        f"https://github.com/{parsed.owner.lower()}/{parsed.repository.lower()}.git"
    )


def normalize_local_path_alias(path: Path) -> str:
    """Absolute resolved path string for local_path aliases."""

    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError as error:
        raise RepositoryIdentityError(
            f"Unable to normalize local path: {path}"
        ) from error
    return str(resolved)


def normalize_identity_hints(hints: RepositoryIdentityHints) -> NormalizedRepositoryIdentity:
    """Normalize identity hints into a canonical key (if any) and aliases.

    Rules:

    * Credential-bearing URLs and URL userinfo are rejected.
    * Query strings and fragments on source URLs are rejected (not persisted).
    * GitHub URLs (any supported form) produce ``github:{owner}/{repo}``.
    * Local paths never become canonical keys.
    * Absolute local paths become ``local_path`` aliases when provided.
    """

    display_name = hints.display_name.strip()
    github: ParsedGitHubUrl | None = None
    aliases: list[NormalizedAlias] = []

    if hints.source_location is not None:
        location = _require_safe_source_location(hints.source_location)
        github = _try_parse_github(location)
        if github is None and hints.source_type is RepositorySourceType.GITHUB:
            raise RepositoryIdentityError(
                f"source_location is not a supported GitHub URL: {location}"
            )
        if github is not None:
            aliases.append(
                NormalizedAlias(
                    alias_type=RepositoryAliasType.GITHUB_URL,
                    alias_value=normalize_github_url_alias(github),
                )
            )

    if hints.local_path is not None:
        aliases.append(
            NormalizedAlias(
                alias_type=RepositoryAliasType.LOCAL_PATH,
                alias_value=normalize_local_path_alias(hints.local_path),
            )
        )

    if hints.existing_repository_key is not None:
        legacy = hints.existing_repository_key.strip()
        if not legacy:
            raise RepositoryIdentityError("existing_repository_key must be nonempty")
        if any(ch in legacy for ch in ("://", "@", "/", "\\", ":", "?", "#")):
            raise RepositoryIdentityError(
                "existing_repository_key must not contain URLs, paths, or credentials"
            )
        aliases.append(
            NormalizedAlias(
                alias_type=RepositoryAliasType.LEGACY_REPOSITORY_KEY,
                alias_value=legacy.lower(),
            )
        )

    canonical_key: str | None = None
    source_type = hints.source_type
    if github is not None:
        canonical_key = build_github_canonical_key(github.owner, github.repository)
        source_type = RepositorySourceType.GITHUB
    elif hints.source_type is RepositorySourceType.GITHUB:
        raise RepositoryIdentityError(
            "GitHub repositories require a credential-free source_location URL"
        )

    # Deduplicate aliases while preserving order.
    unique: list[NormalizedAlias] = []
    seen: set[tuple[str, str]] = set()
    for alias in aliases:
        key = (alias.alias_type.value, alias.alias_value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(alias)

    return NormalizedRepositoryIdentity(
        source_type=source_type,
        display_name=display_name,
        canonical_key=canonical_key,
        github=github,
        aliases=tuple(unique),
    )


def _require_safe_source_location(value: str) -> str:
    compact = value.strip()
    if not compact:
        raise RepositoryIdentityError("source_location must be nonempty")

    # Prefer GitHub parsing first so standard ``ssh://git@github.com/...`` URLs are
    # accepted (domain ``normalize_source_location`` treats ``git@`` userinfo as
    # credentials, which is incorrect for Git's SSH URI form).
    github = _try_parse_github(compact)
    if github is not None:
        if "://" in compact:
            parsed = urlparse(compact)
            if parsed.query or parsed.fragment:
                raise RepositoryIdentityError(
                    "source_location must not include query strings or fragments"
                )
        return github.credential_free_url

    try:
        safe = normalize_source_location(compact)
    except ValueError as error:
        raise RepositoryIdentityError(str(error)) from error

    if "://" in safe:
        parsed = urlparse(safe)
        if parsed.query or parsed.fragment:
            raise RepositoryIdentityError(
                "source_location must not include query strings or fragments"
            )
        if parsed.username or parsed.password:
            raise RepositoryIdentityError(
                "source_location must not include embedded credentials"
            )
    return safe


def _try_parse_github(location: str) -> ParsedGitHubUrl | None:
    try:
        return parse_github_repository_url(location)
    except UnsupportedRepositoryUrlError as error:
        message = str(error).lower()
        if "credential" in message:
            raise RepositoryIdentityError(str(error)) from error
        return None
