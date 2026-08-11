"""Failure-safe current/previous report artifact lifecycle (Slice 17.15).

Assessments:
  assessments/<repository_id>/{current,previous}/

Intelligence:
  intelligence/<portfolio_id>/{current,previous}/

Failed runs never promote. Max two versions per logical identity.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from codestrata.artifacts.layout import (
    ASSESSMENTS_DIRNAME,
    INTELLIGENCE_DIRNAME,
    TEMPORARY_DIRNAME,
    artifact_root,
    ensure_artifact_tree,
    is_assessment_run_id,
    manifests_directory,
)
from codestrata.artifacts.manifest import (
    ASSESSMENT_HTML_BASENAME,
    ASSESSMENT_JSON_BASENAME,
    ARTIFACT_MANIFEST_BASENAME,
)
from codestrata.artifacts.portfolio_identity import (
    is_logical_portfolio_id,
    resolve_portfolio_artifact_id,
)
from codestrata.artifacts.repository_identity import (
    is_logical_repository_id,
    resolve_repository_artifact_id,
)

SLOT_CURRENT = "current"
SLOT_PREVIOUS = "previous"
ArtifactSlot = Literal["current", "previous"]
MAX_VERSIONS = 2

EIR_JSON = "engineering-intelligence-report.json"
EIR_HTML = "engineering-intelligence-report.html"


class LifecycleError(RuntimeError):
    """Raised when lifecycle rotation cannot complete safely."""


@dataclass(frozen=True, slots=True)
class LifecycleLock:
    path: Path

    def release(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass


def assessment_logical_directory(repository_id: str, *, base: Path | None = None) -> Path:
    return artifact_root(base) / ASSESSMENTS_DIRNAME / repository_id


def assessment_slot_directory(
    repository_id: str,
    slot: ArtifactSlot,
    *,
    base: Path | None = None,
) -> Path:
    return assessment_logical_directory(repository_id, base=base) / slot


def intelligence_logical_directory(portfolio_id: str, *, base: Path | None = None) -> Path:
    return artifact_root(base) / INTELLIGENCE_DIRNAME / portfolio_id


def intelligence_slot_directory(
    portfolio_id: str,
    slot: ArtifactSlot,
    *,
    base: Path | None = None,
) -> Path:
    return intelligence_logical_directory(portfolio_id, base=base) / slot


def staging_assessment_directory(run_id: str, *, base: Path | None = None) -> Path:
    root = ensure_artifact_tree(base)
    path = root / TEMPORARY_DIRNAME / "assessment-runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def staging_intelligence_directory(run_id: str, *, base: Path | None = None) -> Path:
    root = ensure_artifact_tree(base)
    path = root / TEMPORARY_DIRNAME / "intelligence-runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lock_path(logical_dir: Path) -> Path:
    return logical_dir / ".lifecycle.lock"


def acquire_lifecycle_lock(logical_dir: Path, *, timeout_s: float = 30.0) -> LifecycleLock:
    logical_dir.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(logical_dir)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()}\n")
            return LifecycleLock(path=lock)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LifecycleError(f"lifecycle lock timeout: {logical_dir.name}")
            time.sleep(0.05)


def validate_assessment_bundle(directory: Path) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise LifecycleError("assessment staging is not a directory")
    json_path = directory / ASSESSMENT_JSON_BASENAME
    html_path = directory / ASSESSMENT_HTML_BASENAME
    heads = directory / "heads"
    if not json_path.is_file() or json_path.is_symlink():
        raise LifecycleError("assessment.json missing or unsafe")
    if not html_path.is_file() or html_path.is_symlink():
        raise LifecycleError("assessment.html missing or unsafe")
    if not heads.is_dir() or heads.is_symlink():
        raise LifecycleError("heads/ missing or unsafe")
    # Require at least one head artifact when heads/ exists (empty is invalid promote).
    head_files = [p for p in heads.iterdir() if p.is_file() and p.suffix == ".json"]
    if not head_files:
        raise LifecycleError("heads/ has no JSON head artifacts")


def validate_eir_bundle(directory: Path) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise LifecycleError("EIR staging is not a directory")
    for name in (EIR_JSON, EIR_HTML):
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise LifecycleError(f"{name} missing or unsafe")


def _rmtree_safe(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise LifecycleError(f"refusing to delete symlink: {path.name}")
    shutil.rmtree(path)


def _replace_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        _rmtree_safe(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def promote_assessment_run(
    *,
    repository_id: str,
    staging_directory: Path,
    base: Path | None = None,
    previous_run_id: str | None = None,
) -> Path:
    """Validate staging, rotate current→previous, promote staging→current."""

    if not is_logical_repository_id(repository_id):
        raise LifecycleError(f"invalid repository_id: {repository_id!r}")
    validate_assessment_bundle(staging_directory)

    logical = assessment_logical_directory(repository_id, base=base)
    lock = acquire_lifecycle_lock(logical)
    try:
        current = logical / SLOT_CURRENT
        previous = logical / SLOT_PREVIOUS

        # Annotate staging manifest with slot metadata before promote.
        _annotate_assessment_manifest(
            staging_directory,
            repository_id=repository_id,
            artifact_slot=SLOT_CURRENT,
            previous_assessment_run_id=_read_run_id(current) if current.exists() else previous_run_id,
        )

        if previous.exists():
            _rmtree_safe(previous)
        if current.exists():
            _annotate_assessment_manifest(
                current,
                repository_id=repository_id,
                artifact_slot=SLOT_PREVIOUS,
                previous_assessment_run_id=None,
            )
            _replace_dir(current, previous)
        _replace_dir(staging_directory, current)
        refresh_artifact_index(base=base)
        return current
    finally:
        lock.release()


def promote_intelligence_run(
    *,
    portfolio_id: str,
    staging_directory: Path,
    base: Path | None = None,
) -> Path:
    if not is_logical_portfolio_id(portfolio_id):
        raise LifecycleError(f"invalid portfolio_id: {portfolio_id!r}")
    validate_eir_bundle(staging_directory)

    logical = intelligence_logical_directory(portfolio_id, base=base)
    lock = acquire_lifecycle_lock(logical)
    try:
        current = logical / SLOT_CURRENT
        previous = logical / SLOT_PREVIOUS
        _annotate_eir_manifest(
            staging_directory,
            portfolio_id=portfolio_id,
            artifact_slot=SLOT_CURRENT,
            previous_portfolio_run_id=_read_eir_run_id(current) if current.exists() else None,
        )
        if previous.exists():
            _rmtree_safe(previous)
        if current.exists():
            _annotate_eir_manifest(
                current,
                portfolio_id=portfolio_id,
                artifact_slot=SLOT_PREVIOUS,
                previous_portfolio_run_id=None,
            )
            _replace_dir(current, previous)
        _replace_dir(staging_directory, current)
        refresh_artifact_index(base=base)
        return current
    finally:
        lock.release()


def discard_staging(staging_directory: Path) -> None:
    """Clean failed staging without touching current/previous."""

    if not staging_directory.exists():
        return
    resolved = staging_directory.resolve()
    parts = resolved.parts
    # Allow temporary/assessment-runs and custom <output>/.staging/
    if TEMPORARY_DIRNAME not in parts and ".staging" not in parts:
        raise LifecycleError("refuse to discard non-staging path")
    _rmtree_safe(staging_directory)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_run_id(slot_dir: Path) -> str | None:
    data = _read_json(slot_dir / ASSESSMENT_JSON_BASENAME)
    for key in ("assessment_run_id", "assessment_id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _read_eir_run_id(slot_dir: Path) -> str | None:
    data = _read_json(slot_dir / EIR_JSON)
    for key in ("portfolio_run_id", "run_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _annotate_assessment_manifest(
    directory: Path,
    *,
    repository_id: str,
    artifact_slot: ArtifactSlot,
    previous_assessment_run_id: str | None,
) -> None:
    path = directory / ASSESSMENT_JSON_BASENAME
    data = _read_json(path)
    run_id = data.get("assessment_run_id") or data.get("assessment_id") or directory.name
    data["repository_id"] = repository_id
    data["repository_name"] = data.get("repository_name") or data.get("repository") or repository_id
    data["assessment_run_id"] = run_id
    data["assessment_id"] = data.get("assessment_id") or run_id
    data["artifact_slot"] = artifact_slot
    if previous_assessment_run_id:
        data["previous_assessment_run_id"] = previous_assessment_run_id
    elif "previous_assessment_run_id" in data and artifact_slot == SLOT_PREVIOUS:
        # Keep existing previous pointer when demoting.
        pass
    _write_json(path, data)


def _annotate_eir_manifest(
    directory: Path,
    *,
    portfolio_id: str,
    artifact_slot: ArtifactSlot,
    previous_portfolio_run_id: str | None,
) -> None:
    path = directory / EIR_JSON
    data = _read_json(path)
    run_id = data.get("portfolio_run_id") or data.get("run_id") or directory.name
    data["portfolio_id"] = portfolio_id
    data["portfolio_name"] = data.get("portfolio_name") or portfolio_id
    data["portfolio_run_id"] = run_id
    data["artifact_slot"] = artifact_slot
    if previous_portfolio_run_id:
        data["previous_portfolio_run_id"] = previous_portfolio_run_id
    _write_json(path, data)


def refresh_artifact_index(*, base: Path | None = None) -> Path:
    """Rebuild manifests/artifact-manifest.json from current/previous slots."""

    root = ensure_artifact_tree(base)
    repositories: dict[str, Any] = {}
    assessments_root = root / ASSESSMENTS_DIRNAME
    if assessments_root.is_dir():
        for entry in sorted(assessments_root.iterdir()):
            if entry.is_symlink() or not entry.is_dir():
                continue
            if is_assessment_run_id(entry.name):
                continue  # legacy flat run dirs — ignored in new index
            if not is_logical_repository_id(entry.name):
                continue
            current = entry / SLOT_CURRENT
            previous = entry / SLOT_PREVIOUS
            repositories[entry.name] = {
                "repository_id": entry.name,
                "repository_name": _read_json(current / ASSESSMENT_JSON_BASENAME).get(
                    "repository_name"
                )
                or entry.name,
                "current_run_id": _read_run_id(current) if current.exists() else None,
                "previous_run_id": _read_run_id(previous) if previous.exists() else None,
                "current_path": f"assessments/{entry.name}/current",
                "previous_path": f"assessments/{entry.name}/previous"
                if previous.exists()
                else None,
            }

    portfolios: dict[str, Any] = {}
    intel_root = root / INTELLIGENCE_DIRNAME
    if intel_root.is_dir():
        for entry in sorted(intel_root.iterdir()):
            if entry.is_symlink() or not entry.is_dir():
                continue
            if not is_logical_portfolio_id(entry.name):
                continue
            current = entry / SLOT_CURRENT
            previous = entry / SLOT_PREVIOUS
            current_data = _read_json(current / EIR_JSON) if current.exists() else {}
            previous_data = _read_json(previous / EIR_JSON) if previous.exists() else {}
            portfolios[entry.name] = {
                "portfolio_id": entry.name,
                "portfolio_name": current_data.get("portfolio_name") or entry.name,
                "current_run_id": _read_eir_run_id(current) if current.exists() else None,
                "previous_run_id": _read_eir_run_id(previous) if previous.exists() else None,
                "current_repository_count": current_data.get("repository_count"),
                "previous_repository_count": previous_data.get("repository_count"),
                "current_path": f"intelligence/{entry.name}/current",
                "previous_path": f"intelligence/{entry.name}/previous"
                if previous.exists()
                else None,
            }

    payload = {
        "schema": "codestrata-artifact-manifest:1.1.0",
        "artifact_root": ".codestrata-artifacts",
        "repositories": repositories,
        "portfolios": portfolios,
        "boundaries": {
            "data_lake_upload_forbidden": True,
            "run_ids_are_metadata": True,
            "assessment_versions_per_repository": MAX_VERSIONS,
            "engineering_intelligence_versions_per_portfolio": MAX_VERSIONS,
        },
    }
    out = manifests_directory(base=base) / ARTIFACT_MANIFEST_BASENAME
    _write_json(out, payload)
    return out


def resolve_current_assessment_html(
    *,
    repository_id: str | None = None,
    repository_name: str | None = None,
    source_url: str | None = None,
    base: Path | None = None,
    assessments_root: Path | None = None,
) -> Path | None:
    """Locate ``current/assessment.html`` for a repository (CLI/VS Code)."""

    rid = repository_id
    if not rid:
        rid = resolve_repository_artifact_id(
            repository_name=repository_name or "repository",
            source_url=source_url,
        )
    if assessments_root is not None:
        candidate = assessments_root / rid / SLOT_CURRENT / ASSESSMENT_HTML_BASENAME
    else:
        candidate = assessment_slot_directory(rid, SLOT_CURRENT, base=base) / ASSESSMENT_HTML_BASENAME
    if candidate.is_file() and not candidate.is_symlink():
        return candidate
    return None


__all__ = [
    "EIR_HTML",
    "EIR_JSON",
    "LifecycleError",
    "LifecycleLock",
    "MAX_VERSIONS",
    "SLOT_CURRENT",
    "SLOT_PREVIOUS",
    "acquire_lifecycle_lock",
    "assessment_logical_directory",
    "assessment_slot_directory",
    "discard_staging",
    "intelligence_logical_directory",
    "intelligence_slot_directory",
    "promote_assessment_run",
    "promote_intelligence_run",
    "refresh_artifact_index",
    "resolve_current_assessment_html",
    "resolve_portfolio_artifact_id",
    "resolve_repository_artifact_id",
    "staging_assessment_directory",
    "staging_intelligence_directory",
    "validate_assessment_bundle",
    "validate_eir_bundle",
]
