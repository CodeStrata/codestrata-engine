"""Scan-boundary package — shared repository path gating and source roles."""

from __future__ import annotations

from codestrata.scan_boundary.policy import (
    BOUNDARY_POLICY_VERSION,
    DEFAULT_EXCLUDED_DIRECTORY_NAMES,
    ScanSourceRole,
    default_ignore_path_markers,
)
from codestrata.scan_boundary.service import (
    BoundaryDecision,
    BoundaryDiagnostics,
    BoundaryPolicy,
    BoundaryService,
    classify_path_role,
    normalize_repo_relative,
)

__all__ = [
    "BOUNDARY_POLICY_VERSION",
    "DEFAULT_EXCLUDED_DIRECTORY_NAMES",
    "BoundaryDecision",
    "BoundaryDiagnostics",
    "BoundaryPolicy",
    "BoundaryService",
    "ScanSourceRole",
    "classify_path_role",
    "default_ignore_path_markers",
    "normalize_repo_relative",
]
