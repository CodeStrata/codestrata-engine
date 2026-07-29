"""Repository onboarding orchestration (Phase 5.11).

Coordinates existing assessment, knowledge, and reporting services.
Does not reimplement scanning, rules, indexing, retrieval, or roadmap logic.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from codestrata import RULESET_VERSION, __version__
from codestrata.application.assessment.service import (
    DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    AssessmentApplicationService,
    AssessmentCommandError,
    AssessmentCommandResult,
)
from codestrata.application.onboarding.manifest import write_onboarding_manifest
from codestrata.application.onboarding.settings_overrides import apply_onboarding_settings
from codestrata.application.onboarding.validation import (
    validate_config_path,
    validate_output_directory,
    validate_provider_against_settings,
    validate_repository_source,
)
from codestrata.config import load_settings
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.onboarding.enums import OnboardingStatus
from codestrata.domain.onboarding.errors import OnboardingError
from codestrata.domain.onboarding.models import (
    OnboardingResult,
    OnboardingSummary,
    RepositoryOnboardingManifest,
)
from codestrata.reporting.assessment_json import ASSESSMENT_JSON_REPORT_VERSION
from codestrata.reporting.modernization_models import AssessmentMode

AssessRunner = Callable[..., AssessmentCommandResult]


class OnboardingApplicationService:
    """Guided repository onboarding over existing CodeStrata services."""

    def __init__(
        self,
        *,
        assess_runner: AssessRunner | None = None,
    ) -> None:
        self._assess_runner = assess_runner or self._default_assess_runner

    def onboard(
        self,
        repository: str,
        *,
        config_path: Path = Path("codestrata.toml"),
        output_directory: Path = DEFAULT_ASSESS_OUTPUT_DIRECTORY,
        force_reindex: bool = False,
        skip_report: bool = False,
        skip_index: bool = False,
        provider: str | None = None,
        settings: CodestrataSettings | None = None,
        mode: AssessmentMode = AssessmentMode.DETERMINISTIC,
    ) -> OnboardingResult:
        """Run the end-to-end onboarding workflow for one repository."""

        started = perf_counter()
        warnings: list[str] = []

        if settings is None:
            config = validate_config_path(config_path)
            loaded = load_settings(config)
        else:
            config = config_path
            loaded = settings
        output = validate_output_directory(output_directory)
        repo = validate_repository_source(repository)

        indexing_enabled = not skip_index
        resolved_provider = validate_provider_against_settings(
            loaded,
            provider_override=provider,
            indexing_enabled=indexing_enabled,
        )
        onboard_settings = apply_onboarding_settings(
            loaded,
            skip_index=skip_index,
            provider=resolved_provider,
            enable_roadmap=True,
        )

        existing_repository = self._repository_already_registered(onboard_settings, repo)

        try:
            assessment = self._assess_runner(
                repo=repo,
                output_directory=output,
                mode=mode,
                config_path=config if settings is None else config_path,
                settings=onboard_settings,
                write_reports=not skip_report,
                force_reindex=force_reindex,
            )
        except AssessmentCommandError as error:
            raise OnboardingError(
                f"Assessment failed during onboarding: {error}\n\n"
                "Fix: resolve the assessment error (see message above), then re-run "
                "`codestrata onboard`."
            ) from error
        except OnboardingError:
            raise
        except Exception as error:  # noqa: BLE001 - application boundary
            raise OnboardingError(
                f"Unexpected onboarding failure: {error}\n\n"
                "Fix: re-run with --verbose and inspect the stack trace."
            ) from error

        languages, frameworks = self._technologies_from_report(
            assessment.json_report_path if not skip_report else None,
            assessment,
        )
        if skip_index and assessment.knowledge_vector_count:
            warnings.append("Index counts present despite --skip-index; check configuration.")

        chunks_indexed = int(assessment.knowledge_vector_count or 0)
        if skip_index:
            chunks_indexed = 0

        reports: list[str] = []
        html_path: str | None = None
        json_path: str | None = None
        if not skip_report:
            if assessment.html_report_path.is_file():
                reports.append(str(assessment.html_report_path))
                html_path = str(assessment.html_report_path)
            if assessment.json_report_path.is_file():
                reports.append(str(assessment.json_report_path))
                json_path = str(assessment.json_report_path)
        else:
            warnings.append("Report generation skipped (--skip-report).")

        if skip_index:
            warnings.append("Knowledge indexing skipped (--skip-index).")
        elif assessment.knowledge_index_status in {None, "disabled", "failed"}:
            warnings.append(
                "Knowledge index was not produced; check embedding/indexing "
                f"status={assessment.knowledge_index_status!r}."
            )

        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        status = OnboardingStatus.SUCCEEDED
        if warnings and (
            skip_index
            or skip_report
            or assessment.knowledge_index_status in {"failed", "disabled"}
        ):
            # Partial when user intentionally skipped stages or index soft-failed.
            if assessment.knowledge_index_status == "failed":
                status = OnboardingStatus.PARTIAL

        roadmap_count = int(assessment.roadmap_report_initiative_count or 0)
        findings_count = int(
            assessment.rule_finding_count
            if assessment.rule_finding_count is not None
            else assessment.findings_count
        )
        recommendations_count = int(
            assessment.phase3_recommendation_count
            if assessment.phase3_recommendation_count is not None
            else assessment.recommendations_count
        )

        scan_id = assessment.knowledge_run_id or assessment.run_directory.name
        repository_id = assessment.knowledge_repository_id or f"local:{assessment.repository_name}"

        manifest = RepositoryOnboardingManifest(
            repository_id=repository_id,
            repository_name=assessment.repository_name,
            scan_id=scan_id,
            assessment_version=RULESET_VERSION,
            report_version=ASSESSMENT_JSON_REPORT_VERSION,
            embedding_provider=(
                resolved_provider
                if indexing_enabled
                else onboard_settings.knowledge.embedding.provider
            ),
            embedding_model=(
                onboard_settings.knowledge.embedding.model if indexing_enabled else None
            ),
            index_fingerprint=assessment.knowledge_index_fingerprint,
            languages_detected=tuple(languages),
            frameworks_detected=tuple(frameworks),
            scan_timestamp=datetime.now(UTC),
            codestrata_version=__version__,
            findings_count=findings_count,
            recommendations_count=recommendations_count,
            roadmap_initiative_count=roadmap_count,
            chunks_indexed=chunks_indexed,
            knowledge_corpus_id=assessment.knowledge_corpus_id,
            knowledge_snapshot_id=assessment.knowledge_snapshot_id,
            html_report_path=html_path,
            json_report_path=json_path,
            run_directory=str(assessment.run_directory),
            status=status,
            metadata={
                "force_reindex": "true" if force_reindex else "false",
                "skip_report": "true" if skip_report else "false",
                "skip_index": "true" if skip_index else "false",
                "knowledge_index_status": str(assessment.knowledge_index_status or ""),
            },
        )
        manifest_path = write_onboarding_manifest(manifest, assessment.run_directory)

        summary = OnboardingSummary(
            repository_analyzed=assessment.repository_name,
            languages_detected=tuple(languages),
            frameworks_detected=tuple(frameworks),
            findings_count=findings_count,
            recommendations_count=recommendations_count,
            roadmap_initiative_count=roadmap_count,
            chunks_indexed=chunks_indexed,
            reports_generated=tuple(reports),
            elapsed_ms=elapsed_ms,
            knowledge_repository_id=assessment.knowledge_repository_id,
            knowledge_run_id=assessment.knowledge_run_id,
            status=status,
        )
        return OnboardingResult(
            status=status,
            summary=summary,
            manifest=manifest,
            manifest_path=str(manifest_path),
            assessment_run_directory=str(assessment.run_directory),
            warnings=tuple(warnings),
            existing_repository=existing_repository,
        )

    @staticmethod
    def _default_assess_runner(**kwargs: Any) -> AssessmentCommandResult:
        return AssessmentApplicationService().run(**kwargs)

    @staticmethod
    def _repository_already_registered(settings: CodestrataSettings, repository: str) -> bool:
        """Best-effort check whether the knowledge store already knows this repo."""

        path = Path(repository)
        if not path.exists():
            return False
        try:
            from codestrata.application.knowledge.models import RepositoryAliasType
            from codestrata.infrastructure.knowledge_store.factory import create_knowledge_store

            store = create_knowledge_store(settings=settings)
            resolved = path.expanduser().resolve()
            record = store.registry.resolve_alias(
                RepositoryAliasType.LOCAL_PATH,
                str(resolved),
            )
            return record is not None
        except Exception:  # noqa: BLE001 - probe must not fail onboard
            return False

    @staticmethod
    def _technologies_from_report(
        json_report_path: Path | None,
        assessment: AssessmentCommandResult,
    ) -> tuple[list[str], list[str]]:
        languages: list[str] = []
        frameworks: list[str] = []
        if json_report_path is not None and json_report_path.is_file():
            try:
                payload = json.loads(json_report_path.read_text(encoding="utf-8"))
                assessment_block = payload.get("assessment") or {}
                for item in assessment_block.get("technologies") or []:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    category = str(item.get("category") or "").strip().lower()
                    if not name:
                        continue
                    if category == "language":
                        languages.append(name)
                    elif category == "framework":
                        frameworks.append(name)
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        if not languages and not frameworks and assessment.technologies_count:
            # Report skipped or unreadable — leave empty rather than inventing names.
            pass
        return sorted(set(languages)), sorted(set(frameworks))


def run_onboarding(
    repository: str,
    *,
    config_path: Path = Path("codestrata.toml"),
    output_directory: Path = DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    force_reindex: bool = False,
    skip_report: bool = False,
    skip_index: bool = False,
    provider: str | None = None,
    settings: CodestrataSettings | None = None,
) -> OnboardingResult:
    """Module-level entrypoint used by the CLI."""

    return OnboardingApplicationService().onboard(
        repository,
        config_path=config_path,
        output_directory=output_directory,
        force_reindex=force_reindex,
        skip_report=skip_report,
        skip_index=skip_index,
        provider=provider,
        settings=settings,
    )
