"""Shared evidence location formatting for reporters."""

from __future__ import annotations

from codestrata.models.evidence import Evidence

REPOSITORY_LEVEL_EVIDENCE_LABEL = "Repository-level analysis"
_ROOT_PATHS = frozenset({".", "./"})


def format_evidence_location(
    file_path: str,
    line_number: int | None = None,
    column_number: int | None = None,
) -> str:
    """Format a repository-relative evidence location for human-readable reports.

    Rules:
    - repository root paths "." and "./" display as "Repository-level analysis"
    - path only when line is absent
    - path:line when column is absent
    - path:line:column when both are available

    JSON and domain models retain the original path values unchanged.
    """

    path = file_path.strip() if file_path else ""
    if not path:
        return ""

    display_path = REPOSITORY_LEVEL_EVIDENCE_LABEL if path in _ROOT_PATHS else path

    if line_number is None:
        return display_path

    location = f"{display_path}:{line_number}"
    if column_number is None:
        return location
    return f"{location}:{column_number}"


def format_evidence_item_location(evidence: Evidence) -> str:
    """Format an Evidence object's primary location string."""

    return format_evidence_location(
        evidence.file_path,
        evidence.line_number,
        evidence.column_number,
    )
