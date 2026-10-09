"""Path role and eligibility for quality metrics."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.evidence.inventory.classification import is_vendor_path
from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.application.evidence.quality.maps import (
    SUPPORTED_COMPLEXITY_LANGUAGES,
    language_for_path,
)
from codestrata.application.evidence.quality.models import FileRole
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.scan_boundary import default_ignore_path_markers

_ROLE = {
    SourceClassification.SOURCE: FileRole.SOURCE,
    SourceClassification.TEST: FileRole.TEST,
    SourceClassification.GENERATED: FileRole.GENERATED,
    SourceClassification.VENDOR: FileRole.VENDOR,
}


def file_role(path: str) -> FileRole:
    if is_vendor_path(path):
        return FileRole.VENDOR
    classification = classify_source_path(path)
    return _ROLE.get(classification, FileRole.OTHER)


def is_ignored(path: str, *, ignore_markers: Sequence[str] | None = None) -> bool:
    lower = path.replace("\\", "/").lower()
    if lower.startswith(".codestrata/") or "/.codestrata/" in lower:
        return True
    markers = tuple(ignore_markers) if ignore_markers is not None else default_ignore_path_markers()
    for marker in markers:
        compact = marker.strip().lower().lstrip("/")
        if compact and (compact in lower or lower.startswith(compact)):
            return True
    return False


def is_supported_source_path(path: str) -> bool:
    return language_for_path(path) is not None


def clone_eligible(path: str, role: FileRole) -> bool:
    if role in {FileRole.GENERATED, FileRole.VENDOR, FileRole.OTHER}:
        return False
    language = language_for_path(path)
    return language in SUPPORTED_COMPLEXITY_LANGUAGES and not is_ignored(path)


__all__ = ["clone_eligible", "file_role", "is_ignored", "is_supported_source_path"]
