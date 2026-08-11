"""Human-readable logical repository artifact identity (Slice 17.15).

Folder names under ``.codestrata-artifacts/assessments/<repository_id>/``.
Run IDs remain metadata only — never the top-level assessment folder.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from codestrata.artifacts.layout import sanitize_repository_slug

# Prefer existing GitHub URL parser when available.
try:
    from codestrata.repository_auth.github_urls import parse_github_repository_url
except Exception:  # pragma: no cover - defensive import boundary
    parse_github_repository_url = None  # type: ignore[assignment]

_UNSAFE = re.compile(r"[^a-z0-9._-]+")
_MULTI_DASH = re.compile(r"-{2,}")
GITHUB_PREFIX = "github-"
LOCAL_PREFIX = "local-"
MAX_SEGMENT_LEN = 80


def _safe_segment(value: str) -> str:
    compact = unquote(value or "").strip().lower()
    # Strip credentials / userinfo leftovers if present in a raw fragment.
    if "@" in compact and "://" not in compact:
        compact = compact.rsplit("@", 1)[-1]
    slug = _UNSAFE.sub("-", compact).strip(".-")
    slug = _MULTI_DASH.sub("-", slug)
    if len(slug) > MAX_SEGMENT_LEN:
        slug = slug[:MAX_SEGMENT_LEN].rstrip("-")
    return slug or "repository"


def _short_suffix(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return digest


def build_github_repository_artifact_id(owner: str, repository: str) -> str:
    """Return ``github-<owner>-<repo>`` filesystem-safe logical identity."""

    owner_s = _safe_segment(owner)
    repo_s = _safe_segment(repository)
    if owner_s == "repository" or repo_s == "repository":
        raise ValueError("GitHub owner and repository are required")
    return f"{GITHUB_PREFIX}{owner_s}-{repo_s}"


def build_local_repository_artifact_id(
    repository_name: str,
    *,
    collision_seed: str | None = None,
) -> str:
    """Return ``local-<safe-name>``; optional short suffix only when required."""

    base = _safe_segment(repository_name)
    if collision_seed:
        return f"{LOCAL_PREFIX}{base}-{_short_suffix(collision_seed)}"
    return f"{LOCAL_PREFIX}{base}"


def try_parse_github_owner_repo(source: str | None) -> tuple[str, str] | None:
    """Extract (owner, repo) from a credential-free GitHub URL or ``owner/repo``."""

    if not source:
        return None
    raw = source.strip()
    if not raw:
        return None
    # Reject userinfo explicitly.
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.username or parsed.password:
        return None
    if parse_github_repository_url is not None:
        try:
            gh = parse_github_repository_url(raw)
            return gh.owner, gh.repository
        except Exception:
            pass
    # Lightweight fallback: github.com/owner/repo
    host = (parsed.hostname or "").lower()
    if host in {"github.com", "www.github.com"}:
        parts = [p for p in (parsed.path or "").strip("/").split("/") if p]
        if len(parts) >= 2:
            repo = parts[1].removesuffix(".git")
            return parts[0], repo
    # owner/repo shorthand (no scheme)
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        owner, repo = raw.split("/", 1)
        return owner, repo.removesuffix(".git")
    return None


def resolve_repository_artifact_id(
    *,
    repository_name: str,
    source_url: str | None = None,
    remote: str | None = None,
    catalog_github_repository: str | None = None,
    path: Path | str | None = None,
) -> str:
    """Resolve stable human-readable repository artifact folder identity.

    Preference order:
    1. GitHub remote / source URL / catalog ``owner/repo``
    2. ``local-<safe-name>`` from repository name (never absolute path)
    """

    for candidate in (remote, source_url, catalog_github_repository):
        parsed = try_parse_github_owner_repo(candidate)
        if parsed is not None:
            return build_github_repository_artifact_id(parsed[0], parsed[1])

    # Never use absolute local paths as identity.
    name = (repository_name or "").strip()
    if not name and path is not None:
        name = Path(path).name
    if not name:
        name = "repository"
    # If name already looks like a logical id, reuse.
    lowered = name.lower()
    if lowered.startswith(GITHUB_PREFIX) or lowered.startswith(LOCAL_PREFIX):
        return sanitize_logical_id(name)
    return build_local_repository_artifact_id(name)


def sanitize_logical_id(value: str) -> str:
    """Sanitize an already-prefixed logical id without stripping the prefix."""

    text = value.strip().lower()
    if text.startswith(GITHUB_PREFIX):
        rest = _safe_segment(text[len(GITHUB_PREFIX) :])
        return f"{GITHUB_PREFIX}{rest}"
    if text.startswith(LOCAL_PREFIX):
        rest = _safe_segment(text[len(LOCAL_PREFIX) :])
        return f"{LOCAL_PREFIX}{rest}"
    return _safe_segment(text)


def is_logical_repository_id(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text or "/" in text or "\\" in text or ".." in text:
        return False
    if text.startswith(GITHUB_PREFIX) and len(text) > len(GITHUB_PREFIX):
        return bool(re.fullmatch(r"github-[a-z0-9._-]+", text))
    if text.startswith(LOCAL_PREFIX) and len(text) > len(LOCAL_PREFIX):
        return bool(re.fullmatch(r"local-[a-z0-9._-]+", text))
    return False


__all__ = [
    "GITHUB_PREFIX",
    "LOCAL_PREFIX",
    "build_github_repository_artifact_id",
    "build_local_repository_artifact_id",
    "is_logical_repository_id",
    "resolve_repository_artifact_id",
    "sanitize_logical_id",
    "try_parse_github_owner_repo",
]
