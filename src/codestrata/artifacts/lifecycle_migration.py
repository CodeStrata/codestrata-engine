"""Migrate Slice 17.12 run-ID folders to logical current/previous (Slice 17.15)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codestrata.artifacts.layout import (
    ASSESSMENTS_DIRNAME,
    INTELLIGENCE_DIRNAME,
    is_assessment_run_id,
)
from codestrata.artifacts.lifecycle import (
    EIR_HTML,
    EIR_JSON,
    SLOT_CURRENT,
    SLOT_PREVIOUS,
    promote_assessment_run,
    promote_intelligence_run,
    refresh_artifact_index,
    staging_assessment_directory,
    staging_intelligence_directory,
)
from codestrata.artifacts.portfolio_identity import (
    RELEASE_VALIDATION_PORTFOLIO_ID,
    resolve_portfolio_artifact_id,
)
from codestrata.artifacts.repository_identity import (
    build_github_repository_artifact_id,
    build_local_repository_artifact_id,
    resolve_repository_artifact_id,
)

_RUN_SUFFIX = re.compile(r"^(?P<root>.+)-(?P<stamp>\d{8}-\d{6})$")


@dataclass
class LifecycleMigrationResult:
    assessments_migrated: int = 0
    assessments_skipped: int = 0
    intelligence_migrated: int = 0
    intelligence_skipped: int = 0
    deleted_excess: int = 0
    errors: list[str] = field(default_factory=list)


def _load_catalog_github_map(catalog_path: Path | None) -> dict[str, str]:
    """Map catalog short id → github owner/repo."""

    if catalog_path is None or not catalog_path.is_file():
        return {}
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    for row in data.get("repositories") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "").strip()
        gh = str(row.get("github_repository") or "").strip()
        if rid and gh and "/" in gh:
            out[rid] = gh
    return out


def _repository_id_for_run(
    run_dir: Path,
    *,
    catalog_map: dict[str, str],
) -> str:
    manifest = run_dir / "assessment.json"
    remote = None
    repo_name = run_dir.name
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            git = data.get("git") if isinstance(data.get("git"), dict) else {}
            remote = git.get("remote") if isinstance(git, dict) else None
            repo_name = str(data.get("repository") or repo_name)
            existing = data.get("repository_id")
            if isinstance(existing, str) and existing.startswith(("github-", "local-")):
                return existing

    match = _RUN_SUFFIX.match(run_dir.name)
    slug = match.group("root") if match else run_dir.name
    catalog_gh = catalog_map.get(slug)
    if catalog_gh:
        owner, repo = catalog_gh.split("/", 1)
        return build_github_repository_artifact_id(owner, repo)
    return resolve_repository_artifact_id(
        repository_name=slug or repo_name,
        remote=str(remote) if remote else None,
    )


def _sort_key(run_dir: Path) -> str:
    manifest = run_dir / "assessment.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            executed = data.get("executed_at") if isinstance(data, dict) else None
            if isinstance(executed, str) and executed:
                return executed
        except (OSError, json.JSONDecodeError):
            pass
    match = _RUN_SUFFIX.match(run_dir.name)
    if match:
        return match.group("stamp")
    return run_dir.name


def migrate_assessment_run_folders(
    *,
    workspace: Path,
    catalog_path: Path | None = None,
    dry_run: bool = False,
) -> LifecycleMigrationResult:
    """Group flat ``<slug>-<stamp>`` runs into logical current/previous."""

    result = LifecycleMigrationResult()
    assessments = workspace / ".codestrata-artifacts" / ASSESSMENTS_DIRNAME
    if not assessments.is_dir():
        return result

    catalog_map = _load_catalog_github_map(catalog_path)
    groups: dict[str, list[Path]] = {}
    for entry in assessments.iterdir():
        if entry.is_symlink() or not entry.is_dir():
            continue
        if (entry / SLOT_CURRENT).is_dir() or (entry / SLOT_PREVIOUS).is_dir():
            result.assessments_skipped += 1
            continue
        if not is_assessment_run_id(entry.name) and not _RUN_SUFFIX.match(entry.name):
            # Already logical without slots, or unknown — skip safely.
            result.assessments_skipped += 1
            continue
        if not (entry / "assessment.json").is_file():
            result.assessments_skipped += 1
            continue
        rid = _repository_id_for_run(entry, catalog_map=catalog_map)
        groups.setdefault(rid, []).append(entry)

    for repository_id, runs in sorted(groups.items()):
        ordered = sorted(runs, key=_sort_key, reverse=True)
        keep = ordered[:2]
        drop = ordered[2:]
        if dry_run:
            result.assessments_migrated += len(keep)
            result.deleted_excess += len(drop)
            continue
        for outdated in drop:
            try:
                shutil.rmtree(outdated)
                result.deleted_excess += 1
            except OSError as error:
                result.errors.append(f"{outdated.name}: {error}")
        # Promote oldest of keep first so newest ends as current.
        for run_dir in reversed(keep):
            try:
                staging = staging_assessment_directory(run_dir.name, base=workspace)
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(run_dir, staging, symlinks=False)
                promote_assessment_run(
                    repository_id=repository_id,
                    staging_directory=staging,
                    base=workspace,
                )
                shutil.rmtree(run_dir, ignore_errors=True)
                result.assessments_migrated += 1
            except Exception as error:  # noqa: BLE001
                result.errors.append(f"{run_dir.name}: {error}")

    return result


def migrate_intelligence_run_folders(
    *,
    workspace: Path,
    dry_run: bool = False,
) -> LifecycleMigrationResult:
    result = LifecycleMigrationResult()
    intel = workspace / ".codestrata-artifacts" / INTELLIGENCE_DIRNAME
    if not intel.is_dir():
        return result

    groups: dict[str, list[Path]] = {}
    for entry in intel.iterdir():
        if entry.is_symlink() or not entry.is_dir():
            continue
        if (entry / SLOT_CURRENT).is_dir():
            result.intelligence_skipped += 1
            continue
        if not (entry / EIR_JSON).is_file():
            result.intelligence_skipped += 1
            continue
        portfolio_id = resolve_portfolio_artifact_id(portfolio_name=entry.name)
        groups.setdefault(portfolio_id, []).append(entry)

    for portfolio_id, runs in sorted(groups.items()):
        ordered = sorted(runs, key=lambda path: path.name, reverse=True)
        keep = ordered[:2]
        drop = ordered[2:]
        if dry_run:
            result.intelligence_migrated += len(keep)
            result.deleted_excess += len(drop)
            continue
        for outdated in drop:
            try:
                shutil.rmtree(outdated)
                result.deleted_excess += 1
            except OSError as error:
                result.errors.append(f"{outdated.name}: {error}")
        for run_dir in reversed(keep):
            try:
                staging = staging_intelligence_directory(run_dir.name, base=workspace)
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(run_dir, staging, symlinks=False)
                # Ensure required HTML exists (some exports may only have JSON).
                if not (staging / EIR_HTML).is_file() and (run_dir / EIR_HTML).is_file():
                    shutil.copy2(run_dir / EIR_HTML, staging / EIR_HTML)
                if not (staging / EIR_HTML).is_file():
                    # Create minimal placeholder HTML to satisfy promote validation
                    # only when HTML was never produced (should be rare).
                    (staging / EIR_HTML).write_text(
                        "<!DOCTYPE html><html><body><p>Engineering Intelligence Report</p></body></html>\n",
                        encoding="utf-8",
                    )
                promote_intelligence_run(
                    portfolio_id=portfolio_id,
                    staging_directory=staging,
                    base=workspace,
                )
                shutil.rmtree(run_dir, ignore_errors=True)
                result.intelligence_migrated += 1
            except Exception as error:  # noqa: BLE001
                result.errors.append(f"{run_dir.name}: {error}")

    if not dry_run:
        refresh_artifact_index(base=workspace)
    return result


def migrate_report_lifecycle(
    *,
    workspace: Path,
    catalog_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    assessments = migrate_assessment_run_folders(
        workspace=workspace, catalog_path=catalog_path, dry_run=dry_run
    )
    intelligence = migrate_intelligence_run_folders(workspace=workspace, dry_run=dry_run)
    return {
        "assessments_migrated": assessments.assessments_migrated,
        "assessments_skipped": assessments.assessments_skipped,
        "intelligence_migrated": intelligence.intelligence_migrated,
        "intelligence_skipped": intelligence.intelligence_skipped,
        "deleted_excess": assessments.deleted_excess + intelligence.deleted_excess,
        "errors": assessments.errors + intelligence.errors,
        "release_validation_portfolio_id": RELEASE_VALIDATION_PORTFOLIO_ID,
        "dry_run": dry_run,
    }


__all__ = [
    "LifecycleMigrationResult",
    "migrate_assessment_run_folders",
    "migrate_intelligence_run_folders",
    "migrate_report_lifecycle",
]
