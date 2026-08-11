"""Artifact classification for init verification."""

from __future__ import annotations

from pathlib import Path

from verification.cli_initialization.contract import (
    FORBIDDEN_ARTIFACTS,
    OPTIONAL_DECLARED_DIRS,
    REQUIRED_ARTIFACTS,
    InitializationContract,
    default_contract,
)


def classify_artifacts(
    root: Path,
    *,
    pre_existing: set[str],
    contract: InitializationContract | None = None,
) -> dict[str, str]:
    """Map relative paths → required|optional|forbidden|pre_existing|unexpected."""

    active = contract or default_contract()
    classifications: dict[str, str] = {}
    files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    dirs = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    }

    for rel in sorted(files | dirs):
        if rel in pre_existing:
            classifications[rel] = "pre_existing"
        elif rel in active.required_artifacts or rel in REQUIRED_ARTIFACTS:
            classifications[rel] = "required"
        elif any(rel == item or rel.startswith(item + "/") for item in FORBIDDEN_ARTIFACTS):
            classifications[rel] = "forbidden"
        elif rel in OPTIONAL_DECLARED_DIRS:
            classifications[rel] = "optional"
        elif rel == "codestrata.toml":
            classifications[rel] = "required"
        elif rel.startswith("reports/") or rel.endswith("report.json"):
            classifications[rel] = "forbidden"
        else:
            # New files beyond required config are unexpected for init-only.
            if rel not in pre_existing and rel not in REQUIRED_ARTIFACTS:
                if rel == "codestrata.toml":
                    classifications[rel] = "required"
                else:
                    # Doctor may create reports/.codestrata-doctor-write-probe transiently;
                    # persistent reports dir after doctor is optional product side-effect.
                    if rel == "reports" or rel.startswith("reports/"):
                        classifications[rel] = "optional"
                    else:
                        classifications[rel] = "unexpected"
            else:
                classifications[rel] = "pre_existing"
    return classifications


def forbidden_present(classifications: dict[str, str]) -> list[str]:
    return sorted(path for path, kind in classifications.items() if kind == "forbidden")


def required_missing(classifications: dict[str, str], required: tuple[str, ...] | None = None) -> list[str]:
    need = required or REQUIRED_ARTIFACTS
    present = set(classifications)
    return [item for item in need if item not in present]
