"""Assessment head artifact naming (Slice 17.12).

Domain head JSON files remain the source of truth. Filenames under ``heads/``
are stable short names; legacy ``*-assessment.json`` basenames map here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AssessmentHeadSpec:
    """One assessment head artifact specification."""

    head_id: str
    heads_basename: str
    legacy_filename: str


# Order is presentation-stable for manifests.
ASSESSMENT_HEAD_SPECS: tuple[AssessmentHeadSpec, ...] = (
    AssessmentHeadSpec("architecture", "architecture.json", "architecture-assessment.json"),
    AssessmentHeadSpec("security", "security.json", "security-assessment.json"),
    AssessmentHeadSpec("technical-debt", "technical-debt.json", "technical-debt-assessment.json"),
    AssessmentHeadSpec("cloud", "cloud.json", "cloud-assessment.json"),
    AssessmentHeadSpec("ai", "ai.json", "ai-readiness-assessment.json"),
    AssessmentHeadSpec("dependencies", "dependencies.json", "dependency-assessment.json"),
    AssessmentHeadSpec("testing", "testing.json", "testing-assessment.json"),
    AssessmentHeadSpec("performance", "performance.json", "performance-assessment.json"),
)

_LEGACY_TO_HEAD = {spec.legacy_filename: spec.heads_basename for spec in ASSESSMENT_HEAD_SPECS}
_HEAD_ID_TO_SPEC = {spec.head_id: spec for spec in ASSESSMENT_HEAD_SPECS}


def heads_directory(run_directory: Path) -> Path:
    return run_directory / "heads"


def head_basename_for_legacy_filename(legacy_filename: str) -> str:
    """Map a legacy ``*-assessment.json`` basename to ``heads/<name>.json``."""

    mapped = _LEGACY_TO_HEAD.get(legacy_filename)
    if mapped is not None:
        return mapped
    # Fallback: strip trailing -assessment.json if present.
    name = legacy_filename
    if name.endswith("-assessment.json"):
        return name[: -len("-assessment.json")] + ".json"
    return name


def resolve_head_path(run_directory: Path, *, head_id: str | None = None, legacy_filename: str | None = None) -> Path:
    """Return the authoritative path for a head artifact under ``heads/``."""

    heads = heads_directory(run_directory)
    if head_id is not None:
        spec = _HEAD_ID_TO_SPEC.get(head_id)
        if spec is None:
            raise KeyError(f"unknown assessment head id: {head_id!r}")
        return heads / spec.heads_basename
    if legacy_filename is not None:
        return heads / head_basename_for_legacy_filename(legacy_filename)
    raise ValueError("head_id or legacy_filename is required")


def list_completed_heads(run_directory: Path) -> list[dict[str, str]]:
    """Return completed head descriptors present on disk."""

    heads = heads_directory(run_directory)
    completed: list[dict[str, str]] = []
    if not heads.is_dir():
        return completed
    for spec in ASSESSMENT_HEAD_SPECS:
        path = heads / spec.heads_basename
        if path.is_file():
            completed.append(
                {
                    "head_id": spec.head_id,
                    "path": f"heads/{spec.heads_basename}",
                    "legacy_filename": spec.legacy_filename,
                }
            )
    return completed
