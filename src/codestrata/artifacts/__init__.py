"""Authoritative local runtime artifact layout (Slice 17.12 / 17.15).

All Engine-generated assessment, intelligence, validation, and temporary
runtime outputs belong under ``.codestrata-artifacts/``.
"""

from __future__ import annotations

from codestrata.artifacts.heads import (
    ASSESSMENT_HEAD_SPECS,
    head_basename_for_legacy_filename,
    heads_directory,
    resolve_head_path,
)
from codestrata.artifacts.layout import (
    ARTIFACT_ROOT_NAME,
    AssessmentRunPaths,
    artifact_root,
    ensure_artifact_tree,
    intelligence_run_directory,
    manifests_directory,
    temporary_directory,
    validation_logs_directory,
    validation_repositories_directory,
    validation_suite_directory,
)
from codestrata.artifacts.lifecycle import (
    discard_staging,
    promote_assessment_run,
    promote_intelligence_run,
    refresh_artifact_index,
    resolve_current_assessment_html,
)
from codestrata.artifacts.lifecycle_migration import migrate_report_lifecycle
from codestrata.artifacts.manifest import (
    ASSESSMENT_HTML_BASENAME,
    ASSESSMENT_JSON_BASENAME,
    ARTIFACT_MANIFEST_BASENAME,
    build_assessment_manifest,
    build_artifact_index_manifest,
    write_assessment_manifest,
    write_artifact_index_manifest,
)
from codestrata.artifacts.migration import (
    LEGACY_REPORTS_DIRECTORY_NAME,
    migrate_legacy_report_tree,
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

__all__ = [
    "ARTIFACT_MANIFEST_BASENAME",
    "ARTIFACT_ROOT_NAME",
    "ASSESSMENT_HEAD_SPECS",
    "ASSESSMENT_HTML_BASENAME",
    "ASSESSMENT_JSON_BASENAME",
    "AssessmentRunPaths",
    "LEGACY_REPORTS_DIRECTORY_NAME",
    "RELEASE_VALIDATION_PORTFOLIO_ID",
    "artifact_root",
    "build_assessment_manifest",
    "build_artifact_index_manifest",
    "build_github_repository_artifact_id",
    "build_local_repository_artifact_id",
    "discard_staging",
    "ensure_artifact_tree",
    "head_basename_for_legacy_filename",
    "heads_directory",
    "intelligence_run_directory",
    "manifests_directory",
    "migrate_legacy_report_tree",
    "migrate_report_lifecycle",
    "promote_assessment_run",
    "promote_intelligence_run",
    "refresh_artifact_index",
    "resolve_current_assessment_html",
    "resolve_head_path",
    "resolve_portfolio_artifact_id",
    "resolve_repository_artifact_id",
    "temporary_directory",
    "validation_logs_directory",
    "validation_repositories_directory",
    "validation_suite_directory",
    "write_assessment_manifest",
    "write_artifact_index_manifest",
]
