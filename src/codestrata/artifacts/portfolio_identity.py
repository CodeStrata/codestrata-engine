"""Human-readable logical portfolio / EIR identity (Slice 17.15).

Folder names under ``.codestrata-artifacts/intelligence/<portfolio_id>/``.
``portfolio_run_id`` remains metadata only.
"""

from __future__ import annotations

import re

_UNSAFE = re.compile(r"[^a-z0-9._-]+")
_MULTI_DASH = re.compile(r"-{2,}")

# Authoritative suite / catalog purpose for the 22-repo validation portfolio.
RELEASE_VALIDATION_PORTFOLIO_ID = "release-validation"


def sanitize_portfolio_id(name: str) -> str:
    """Normalize a logical portfolio name to a filesystem-safe identity."""

    compact = (name or "").strip().lower()
    # Strip accidental run-id / timestamp suffixes if a caller passes them.
    compact = re.sub(r"-\d{8}-\d{6}$", "", compact)
    if compact.startswith("portfolio-sv"):
        # Map historical suite portfolio run folders to release-validation.
        if "sv17-13" in compact or compact.startswith("portfolio-sv17-13"):
            return RELEASE_VALIDATION_PORTFOLIO_ID
    slug = _UNSAFE.sub("-", compact).strip(".-")
    slug = _MULTI_DASH.sub("-", slug)
    return slug or "portfolio"


def resolve_portfolio_artifact_id(
    *,
    portfolio_name: str | None = None,
    suite_id: str | None = None,
    catalog_purpose: str | None = None,
) -> str:
    """Resolve stable portfolio folder identity.

    Prefer catalog / suite logical names (e.g. ``release-validation``) over
    timestamped ``portfolio-sv17-13-*`` run folders.
    """

    for candidate in (portfolio_name, catalog_purpose, suite_id):
        if not candidate:
            continue
        text = candidate.strip().lower()
        if text in {"release_validation", "release-validation", "sv17-13"}:
            return RELEASE_VALIDATION_PORTFOLIO_ID
        if text.startswith("portfolio-sv17-13"):
            return RELEASE_VALIDATION_PORTFOLIO_ID
        if text == "community-22-repository-validation":
            return RELEASE_VALIDATION_PORTFOLIO_ID
        return sanitize_portfolio_id(text)
    return RELEASE_VALIDATION_PORTFOLIO_ID


def is_logical_portfolio_id(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text or "/" in text or "\\" in text or ".." in text:
        return False
    # Reject pure run-id style portfolio folders.
    if re.fullmatch(r"portfolio-sv\d+-\d+-\d{8}-\d{6}", text):
        return False
    if re.fullmatch(r"portfolio-\d{8}-\d{6}", text):
        return False
    return bool(re.fullmatch(r"[a-z0-9._-]+", text))


__all__ = [
    "RELEASE_VALIDATION_PORTFOLIO_ID",
    "is_logical_portfolio_id",
    "resolve_portfolio_artifact_id",
    "sanitize_portfolio_id",
]
