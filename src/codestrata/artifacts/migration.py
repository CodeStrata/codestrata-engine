"""Migration helpers from legacy ``reports/`` layout (Slice 17.12)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from codestrata.artifacts.heads import ASSESSMENT_HEAD_SPECS, heads_directory
from codestrata.artifacts.layout import (
    ASSESSMENTS_DIRNAME,
    artifact_root,
    ensure_artifact_tree,
    sanitize_repository_slug,
)
from codestrata.artifacts.manifest import (
    ASSESSMENT_HTML_BASENAME,
    ASSESSMENT_JSON_BASENAME,
    build_assessment_manifest,
    write_assessment_manifest,
)

LEGACY_REPORTS_DIRECTORY_NAME = "reports"
LEGACY_HTML = "report.html"
LEGACY_JSON = "report.json"


@dataclass
class MigrationResult:
    migrated_runs: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def migrate_legacy_report_tree(
    *,
    workspace: Path | None = None,
    legacy_reports: Path | None = None,
    copy: bool = True,
) -> MigrationResult:
    """Migrate ``reports/<repo>/<stamp>/`` runs into ``.codestrata-artifacts/assessments/``.

    Does not delete legacy trees by default (``copy=True``). When ``copy=False``,
    moves files. Never uploads artifacts.
    """

    base = workspace or Path.cwd()
    source = legacy_reports or (base / LEGACY_REPORTS_DIRECTORY_NAME)
    result = MigrationResult()
    if not source.is_dir():
        return result

    ensure_artifact_tree(base)
    assessments_root = artifact_root(base) / ASSESSMENTS_DIRNAME

    for repo_dir in sorted(path for path in source.iterdir() if path.is_dir() and not path.is_symlink()):
        if repo_dir.name == "verification":
            # Handled by validation migration.
            continue
        for run_dir in sorted(path for path in repo_dir.iterdir() if path.is_dir() and not path.is_symlink()):
            if not (run_dir / LEGACY_HTML).is_file():
                result.skipped.append(str(run_dir.relative_to(base)) if _is_relative(run_dir, base) else str(run_dir))
                continue
            run_id = f"{sanitize_repository_slug(repo_dir.name)}-{run_dir.name}"
            dest = assessments_root / run_id
            try:
                _migrate_one_run(run_dir, dest, repository=repo_dir.name, run_id=run_id, copy=copy)
                result.migrated_runs.append(run_id)
            except Exception as error:  # noqa: BLE001 — collect and continue
                result.errors.append(f"{run_id}: {error}")
    return result


def migrate_legacy_verification_tree(
    *,
    workspace: Path | None = None,
    legacy_verification: Path | None = None,
    copy: bool = True,
) -> MigrationResult:
    """Move ``reports/verification/<suite>/`` into validation/suites/."""

    from codestrata.artifacts.layout import VALIDATION_DIRNAME, VALIDATION_SUITES_DIRNAME

    base = workspace or Path.cwd()
    source = legacy_verification or (base / LEGACY_REPORTS_DIRECTORY_NAME / "verification")
    result = MigrationResult()
    if not source.is_dir():
        return result
    ensure_artifact_tree(base)
    dest_root = artifact_root(base) / VALIDATION_DIRNAME / VALIDATION_SUITES_DIRNAME
    for suite_dir in sorted(path for path in source.iterdir() if path.is_dir() and not path.is_symlink()):
        dest = dest_root / suite_dir.name
        try:
            if dest.exists():
                result.skipped.append(suite_dir.name)
                continue
            if copy:
                shutil.copytree(suite_dir, dest)
            else:
                shutil.move(str(suite_dir), str(dest))
            result.migrated_runs.append(suite_dir.name)
        except Exception as error:  # noqa: BLE001
            result.errors.append(f"{suite_dir.name}: {error}")
    return result


def _migrate_one_run(
    source: Path,
    dest: Path,
    *,
    repository: str,
    run_id: str,
    copy: bool,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    heads = heads_directory(dest)
    heads.mkdir(parents=True, exist_ok=True)

    # HTML
    legacy_html = source / LEGACY_HTML
    if legacy_html.is_file():
        _transfer(legacy_html, dest / ASSESSMENT_HTML_BASENAME, copy=copy)

    # Heads from legacy sidecars
    for spec in ASSESSMENT_HEAD_SPECS:
        legacy = source / spec.legacy_filename
        if legacy.is_file():
            _transfer(legacy, heads / spec.heads_basename, copy=copy)

    # Other runtime files (findings, graphs, etc.)
    skip_names = {
        LEGACY_HTML,
        LEGACY_JSON,
        ASSESSMENT_HTML_BASENAME,
        ASSESSMENT_JSON_BASENAME,
        *(spec.legacy_filename for spec in ASSESSMENT_HEAD_SPECS),
    }
    for path in source.iterdir():
        if path.name in skip_names or path.name == "heads":
            continue
        target = dest / path.name
        if path.is_dir():
            if copy:
                if target.exists():
                    continue
                shutil.copytree(path, target)
            else:
                shutil.move(str(path), str(target))
        elif path.is_file():
            _transfer(path, target, copy=copy)

    # Manifest (lightweight). Prefer summary hints from legacy report.json when present.
    summary = None
    scores: dict = {}
    findings_summary: dict = {}
    git_metadata: dict = {}
    legacy_json = source / LEGACY_JSON
    if legacy_json.is_file():
        try:
            payload = json.loads(legacy_json.read_text(encoding="utf-8"))
            assessment = payload.get("assessment") if isinstance(payload, dict) else None
            if isinstance(assessment, dict):
                summary = assessment.get("summary") or assessment.get("title")
                if isinstance(assessment.get("scores"), dict):
                    scores = assessment["scores"]
                if isinstance(assessment.get("findings_summary"), dict):
                    findings_summary = assessment["findings_summary"]
            if isinstance(payload, dict) and isinstance(payload.get("repository"), dict):
                git_metadata = {
                    key: payload["repository"].get(key)
                    for key in ("commit", "branch", "remote")
                    if payload["repository"].get(key) is not None
                }
        except (OSError, json.JSONDecodeError):
            pass

    manifest = build_assessment_manifest(
        assessment_id=run_id,
        repository=repository,
        run_directory=dest,
        overall_summary=str(summary) if summary is not None else None,
        overall_scores=scores,
        findings_summary=findings_summary,
        git_metadata=git_metadata,
    )
    write_assessment_manifest(dest / ASSESSMENT_JSON_BASENAME, manifest)


def _transfer(source: Path, dest: Path, *, copy: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copy2(source, dest)
    else:
        shutil.move(str(source), str(dest))


def _is_relative(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
