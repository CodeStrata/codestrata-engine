"""Discover and classify assessment artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verification.repository_assessment.contract import REQUIRED_ARTIFACT_NAMES

# Soft size bound for structural validation (bytes).
_MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    name: str
    classification: str  # required|optional|forbidden|generated|missing|malformed|unexpected
    relative_path: str | None = None
    valid_utf8: bool | None = None
    valid_json: bool | None = None
    top_level_type: str | None = None
    schema_version: str | None = None
    size_bytes: int | None = None
    issues: tuple[str, ...] = ()


@dataclass
class ArtifactInventory:
    run_directory_relative: str | None = None
    records: list[ArtifactRecord] = field(default_factory=list)

    def by_name(self) -> dict[str, ArtifactRecord]:
        return {item.name: item for item in self.records}

    def actual_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    item.name
                    for item in self.records
                    if item.classification in {"required", "optional", "generated", "unexpected"}
                    and item.relative_path
                }
            )
        )

    def validation_map(self) -> dict[str, str]:
        return {item.name: item.classification for item in self.records}


def find_latest_run_directory(output_root: Path) -> Path | None:
    """Locate the newest assessment run directory under *output_root*."""

    if not output_root.exists():
        return None
    candidates: list[Path] = []
    for path in output_root.rglob("report.json"):
        if path.is_file():
            candidates.append(path.parent)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        # Output outside repo — use basename chain only.
        return path.name


def _inspect_json(path: Path) -> tuple[bool, str | None, str | None, tuple[str, ...]]:
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, None, None, ("not_utf8",)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False, None, None, ("invalid_json",)
    top = type(payload).__name__
    schema: str | None = None
    if isinstance(payload, dict):
        schema = payload.get("schema_version")
        if schema is None and isinstance(payload.get("assessment"), dict):
            schema = payload["assessment"].get("schema_version")
        schema = str(schema) if schema is not None else None
    else:
        issues.append("unexpected_top_level_type")
    size = path.stat().st_size
    if size > _MAX_ARTIFACT_BYTES:
        issues.append("oversized")
    if size == 0:
        issues.append("empty")
    return True, top, schema, tuple(issues)


def enumerate_artifacts(repo_root: Path, output_relative: str = "reports") -> ArtifactInventory:
    output_root = repo_root / output_relative
    run_dir = find_latest_run_directory(output_root)
    inventory = ArtifactInventory(
        run_directory_relative=_rel(run_dir, repo_root) if run_dir else None,
    )
    if run_dir is None:
        for name in REQUIRED_ARTIFACT_NAMES:
            inventory.records.append(
                ArtifactRecord(name=name, classification="missing", issues=("run_directory_missing",))
            )
        return inventory

    present = {p.name: p for p in run_dir.iterdir() if p.is_file()}
    # Also note directories as optional bundles.
    for name in REQUIRED_ARTIFACT_NAMES:
        path = present.get(name)
        if path is None:
            inventory.records.append(ArtifactRecord(name=name, classification="missing"))
            continue
        ok_json = name.endswith(".json")
        if ok_json:
            valid, top, schema, issues = _inspect_json(path)
            classification = "malformed" if issues and "invalid_json" in issues else "required"
            if not valid and "not_utf8" in issues:
                classification = "malformed"
            inventory.records.append(
                ArtifactRecord(
                    name=name,
                    classification=classification,
                    relative_path=_rel(path, repo_root),
                    valid_utf8="not_utf8" not in issues,
                    valid_json=valid,
                    top_level_type=top,
                    schema_version=schema,
                    size_bytes=path.stat().st_size,
                    issues=issues,
                )
            )
        else:
            # HTML
            try:
                path.read_text(encoding="utf-8")
                utf8 = True
                issues: tuple[str, ...] = ()
            except UnicodeDecodeError:
                utf8 = False
                issues = ("not_utf8",)
            classification = "malformed" if issues else "required"
            inventory.records.append(
                ArtifactRecord(
                    name=name,
                    classification=classification,
                    relative_path=_rel(path, repo_root),
                    valid_utf8=utf8,
                    size_bytes=path.stat().st_size,
                    issues=issues,
                )
            )

    for name, path in sorted(present.items()):
        if name in REQUIRED_ARTIFACT_NAMES:
            continue
        if name.endswith(".json"):
            valid, top, schema, issues = _inspect_json(path)
            inventory.records.append(
                ArtifactRecord(
                    name=name,
                    classification="optional" if valid else "malformed",
                    relative_path=_rel(path, repo_root),
                    valid_utf8=True,
                    valid_json=valid,
                    top_level_type=top,
                    schema_version=schema,
                    size_bytes=path.stat().st_size,
                    issues=issues,
                )
            )
        else:
            inventory.records.append(
                ArtifactRecord(
                    name=name,
                    classification="optional",
                    relative_path=_rel(path, repo_root),
                    size_bytes=path.stat().st_size,
                )
            )

    graphs = run_dir / "graphs"
    if graphs.is_dir():
        inventory.records.append(
            ArtifactRecord(
                name="graphs/",
                classification="optional",
                relative_path=_rel(graphs, repo_root),
            )
        )
    return inventory


def artifact_payload_summary(inventory: ArtifactInventory) -> dict[str, Any]:
    return {
        "run_directory_relative": inventory.run_directory_relative,
        "actual": list(inventory.actual_names()),
        "validation": inventory.validation_map(),
    }
