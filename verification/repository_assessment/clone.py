"""Safe clone helpers for catalog-backed repositories."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from verification.repository_assessment.catalog import CatalogEntry, QualifiedRevision

_GITHUB_HOST = "github.com"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DEFAULT_CLONE_TIMEOUT_S = 180


@dataclass(frozen=True, slots=True)
class CloneResult:
    ok: bool
    checked_out_sha: str | None
    detail: str
    revision_type: str | None = None
    revision_value: str | None = None


def validate_public_https_url(url: str) -> tuple[bool, str]:
    """Accept only public HTTPS GitHub URLs without credentials."""

    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return False, "only https clone URLs are allowed"
    if parsed.username or parsed.password:
        return False, "credentials in clone URL are forbidden"
    if parsed.hostname not in {_GITHUB_HOST, f"www.{_GITHUB_HOST}"}:
        return False, f"host must be {_GITHUB_HOST}"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return False, "credentials in clone URL are forbidden"
    path = (parsed.path or "").rstrip("/")
    if not path or path.count("/") < 1:
        return False, "github repository path is required"
    return True, "ok"


def reject_floating_revision(revision: QualifiedRevision) -> tuple[bool, str]:
    value = revision.value.strip().lower()
    if value in {"main", "master", "head", "origin/main", "origin/master", "default", "latest"}:
        return False, "floating default-branch revisions are forbidden"
    if revision.revision_type == "commit":
        stripped = revision.value.strip()
        if len(stripped) != 40 or not _SHA_RE.match(stripped):
            return False, "commit revision must be a full 40-character hex SHA"
        if stripped != stripped.lower():
            return False, "commit SHA must be lowercase"
    return True, "ok"


def clone_qualified_repository(
    entry: CatalogEntry,
    destination: Path,
    *,
    timeout_s: int = _DEFAULT_CLONE_TIMEOUT_S,
) -> CloneResult:
    """Clone a catalog entry at its qualified revision into *destination*.

    Destination must not exist. Uses a bounded timeout. Does not initialize
    submodules or LFS. Verifies the final commit SHA.
    """

    if entry.qualified_revision is None:
        return CloneResult(False, None, "catalog entry has no qualified_revision")

    ok_url, url_detail = validate_public_https_url(entry.github_url)
    if not ok_url:
        return CloneResult(False, None, url_detail)

    ok_rev, rev_detail = reject_floating_revision(entry.qualified_revision)
    if not ok_rev:
        return CloneResult(False, None, rev_detail)

    if destination.exists():
        return CloneResult(False, None, "clone destination already exists")

    destination.parent.mkdir(parents=True, exist_ok=True)
    revision = entry.qualified_revision
    # Isolate from ambient credential helpers / global gitconfig userinfo.
    env = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": "/dev/null",
    }

    # Shallow clone compatible with pinned commit/tag when possible.
    clone_cmd = [
        "git",
        "clone",
        "--no-checkout",
        "--filter=blob:none",
        entry.github_url,
        str(destination),
    ]
    try:
        clone_proc = subprocess.run(
            clone_cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env={**dict(__import__("os").environ), **env},
        )
    except subprocess.TimeoutExpired:
        return CloneResult(False, None, "clone timed out")
    if clone_proc.returncode != 0:
        detail = (clone_proc.stderr or clone_proc.stdout or "").strip().splitlines()
        hint = detail[-1][:160] if detail else "no stderr"
        # Keep privacy: never include absolute destination path.
        hint = hint.replace(str(destination), "<clone-dest>")
        return CloneResult(
            False,
            None,
            f"clone failed (exit {clone_proc.returncode}): {hint}",
            revision.revision_type,
            revision.value,
        )

    # Prefer fetching an informational source_tag ref, then verify the pinned SHA.
    # Direct SHA fetch is still attempted when no source_tag is recorded.
    fetch_candidates: list[str] = []
    if revision.source_tag:
        fetch_candidates.append(revision.source_tag)
        fetch_candidates.append(f"refs/tags/{revision.source_tag}")
    fetch_candidates.append(revision.value)

    fetch_proc = None
    for fetch_ref in fetch_candidates:
        fetch_cmd = [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--depth",
            "1",
            "origin",
            fetch_ref,
        ]
        try:
            fetch_proc = subprocess.run(
                fetch_cmd,
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                env={**dict(__import__("os").environ), **env},
            )
        except subprocess.TimeoutExpired:
            return CloneResult(
                False, None, "fetch timed out", revision.revision_type, revision.value
            )
        if fetch_proc.returncode == 0:
            break
    else:
        # Final unshallow attempt of the authoritative commit/tag value.
        fetch_cmd = ["git", "-C", str(destination), "fetch", "origin", revision.value]
        fetch_proc = subprocess.run(
            fetch_cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env={**dict(__import__("os").environ), **env},
        )
        if fetch_proc.returncode != 0:
            return CloneResult(
                False,
                None,
                f"fetch revision failed (exit {fetch_proc.returncode})",
                revision.revision_type,
                revision.value,
            )

    checkout_target = revision.value if revision.revision_type == "commit" else "FETCH_HEAD"
    # Large repos (e.g. moodle) can exceed a hard 60s checkout; bound by clone timeout.
    checkout_timeout_s = max(60, int(timeout_s))
    checkout = subprocess.run(
        ["git", "-C", str(destination), "checkout", "--detach", checkout_target],
        check=False,
        text=True,
        capture_output=True,
        timeout=checkout_timeout_s,
        env={**dict(__import__("os").environ), **env},
    )
    if checkout.returncode != 0 and checkout_target != "FETCH_HEAD":
        checkout = subprocess.run(
            ["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"],
            check=False,
            text=True,
            capture_output=True,
            timeout=checkout_timeout_s,
            env={**dict(__import__("os").environ), **env},
        )
    if checkout.returncode != 0:
        return CloneResult(
            False,
            None,
            f"checkout failed (exit {checkout.returncode})",
            revision.revision_type,
            revision.value,
        )

    sha_proc = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
        env={**dict(__import__("os").environ), **env},
    )
    if sha_proc.returncode != 0:
        return CloneResult(False, None, "rev-parse failed", revision.revision_type, revision.value)
    sha = sha_proc.stdout.strip().lower()
    if not _SHA_RE.match(sha):
        return CloneResult(False, None, "checked-out SHA invalid", revision.revision_type, revision.value)

    if revision.revision_type == "commit":
        expected = revision.value.strip().lower()
        if sha != expected:
            return CloneResult(
                False,
                sha,
                "checked-out SHA does not match pinned commit",
                revision.revision_type,
                revision.value,
            )

    # Ensure origin never retains ambient credential userinfo from helpers.
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "remote",
            "set-url",
            "origin",
            entry.github_url,
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
        env={**dict(__import__("os").environ), **env},
    )

    return CloneResult(
        True,
        sha,
        "cloned and verified",
        revision.revision_type,
        revision.value,
    )
