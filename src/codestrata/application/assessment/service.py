"""Application-layer orchestration for modernization assessment."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from rich.console import Console

from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.application.knowledge.session import AssessmentKnowledgeSession
from codestrata.config import CodestrataSettings, configured_repository_source, load_settings
from codestrata.config.settings import (
    is_github_repository_source as is_github_repository_source_settings,
)
from codestrata.models import AnalysisResult, Repository
from codestrata.reporters.report_paths import (
    DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    ReportPaths,
    create_report_paths,
    format_report_run_timestamp,
    promote_staged_report,
)
from codestrata.reporting import (
    AssessmentMode,
    AssessmentTiming,
    ModernizationReportInput,
    ModernizationReportValidationError,
    write_modernization_assessment_reports,
)
from codestrata.reporting.ai_execution import (
    AI_EXECUTION_FILENAME,
    build_ai_execution_document,
    try_write_ai_execution_artifact,
)
from codestrata.reporting.ai_status import (
    attempt_info_from_metadata,
    customer_failure_message,
    failure_code_for_status,
    stages_for_status,
)
from codestrata.reporting.modernization_models import AIAttemptInfo, AIExecutionStatus
from codestrata.repository_auth.exceptions import (
    RepositoryAccessError,
    UnsupportedRepositoryUrlError,
)
from codestrata.scan_boundary import BoundaryPolicy
from codestrata.services.analysis_service import AnalysisService
from codestrata.services.default_pipeline import create_default_analysis_service
from codestrata.services.graph_assessment import (
    GraphArtifactWriteResult,
    GraphAssessmentPipeline,
    GraphAssessmentPipelineError,
    format_graph_console_summary,
    write_graph_artifacts,
)
from codestrata.services.recommendations import (
    RecommendationEngine,
    RecommendationsArtifactWriteResult,
    write_recommendations_artifact,
)
from codestrata.services.rule_engine import (
    FindingsArtifactWriteResult,
    RuleEngine,
    format_rule_console_summary,
    write_findings_artifact,
)
from codestrata.services.scanners.github_repository_scanner import (
    GitHubRepositoryScanner,
    dispose_ephemeral_repository,
)
from codestrata.services.scanners.local_repository_scanner import LocalRepositoryScanner
from codestrata.static_analysis.exceptions import StaticAnalysisProviderError
from codestrata.static_analysis.models import StaticAnalysisStatus
from codestrata.static_analysis.providers.pmd_discovery import (
    discovery_diagnostic_lines,
    probe_pmd_version,
    resolve_pmd_executable,
)

if TYPE_CHECKING:
    from codestrata.ai.agents import ModernizationAssessmentAgent
    from codestrata.ai.agents.models import ModernizationAssessmentResult
    from codestrata.ai.contracts import LLMAnalysisContextBuilder
    from codestrata.ai.contracts.models import LLMAnalysisContext
    from codestrata.ai.prompts import ModernizationPromptBuilder
    from codestrata.ai.providers.base import AIModelProvider
    from codestrata.domain.ai_enrichment import AiEnrichmentResult

DEFAULT_ASSESS_REPORT_TITLE = "Engineering Assessment"
DEFAULT_ASSESS_TEMPERATURE = 0.0
DEFAULT_ASSESS_MAX_OUTPUT_TOKENS = 5000
CODESTRATA_BEDROCK_MODEL_ID_ENV = "CODESTRATA_BEDROCK_MODEL_ID"

logger = logging.getLogger(__name__)


class AssessmentCommandError(Exception):
    """Assessment failure raised by the application layer."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = 1,
        ai_status: AIExecutionStatus | None = None,
        ai_attempt: AIAttemptInfo | None = None,
        execution_document: dict[str, object] | None = None,
        customer_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.ai_status = ai_status
        self.ai_attempt = ai_attempt
        self.execution_document = execution_document
        self.customer_message = customer_message


class AssessmentCommandResult(BaseModel):
    """Immutable summary returned by a successful assess run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_name: str = Field(min_length=1)
    run_directory: Path
    html_report_path: Path
    json_report_path: Path
    report_path: Path | None = None
    mode: AssessmentMode
    findings_count: int = Field(ge=0)
    technologies_count: int = Field(ge=0)
    recommendations_count: int = Field(ge=0)
    phases_count: int = Field(ge=0)
    ai_executed: bool
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    model_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    duration_ms: float | None = Field(default=None, ge=0.0)
    graphs_directory: Path | None = None
    knowledge_binding_count: int | None = Field(default=None, ge=0)
    repository_graph_node_count: int | None = Field(default=None, ge=0)
    repository_graph_relationship_count: int | None = Field(default=None, ge=0)
    assessment_graph_node_count: int | None = Field(default=None, ge=0)
    assessment_graph_relationship_count: int | None = Field(default=None, ge=0)
    rule_finding_count: int | None = Field(default=None, ge=0)
    rules_evaluated_count: int | None = Field(default=None, ge=0)
    findings_artifact_path: Path | None = None
    phase3_recommendation_count: int | None = Field(default=None, ge=0)
    recommendations_artifact_path: Path | None = None
    architecture_conclusion_count: int | None = Field(default=None, ge=0)
    architecture_conclusions_artifact_path: Path | None = None
    architecture_assessment_status: str | None = None
    architecture_assessment_finding_count: int | None = Field(default=None, ge=0)
    architecture_assessment_artifact_path: Path | None = None
    technical_debt_assessment_status: str | None = None
    technical_debt_assessment_finding_count: int | None = Field(default=None, ge=0)
    technical_debt_assessment_artifact_path: Path | None = None
    dependency_assessment_status: str | None = None
    dependency_assessment_finding_count: int | None = Field(default=None, ge=0)
    dependency_assessment_artifact_path: Path | None = None
    dependency_evidence_status: str | None = None
    dependency_evidence_declaration_count: int | None = Field(default=None, ge=0)
    dependency_evidence_artifact_path: Path | None = None
    repository_sensitive_evidence_status: str | None = None
    repository_sensitive_evidence_artifact_count: int | None = Field(default=None, ge=0)
    repository_sensitive_evidence_configuration_fact_count: int | None = Field(default=None, ge=0)
    repository_sensitive_evidence_artifact_path: Path | None = None
    repository_testing_evidence_status: str | None = None
    repository_testing_evidence_candidate_count: int | None = Field(default=None, ge=0)
    repository_testing_evidence_framework_count: int | None = Field(default=None, ge=0)
    repository_testing_evidence_artifact_path: Path | None = None
    repository_cloud_evidence_status: str | None = None
    repository_cloud_evidence_candidate_count: int | None = Field(default=None, ge=0)
    repository_cloud_evidence_technology_count: int | None = Field(default=None, ge=0)
    repository_cloud_evidence_artifact_path: Path | None = None
    repository_ai_readiness_evidence_status: str | None = None
    repository_ai_readiness_evidence_candidate_count: int | None = Field(default=None, ge=0)
    repository_ai_readiness_evidence_technology_count: int | None = Field(default=None, ge=0)
    repository_ai_readiness_evidence_artifact_path: Path | None = None
    repository_performance_evidence_status: str | None = None
    repository_performance_evidence_candidate_count: int | None = Field(default=None, ge=0)
    repository_performance_evidence_technology_count: int | None = Field(default=None, ge=0)
    repository_performance_evidence_artifact_path: Path | None = None
    security_assessment_status: str | None = None
    security_assessment_finding_count: int | None = Field(default=None, ge=0)
    security_assessment_artifact_path: Path | None = None
    testing_assessment_status: str | None = None
    testing_assessment_finding_count: int | None = Field(default=None, ge=0)
    testing_assessment_artifact_path: Path | None = None
    cloud_assessment_status: str | None = None
    cloud_assessment_finding_count: int | None = Field(default=None, ge=0)
    cloud_assessment_artifact_path: Path | None = None
    ai_readiness_assessment_status: str | None = None
    ai_readiness_assessment_finding_count: int | None = Field(default=None, ge=0)
    ai_readiness_assessment_artifact_path: Path | None = None
    performance_assessment_status: str | None = None
    performance_assessment_finding_count: int | None = Field(default=None, ge=0)
    performance_assessment_artifact_path: Path | None = None
    architecture_report_enabled: bool | None = None
    architecture_report_status: str | None = None
    architecture_report_section_version: str | None = None
    architecture_report_finding_count: int | None = Field(default=None, ge=0)
    architecture_report_conclusion_count: int | None = Field(default=None, ge=0)
    architecture_report_recommendation_group_count: int | None = Field(default=None, ge=0)
    architecture_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    technical_debt_report_enabled: bool | None = None
    technical_debt_report_status: str | None = None
    technical_debt_report_section_version: str | None = None
    technical_debt_report_finding_count: int | None = Field(default=None, ge=0)
    technical_debt_report_conclusion_count: int | None = Field(default=None, ge=0)
    technical_debt_report_hotspot_count: int | None = Field(default=None, ge=0)
    technical_debt_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    dependency_report_enabled: bool | None = None
    dependency_report_status: str | None = None
    dependency_report_section_version: str | None = None
    dependency_report_finding_count: int | None = Field(default=None, ge=0)
    dependency_report_conclusion_count: int | None = Field(default=None, ge=0)
    dependency_report_hotspot_count: int | None = Field(default=None, ge=0)
    dependency_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    security_report_enabled: bool | None = None
    security_report_status: str | None = None
    security_report_section_version: str | None = None
    security_report_finding_count: int | None = Field(default=None, ge=0)
    security_report_conclusion_count: int | None = Field(default=None, ge=0)
    security_report_hotspot_count: int | None = Field(default=None, ge=0)
    security_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    testing_report_enabled: bool | None = None
    testing_report_status: str | None = None
    testing_report_section_version: str | None = None
    testing_report_finding_count: int | None = Field(default=None, ge=0)
    testing_report_conclusion_count: int | None = Field(default=None, ge=0)
    testing_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    cloud_report_enabled: bool | None = None
    cloud_report_status: str | None = None
    cloud_report_section_version: str | None = None
    cloud_report_finding_count: int | None = Field(default=None, ge=0)
    cloud_report_conclusion_count: int | None = Field(default=None, ge=0)
    cloud_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    ai_readiness_report_enabled: bool | None = None
    ai_readiness_report_status: str | None = None
    ai_readiness_report_section_version: str | None = None
    ai_readiness_report_finding_count: int | None = Field(default=None, ge=0)
    ai_readiness_report_conclusion_count: int | None = Field(default=None, ge=0)
    ai_readiness_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    performance_report_enabled: bool | None = None
    performance_report_status: str | None = None
    performance_report_section_version: str | None = None
    performance_report_finding_count: int | None = Field(default=None, ge=0)
    performance_report_conclusion_count: int | None = Field(default=None, ge=0)
    performance_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    roadmap_report_enabled: bool | None = None
    roadmap_report_status: str | None = None
    roadmap_report_section_version: str | None = None
    roadmap_report_initiative_count: int | None = Field(default=None, ge=0)
    roadmap_report_phase_count: int | None = Field(default=None, ge=0)
    roadmap_report_adapter_ms: float | None = Field(default=None, ge=0.0)
    knowledge_repository_id: str | None = None
    knowledge_run_id: str | None = None
    knowledge_snapshot_id: str | None = None
    knowledge_corpus_id: str | None = None
    knowledge_document_count: int | None = Field(default=None, ge=0)
    knowledge_chunk_count: int | None = Field(default=None, ge=0)
    knowledge_corpus_artifact_path: Path | None = None
    knowledge_index_status: str | None = None
    knowledge_vector_count: int | None = Field(default=None, ge=0)
    knowledge_index_artifact_path: Path | None = None
    knowledge_index_fingerprint: str | None = None
    platform_ingest_status: str | None = None
    platform_organization_id: str | None = None
    platform_workspace_id: str | None = None
    platform_repository_id: str | None = None
    platform_assessment_id: str | None = None
    engine_assessment_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_report_path_alias(cls, data: object) -> object:
        """Default ``report_path`` to the HTML report when callers omit it."""

        if not isinstance(data, dict):
            return data
        if data.get("report_path") is None and data.get("html_report_path") is not None:
            return {**data, "report_path": data["html_report_path"]}
        return data


class _RepositoryScanner(Protocol):
    def scan(self, source: str | Path) -> Repository:
        """Scan a repository source and return repository metadata."""


class AssessmentApplicationService:
    """Coordinate end-to-end modernization assessment for any entrypoint.

    Owns orchestration only: repository preparation, scanning, deterministic
    analysis, graphs, rules, recommendations, optional AI enrichment, report
    generation, artifact persistence, and execution status. Business logic
    remains in existing domain and service modules.

    This service must not import Typer or other CLI adapters.
    """

    def run(
        self,
        repo: str | None,
        output_directory: Path,
        *,
        mode: AssessmentMode = AssessmentMode.DETERMINISTIC,
        model_id: str | None = None,
        branch: str | None = None,
        report_title: str = DEFAULT_ASSESS_REPORT_TITLE,
        organization_name: str | None = None,
        max_output_tokens: int = DEFAULT_ASSESS_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_ASSESS_TEMPERATURE,
        max_context_characters: int | None = None,
        pmd_path: str | None = None,
        pmd_profile: str | None = None,
        static_analysis_enabled: bool | None = None,
        config_path: Path = Path("codestrata.toml"),
        profile: str | None = None,
        assessment_activation: str | None = None,
        settings: CodestrataSettings | None = None,
        analysis_service: AnalysisService | None = None,
        provider: AIModelProvider | None = None,
        prompt_builder: ModernizationPromptBuilder | None = None,
        agent: ModernizationAssessmentAgent | None = None,
        scanner: _RepositoryScanner | None = None,
        context_builder: LLMAnalysisContextBuilder | None = None,
        graph_pipeline: GraphAssessmentPipeline | None = None,
        rule_engine: RuleEngine | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        console: Console | None = None,
        clock: Callable[[], datetime] | None = None,
        verbose: bool = False,
        quiet: bool = False,
        json_summary: bool = False,
        knowledge_store: KnowledgeStore | None = None,
        scanned_repository: Repository | None = None,
        write_reports: bool = True,
        force_reindex: bool = False,
    ) -> AssessmentCommandResult:
        """Orchestrate scan → analysis → graph pipeline → optional AI → HTML+JSON reports.

        Repository selection precedence:

        1. Explicit ``repo`` / ``--repo`` argument
        2. ``[repository].path`` from configuration
        3. ``[repository].url`` from configuration
        4. Clear actionable error (never a silent demo repository)

        When ``scanned_repository`` is provided, the scan stage is skipped and that
        repository object is used (Phase 2F.2 incremental stage rebuild).

        ``write_reports`` controls HTML/JSON report file writes (onboarding may skip).
        ``force_reindex`` clears the vector-store scope before indexing when enabled.
        ``quiet`` suppresses stage progress lines.
        ``json_summary`` emits a machine-readable completion object to stdout.
        """

        active_console = console or Console(stderr=False)
        now = clock or (lambda: datetime.now(UTC))
        total_started = perf_counter()

        def stage(message: str) -> None:
            if not quiet:
                # Progress stages: bold label only — no spinners/noise for CI logs.
                active_console.print(f"[bold]{message}[/bold]")

        def warn(message: str) -> None:
            active_console.print(f"[yellow]Warning:[/yellow] {message}")

        try:
            loaded_settings = settings or load_settings(config_path, profile=profile)
        except (FileNotFoundError, ValueError, OSError) as error:
            raise AssessmentCommandError(sanitize_provider_text(str(error))) from error

        from codestrata.benchmark.recorder import BenchmarkRecorder

        benchmark_recorder = BenchmarkRecorder.create(
            enabled=bool(loaded_settings.analysis.runtime.benchmark_collection)
        )
        benchmark_recorder.activate()

        from codestrata.security.filesystem import safe_output_directory

        try:
            output_directory = safe_output_directory(output_directory)
        except (OSError, NotADirectoryError, ValueError) as error:
            benchmark_recorder.deactivate()
            raise AssessmentCommandError(
                f"Invalid --output directory: {sanitize_provider_text(str(error))}"
            ) from error

        if mode == AssessmentMode.AI_ENHANCED and loaded_settings.profile == "local":
            raise AssessmentCommandError(
                "Execution profile 'local' does not allow --with-ai "
                "(no external LLM).\n\n"
                "Fix: use --profile bedrock (or openai for knowledge providers), "
                "or omit --with-ai for deterministic assessment."
            )

        if pmd_profile is not None:
            from codestrata.static_analysis.providers.pmd_profiles import parse_pmd_profile

            try:
                parse_pmd_profile(pmd_profile)
            except ValueError as error:
                raise AssessmentCommandError(sanitize_provider_text(str(error))) from error

        resolved_repo = resolve_assessment_repository(repo, loaded_settings)
        resolved_branch = branch if branch is not None else loaded_settings.repository.branch
        repository_reference = _safe_repository_reference(resolved_repo)

        stage("Initializing...")
        stage("Discovering repository...")
        scan_started = perf_counter()
        repository: Repository | None = None
        try:
            try:
                if scanned_repository is not None:
                    repository = scanned_repository
                else:
                    with benchmark_recorder.stage("repository_discovery"):
                        repository = _scan_repository(
                            resolved_repo,
                            settings=loaded_settings,
                            branch=resolved_branch,
                            scanner=scanner,
                        )
                    if repository is not None:
                        boundary = (repository.metadata or {}).get("scan_boundary")
                        if isinstance(boundary, dict):
                            benchmark_recorder.set_meta("scan_boundary", boundary)
            except AssessmentCommandError:
                raise
            except (
                FileNotFoundError,
                NotADirectoryError,
                UnsupportedRepositoryUrlError,
                RepositoryAccessError,
                OSError,
                ValueError,
            ) as error:
                raise AssessmentCommandError(
                    f"Invalid repository path or URL: {sanitize_provider_text(str(error))}"
                ) from error
            scan_ms = round((perf_counter() - scan_started) * 1000, 2)

            from codestrata.infrastructure.knowledge_store.factory import create_knowledge_store
            from codestrata.infrastructure.knowledge_store.git_revision import (
                observe_repository_revision,
            )

            owned_store = False
            active_knowledge_store: KnowledgeStore
            if knowledge_store is None:
                active_knowledge_store = cast(
                    KnowledgeStore,
                    create_knowledge_store(settings=loaded_settings),
                )
                owned_store = True
            else:
                active_knowledge_store = knowledge_store

            try:
                with AssessmentKnowledgeSession(
                    store=active_knowledge_store,
                    repository=repository,
                    mode=mode,
                    owns_store=owned_store,
                    revision_observer=observe_repository_revision,
                ) as knowledge_session:
                    try:
                        return self._run_assessment_pipeline(
                            repository=repository,
                            loaded_settings=loaded_settings,
                            mode=mode,
                            model_id=model_id,
                            resolved_branch=resolved_branch,
                            report_title=report_title,
                            organization_name=organization_name,
                            max_output_tokens=max_output_tokens,
                            temperature=temperature,
                            max_context_characters=max_context_characters,
                            pmd_path=pmd_path,
                            pmd_profile=pmd_profile,
                            static_analysis_enabled=static_analysis_enabled,
                            analysis_service=analysis_service,
                            provider=provider,
                            prompt_builder=prompt_builder,
                            agent=agent,
                            context_builder=context_builder,
                            graph_pipeline=graph_pipeline,
                            rule_engine=rule_engine,
                            recommendation_engine=recommendation_engine,
                            output_directory=output_directory,
                            repository_reference=repository_reference,
                            scan_ms=scan_ms,
                            total_started=total_started,
                            active_console=active_console,
                            now=now,
                            stage=stage,
                            warn=warn,
                            verbose=verbose,
                            quiet=quiet,
                            json_summary=json_summary,
                            knowledge_session=knowledge_session,
                            write_reports=write_reports,
                            force_reindex=force_reindex,
                            config_path=config_path,
                            assessment_activation=assessment_activation,
                        )
                    except AssessmentCommandError as error:
                        knowledge_session.fail(
                            error_code="ASSESSMENT_FAILED",
                            error_message=sanitize_provider_text(str(error)),
                        )
                        raise
                    except Exception as error:  # noqa: BLE001 - application boundary
                        knowledge_session.fail(
                            error_code="ASSESSMENT_FAILED",
                            error_message=sanitize_provider_text(str(error)),
                        )
                        raise
            except KnowledgeStoreError as error:
                raise AssessmentCommandError(
                    f"Knowledge store failure: {sanitize_provider_text(str(error))}"
                ) from error
        finally:
            # Phase 6.2: always dispose ephemeral GitHub clones; never touch local repos.
            if repository is not None:
                _cleanup_ephemeral_github_clone(repository, warn=warn)
            benchmark_recorder.deactivate()

    def assess_incrementally_if_safe(
        self,
        repo: str | None,
        output_directory: Path,
        *,
        previous_run_id: str | None = None,
        branch: str | None = None,
        with_ai: bool = False,
        config_path: Path = Path("codestrata.toml"),
        profile: str | None = None,
        settings: CodestrataSettings | None = None,
        knowledge_store: KnowledgeStore | None = None,
        candidate: object | None = None,
        plan: object | None = None,
        console: Console | None = None,
    ) -> AssessmentCommandResult:
        """Explicit opt-in incremental assessment with full-rebuild fallback.

        Does not change ``run()`` defaults. Requires ``[incremental].execution_enabled``.
        Returns the same :class:`AssessmentCommandResult` contract as ``run()``.
        """

        from codestrata.application.incremental.execution_models import IncrementalExecutionRequest
        from codestrata.application.incremental.execution_policies import (
            execution_policy_from_settings,
        )
        from codestrata.application.incremental.factory import (
            AssessmentApplicationServiceRunner,
            create_incremental_assessment_executor,
        )
        from codestrata.application.incremental.models import (
            CandidateRepositoryState,
            IncrementalAssessmentPlan,
        )

        loaded_settings = settings or load_settings(config_path)
        policy = execution_policy_from_settings(loaded_settings)
        if not policy.execution_enabled:
            # Explicit API still falls back to full assessment when execution is off.
            return self.run(
                repo,
                output_directory,
                mode=(AssessmentMode.AI_ENHANCED if with_ai else AssessmentMode.DETERMINISTIC),
                branch=branch,
                config_path=config_path,
                settings=loaded_settings,
                knowledge_store=knowledge_store,
                console=console,
            )

        resolved = resolve_assessment_repository(repo, loaded_settings)
        typed_candidate = candidate if isinstance(candidate, CandidateRepositoryState) else None
        typed_plan = plan if isinstance(plan, IncrementalAssessmentPlan) else None
        executor = create_incremental_assessment_executor(
            assessment_runner=AssessmentApplicationServiceRunner(
                self,
                knowledge_store=knowledge_store,
                console=console,
                config_path=config_path,
            ),
            settings=loaded_settings,
            policy=policy,
        )
        result = executor.execute(
            IncrementalExecutionRequest(
                repository=resolved,
                output_directory=str(output_directory),
                branch=branch,
                previous_run_id=previous_run_id,
                with_ai=with_ai,
                candidate=typed_candidate,
                plan=typed_plan,
                policy=policy,
                config_path=str(config_path),
            )
        )
        if result.assessment_result is None:
            raise AssessmentCommandError("Incremental execution produced no assessment result")
        return cast(AssessmentCommandResult, result.assessment_result)

    def _run_assessment_pipeline(
        self,
        *,
        repository: Repository,
        loaded_settings: CodestrataSettings,
        mode: AssessmentMode,
        model_id: str | None,
        resolved_branch: str | None,
        report_title: str,
        organization_name: str | None,
        max_output_tokens: int,
        temperature: float,
        max_context_characters: int | None,
        pmd_path: str | None,
        pmd_profile: str | None,
        static_analysis_enabled: bool | None,
        analysis_service: AnalysisService | None,
        provider: AIModelProvider | None,
        prompt_builder: ModernizationPromptBuilder | None,
        agent: ModernizationAssessmentAgent | None,
        context_builder: LLMAnalysisContextBuilder | None,
        graph_pipeline: GraphAssessmentPipeline | None,
        rule_engine: RuleEngine | None,
        recommendation_engine: RecommendationEngine | None,
        output_directory: Path,
        repository_reference: str,
        scan_ms: float,
        total_started: float,
        active_console: Console,
        now: Callable[[], datetime],
        stage: Callable[[str], None],
        warn: Callable[[str], None],
        verbose: bool,
        knowledge_session: AssessmentKnowledgeSession,
        write_reports: bool = True,
        force_reindex: bool = False,
        quiet: bool = False,
        json_summary: bool = False,
        config_path: Path | None = None,
        assessment_activation: str | None = None,
    ) -> AssessmentCommandResult:
        stage("Analyzing technologies...")
        stage("Running Engineering Intelligence...")
        from codestrata.benchmark.recorder import get_active_recorder

        benchmark_recorder = get_active_recorder()
        analysis_started = perf_counter()
        resolved_pmd = _resolve_pmd_for_assessment(
            cli_path=pmd_path,
            settings=loaded_settings,
            verbose=verbose,
            console=active_console,
        )
        service = analysis_service or create_default_analysis_service(
            loaded_settings,
            pmd_executable=resolved_pmd,
            static_analysis_enabled=static_analysis_enabled,
            pmd_profile=pmd_profile,
        )
        try:
            with benchmark_recorder.stage("repository_inventory"):
                analysis_result = service.analyze(repository)
        except StaticAnalysisProviderError as error:
            raise AssessmentCommandError(sanitize_provider_text(str(error))) from error
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"Deterministic analysis failed: {sanitize_provider_text(str(error))}"
            ) from error
        analysis_ms = round((perf_counter() - analysis_started) * 1000, 2)

        static_analysis_ms = _static_analysis_duration_ms(analysis_result)
        warnings = _static_analysis_warnings(analysis_result)
        for message in warnings:
            warn(message)
        _print_static_analysis_success(active_console, analysis_result)

        from codestrata.application.activation import (
            apply_activation_plan,
            build_activation_plan,
            collect_explicit_activation_overrides,
            load_raw_toml_dict,
            resolve_activation_mode,
        )

        stage("Resolving assessment activation...")
        raw_config = load_raw_toml_dict(config_path)
        activation_overrides = collect_explicit_activation_overrides(
            raw_config,
            cli_activation=assessment_activation,
        )
        activation_mode = resolve_activation_mode(
            settings_mode=loaded_settings.assessment.activation,
            overrides=activation_overrides,
            cli_mode=assessment_activation,
        )
        activation_plan = build_activation_plan(
            analysis_result,
            mode=activation_mode,
            overrides=activation_overrides,
        )
        loaded_settings = apply_activation_plan(
            loaded_settings,
            activation_plan,
            overrides=activation_overrides,
        )
        activation_coverage = activation_plan.to_coverage_payload()
        if verbose:
            enabled_ids = (
                ", ".join(item.pack_id.value for item in activation_plan.packs if item.enabled)
                or "(none)"
            )
            active_console.print(
                f"[dim]Assessment activation mode={activation_mode.value}; "
                f"enabled packs: {enabled_ids}[/dim]"
            )

        stage("Building knowledge graphs...")
        graph_started = perf_counter()
        active_graph_pipeline = graph_pipeline or GraphAssessmentPipeline()
        try:
            with benchmark_recorder.stage("graph_generation"):
                graph_pipeline_result = active_graph_pipeline.run(repository)
        except GraphAssessmentPipelineError as error:
            raise AssessmentCommandError(sanitize_provider_text(str(error))) from error
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"[graph_pipeline] Graph assessment pipeline failed: "
                f"{sanitize_provider_text(str(error))}"
            ) from error

        # Create the run directory before AI so graph artifacts persist even when AI fails.
        generated_at = now()
        run_timestamp = format_report_run_timestamp(generated_at)
        report_paths = create_report_paths(
            analysis_result,
            output_directory,
            timestamp=run_timestamp,
            create_directory=True,
        )
        try:
            with benchmark_recorder.stage("graph_serialization"):
                graph_artifacts = write_graph_artifacts(
                    graph_pipeline_result,
                    report_paths.run_directory,
                )
        except GraphAssessmentPipelineError as error:
            raise AssessmentCommandError(sanitize_provider_text(str(error))) from error
        _write_scan_boundary_diagnostics(repository, report_paths.run_directory)
        graph_elapsed_ms = round((perf_counter() - graph_started) * 1000, 2)
        for line in format_graph_console_summary(graph_artifacts.summary):
            active_console.print(line)

        stage("Evaluating assessment rules...")
        rules_started = perf_counter()
        rules_elapsed_ms: float | None = None
        shared_source_texts: dict[str, str] = {}
        shared_source_stats = None
        runtime_cfg = loaded_settings.analysis.runtime
        if runtime_cfg.shared_source_text_cache:
            from codestrata.application.runtime_performance.file_text_cache import (
                load_shared_source_texts,
            )

            inventory_paths = tuple(str(path) for path in getattr(repository, "files", ()) or ())
            shared_source_texts, shared_source_stats = load_shared_source_texts(
                relative_paths=inventory_paths,
                repository_root=Path(repository.path),
                max_files=runtime_cfg.max_source_files,
                max_chars=runtime_cfg.max_source_chars,
                max_read_workers=runtime_cfg.max_read_workers,
            )
        active_rule_engine = rule_engine or RuleEngine()
        active_recommendation_engine = recommendation_engine or RecommendationEngine()
        findings_artifact = None
        architecture_conclusions_artifact = None
        architecture_conclusion_count = None
        architecture_assessment_artifact = None
        architecture_assessment_status = None
        architecture_assessment_finding_count = None
        architecture_section_for_report = None
        technical_debt_assessment_artifact = None
        technical_debt_assessment_status = None
        technical_debt_assessment_finding_count = None
        technical_debt_section_for_report = None
        dependency_assessment_artifact = None
        dependency_assessment_status = None
        dependency_assessment_finding_count = None
        dependency_section_for_report = None
        dependency_evidence_artifact = None
        dependency_evidence_status = None
        dependency_evidence_declaration_count = None
        dependency_evidence = None
        repository_sensitive_evidence_artifact = None
        repository_sensitive_evidence_status = None
        repository_sensitive_evidence_artifact_count = None
        repository_sensitive_evidence_configuration_fact_count = None
        repository_sensitive_evidence = None
        repository_testing_evidence_artifact = None
        repository_testing_evidence_status = None
        repository_testing_evidence_candidate_count = None
        repository_testing_evidence_framework_count = None
        repository_testing_evidence = None
        repository_cloud_evidence_artifact = None
        repository_cloud_evidence_status = None
        repository_cloud_evidence_candidate_count = None
        repository_cloud_evidence_technology_count = None
        repository_cloud_evidence = None
        repository_ai_readiness_evidence_artifact = None
        repository_ai_readiness_evidence_status = None
        repository_ai_readiness_evidence_candidate_count = None
        repository_ai_readiness_evidence_technology_count = None
        repository_ai_readiness_evidence = None
        repository_performance_evidence_artifact = None
        repository_performance_evidence_status = None
        repository_performance_evidence_candidate_count = None
        repository_performance_evidence_technology_count = None
        repository_performance_evidence = None
        dependency_pack_result = None
        security_pack_result = None
        testing_pack_result = None
        cloud_pack_result = None
        try:
            rule_evaluation = active_rule_engine.evaluate_pipeline_result(graph_pipeline_result)
            from codestrata.application.rules.architecture.assessment import (
                architecture_pack_enabled,
                evaluate_architecture_pack_detailed,
                merge_rule_evaluations,
            )

            architecture_pack_result = None
            technical_debt_pack_result = None
            if architecture_pack_enabled(loaded_settings):
                architecture_pack_result = evaluate_architecture_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_root=Path(repository.path),
                    file_texts=shared_source_texts or None,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    architecture_pack_result.evaluation,
                )
            from codestrata.application.rules.technical_debt.assessment import (
                evaluate_technical_debt_pack_detailed,
                technical_debt_pack_enabled,
            )

            if technical_debt_pack_enabled(loaded_settings):
                technical_debt_pack_result = evaluate_technical_debt_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_root=Path(repository.path),
                    file_texts=shared_source_texts or None,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    technical_debt_pack_result.evaluation,
                )
            from codestrata.application.dependency.assessment.factory import (
                dependency_pack_enabled as dependency_rules_pack_enabled,
            )
            from codestrata.application.rules.dependency.assessment import (
                evaluate_dependency_pack_detailed,
            )

            if dependency_rules_pack_enabled(loaded_settings):
                dependency_pack_result = evaluate_dependency_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_root=Path(repository.path),
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    dependency_pack_result.evaluation,
                )

            # Phase 4.5.2 / 4.5.3 — collect repository-sensitive evidence once,
            # then evaluate security hygiene rules against the in-memory bundle.
            from codestrata.application.evidence.repository_sensitive.artifacts import (
                write_repository_sensitive_evidence_artifact,
            )
            from codestrata.application.evidence.repository_sensitive.io import (
                load_repository_sensitive_inputs,
            )
            from codestrata.application.evidence.repository_sensitive.service import (
                create_repository_sensitive_evidence_service,
                repository_sensitive_evidence_collection_enabled,
            )
            from codestrata.application.security.assessment.factory import (
                security_pack_enabled as security_rules_pack_enabled,
            )

            if repository_sensitive_evidence_collection_enabled(loaded_settings):
                rs_settings = loaded_settings.evidence.repository_sensitive
                rs_service = create_repository_sensitive_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                _candidates, texts, binaries, load_errors = load_repository_sensitive_inputs(
                    relative_paths=inventory_paths,
                    repository_root=Path(repository.path),
                    ignore_path_markers=rs_settings.ignore_path_markers,
                    max_files=rs_settings.max_files,
                    max_file_chars=rs_settings.max_file_chars,
                    max_file_bytes=rs_settings.max_file_bytes,
                )
                repository_sensitive_evidence = rs_service.collect(
                    repository_id=str(getattr(repository, "name", None) or repository.path),
                    relative_paths=inventory_paths,
                    file_texts=texts,
                    file_binaries=binaries,
                    load_errors=load_errors,
                    configuration_fingerprint=(
                        f"evidence.repository_sensitive.enabled={rs_settings.enabled}"
                    ),
                )
                rs_write = write_repository_sensitive_evidence_artifact(
                    repository_sensitive_evidence,
                    report_paths.run_directory,
                )
                repository_sensitive_evidence_artifact = rs_write.path
                repository_sensitive_evidence_status = repository_sensitive_evidence.status.value
                repository_sensitive_evidence_artifact_count = rs_write.artifact_count
                repository_sensitive_evidence_configuration_fact_count = (
                    rs_write.configuration_fact_count
                )

            security_pack_result = None
            if security_rules_pack_enabled(loaded_settings):
                from codestrata.application.rules.security.assessment import (
                    evaluate_security_pack_detailed,
                )

                security_pack_result = evaluate_security_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_sensitive_evidence=repository_sensitive_evidence,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    security_pack_result.evaluation,
                )

            findings_artifact = write_findings_artifact(
                rule_evaluation,
                report_paths.run_directory,
            )
            from codestrata.application.architecture.assessment.artifacts import (
                write_architecture_assessment_artifact,
            )
            from codestrata.application.architecture.assessment.factory import (
                architecture_assessment_section_enabled,
                architecture_assessment_section_settings,
                configuration_fingerprint_payload,
                create_architecture_assessment_assembler,
            )
            from codestrata.application.architecture.conclusions.factory import (
                architecture_conclusions_enabled,
                create_architecture_conclusion_service,
                enabled_policy_ids,
            )

            conclusion_result = None
            if architecture_conclusions_enabled(loaded_settings):
                conclusion_service = create_architecture_conclusion_service(loaded_settings)
                conclusion_result = conclusion_service.build(
                    repository_id=str(getattr(repository, "name", None) or repository.path),
                    findings=rule_evaluation.findings,
                    enabled_policy_ids=enabled_policy_ids(loaded_settings),
                    extraction_coverage=(
                        architecture_pack_result.extraction_coverage
                        if architecture_pack_result is not None
                        else None
                    ),
                    classification_coverage=(
                        architecture_pack_result.classification_coverage
                        if architecture_pack_result is not None
                        else None
                    ),
                    graph_fingerprint=(
                        architecture_pack_result.graph_fingerprint
                        if architecture_pack_result is not None
                        else ""
                    ),
                    enterprise_context_present=False,
                )
                conclusions_path = report_paths.run_directory / "architecture_conclusions.json"
                conclusions_path.write_text(
                    conclusion_result.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                architecture_conclusions_artifact = conclusions_path
                architecture_conclusion_count = len(conclusion_result.conclusions)

            if architecture_assessment_section_enabled(loaded_settings):
                section_cfg = architecture_assessment_section_settings(loaded_settings)
                pack_on = architecture_pack_enabled(loaded_settings)
                conclusions_on = architecture_conclusions_enabled(loaded_settings)
                assembler = create_architecture_assessment_assembler()
                if not pack_on:
                    architecture_section = assembler.assemble_disabled(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        reason="architecture_pack_disabled",
                    )
                else:
                    architecture_section = assembler.assemble(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        findings=rule_evaluation.findings,
                        conclusion_result=conclusion_result,
                        pack_enabled=True,
                        conclusions_enabled=conclusions_on,
                        include_findings=section_cfg.include_findings,
                        include_conclusions=section_cfg.include_conclusions,
                        include_recommendation_groups=(section_cfg.include_recommendation_groups),
                        include_coverage=section_cfg.include_coverage,
                        include_limitations=section_cfg.include_limitations,
                        include_traceability=section_cfg.include_traceability,
                        include_execution_summary=section_cfg.include_execution_summary,
                        extraction_coverage=(
                            architecture_pack_result.extraction_coverage
                            if architecture_pack_result is not None
                            else None
                        ),
                        classification_coverage=(
                            architecture_pack_result.classification_coverage
                            if architecture_pack_result is not None
                            else None
                        ),
                        graph_fingerprint=(
                            architecture_pack_result.graph_fingerprint
                            if architecture_pack_result is not None
                            else ""
                        ),
                        evidence_fingerprint=(
                            architecture_pack_result.evidence_fingerprint
                            if architecture_pack_result is not None
                            else ""
                        ),
                        evidence_pipeline=(
                            architecture_pack_result.evidence_pipeline
                            if architecture_pack_result is not None
                            else "legacy_view_builder"
                        ),
                        configuration_payload=configuration_fingerprint_payload(
                            loaded_settings,
                            pack_enabled=True,
                            conclusions_enabled=conclusions_on,
                        ),
                        architecture_rules_planned=len(
                            architecture_pack_result.evaluation.rules_evaluated
                        )
                        if architecture_pack_result is not None
                        else 7,
                        rules_executed=len(architecture_pack_result.evaluation.rules_evaluated)
                        if architecture_pack_result is not None
                        else 0,
                        enterprise_context_used=False,
                    )
                assessment_write = write_architecture_assessment_artifact(
                    architecture_section,
                    report_paths.run_directory,
                )
                architecture_assessment_artifact = assessment_write.path
                architecture_assessment_status = architecture_section.status.value
                architecture_assessment_finding_count = assessment_write.finding_count
                architecture_section_for_report = architecture_section

            from codestrata.application.rules.technical_debt.assessment import (
                complexity_evidence_collection_enabled,
            )
            from codestrata.application.technical_debt.assessment.artifacts import (
                write_technical_debt_assessment_artifact,
            )
            from codestrata.application.technical_debt.assessment.factory import (
                configuration_fingerprint_payload as td_configuration_fingerprint_payload,
            )
            from codestrata.application.technical_debt.assessment.factory import (
                create_technical_debt_assessment_assembler,
                technical_debt_assessment_section_enabled,
                technical_debt_assessment_section_settings,
            )

            if technical_debt_assessment_section_enabled(loaded_settings):
                td_section_cfg = technical_debt_assessment_section_settings(loaded_settings)
                td_pack_on = technical_debt_pack_enabled(loaded_settings)
                td_assembler = create_technical_debt_assessment_assembler()
                if not td_pack_on:
                    technical_debt_section = td_assembler.assemble_disabled(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        reason="technical_debt_pack_disabled",
                    )
                else:
                    pack_eval = (
                        technical_debt_pack_result.evaluation
                        if technical_debt_pack_result is not None
                        else None
                    )
                    matched = len(pack_eval.findings) if pack_eval is not None else 0
                    executed = len(pack_eval.rules_evaluated) if pack_eval is not None else 0
                    skipped = len(pack_eval.rules_skipped) if pack_eval is not None else 0
                    technical_debt_section = td_assembler.assemble(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        findings=rule_evaluation.findings,
                        pack_enabled=True,
                        complexity_evidence_enabled=complexity_evidence_collection_enabled(
                            loaded_settings
                        ),
                        include_findings=td_section_cfg.include_findings,
                        include_coverage=td_section_cfg.include_coverage,
                        include_limitations=td_section_cfg.include_limitations,
                        include_traceability=td_section_cfg.include_traceability,
                        include_execution_summary=td_section_cfg.include_execution_summary,
                        include_synthesis=td_section_cfg.include_synthesis,
                        complexity_evidence=(
                            technical_debt_pack_result.complexity_evidence
                            if technical_debt_pack_result is not None
                            else None
                        ),
                        evidence_pipeline=(
                            technical_debt_pack_result.evidence_pipeline
                            if technical_debt_pack_result is not None
                            else "not_configured"
                        ),
                        evidence_fingerprint=(
                            technical_debt_pack_result.evidence_fingerprint
                            if technical_debt_pack_result is not None
                            else ""
                        ),
                        configuration_payload=td_configuration_fingerprint_payload(
                            loaded_settings,
                            pack_enabled=True,
                        ),
                        debt_rules_planned=5,
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=max(executed - matched, 0),
                        rules_not_applicable=skipped,
                        files_considered=(
                            technical_debt_pack_result.files_considered
                            if technical_debt_pack_result is not None
                            else 0
                        ),
                        files_analyzed=(
                            technical_debt_pack_result.files_analyzed
                            if technical_debt_pack_result is not None
                            else 0
                        ),
                        files_excluded=(
                            technical_debt_pack_result.files_excluded
                            if technical_debt_pack_result is not None
                            else 0
                        ),
                        files_failed=(
                            technical_debt_pack_result.files_failed
                            if technical_debt_pack_result is not None
                            else 0
                        ),
                        diagnostics=(
                            technical_debt_pack_result.diagnostics
                            if technical_debt_pack_result is not None
                            else ()
                        ),
                    )
                td_write = write_technical_debt_assessment_artifact(
                    technical_debt_section,
                    report_paths.run_directory,
                )
                technical_debt_assessment_artifact = td_write.path
                technical_debt_assessment_status = technical_debt_section.status.value
                technical_debt_assessment_finding_count = td_write.finding_count
                technical_debt_section_for_report = technical_debt_section
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"[rule_engine] Rule evaluation failed: {sanitize_provider_text(str(error))}"
            ) from error

        # Phase 4.4.2 / 4.4.3 — Dependency Evidence + Dependency hygiene assessment.
        try:
            from codestrata.application.dependency.assessment.artifacts import (
                write_dependency_assessment_artifact,
            )
            from codestrata.application.dependency.assessment.factory import (
                configuration_fingerprint_payload as dep_configuration_fingerprint_payload,
            )
            from codestrata.application.dependency.assessment.factory import (
                create_dependency_assessment_assembler,
                dependency_assessment_section_enabled,
                dependency_assessment_section_settings,
                dependency_pack_enabled,
            )
            from codestrata.application.evidence.dependency.artifacts import (
                write_dependency_evidence_artifact,
            )
            from codestrata.application.evidence.dependency.io import (
                load_dependency_manifest_texts,
            )
            from codestrata.application.evidence.dependency.service import (
                create_dependency_evidence_service,
            )
            from codestrata.application.rules.dependency.assessment import (
                dependency_evidence_collection_enabled,
            )
            from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS

            dependency_evidence = (
                dependency_pack_result.dependency_evidence
                if dependency_pack_result is not None
                else None
            )
            if dependency_evidence is None and dependency_evidence_collection_enabled(
                loaded_settings
            ):
                dep_evidence_service = create_dependency_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                _paths, texts = load_dependency_manifest_texts(
                    relative_paths=inventory_paths,
                    repository_root=Path(repository.path),
                    max_files=loaded_settings.evidence.dependency.max_files,
                    max_chars=loaded_settings.evidence.dependency.max_file_chars,
                )
                dependency_evidence = dep_evidence_service.collect(
                    repository_id=str(getattr(repository, "name", None) or repository.path),
                    relative_paths=inventory_paths,
                    file_texts=texts,
                    configuration_fingerprint=(
                        f"evidence.dependency.enabled={loaded_settings.evidence.dependency.enabled}"
                    ),
                )

            if dependency_evidence is not None:
                evidence_write = write_dependency_evidence_artifact(
                    dependency_evidence,
                    report_paths.run_directory,
                )
                dependency_evidence_artifact = evidence_write.path
                dependency_evidence_status = dependency_evidence.status.value
                dependency_evidence_declaration_count = evidence_write.declaration_count

            if dependency_assessment_section_enabled(loaded_settings):
                dep_section_cfg = dependency_assessment_section_settings(loaded_settings)
                dep_assembler = create_dependency_assessment_assembler()
                dep_pack_on = dependency_pack_enabled(loaded_settings)
                if not dep_pack_on:
                    dependency_section = dep_assembler.assemble_disabled(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        reason="dependency_pack_disabled",
                    )
                    if dependency_evidence is not None:
                        dependency_section = dependency_section.model_copy(
                            update={
                                "evidence_pipeline": "dependency.manifest",
                                "evidence_fingerprint": (dependency_evidence.evidence_fingerprint),
                            }
                        )
                else:
                    pack_eval = (
                        dependency_pack_result.evaluation
                        if dependency_pack_result is not None
                        else None
                    )
                    pack_findings = pack_eval.findings if pack_eval is not None else ()
                    matched = len(pack_findings)
                    executed = len(pack_eval.rules_evaluated) if pack_eval is not None else 0
                    skipped = len(pack_eval.rules_skipped) if pack_eval is not None else 0
                    evidence_on = dependency_evidence_collection_enabled(loaded_settings)
                    dependency_section = dep_assembler.assemble(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        findings=pack_findings,
                        pack_enabled=True,
                        evidence_enabled=evidence_on,
                        include_findings=dep_section_cfg.include_findings,
                        include_coverage=dep_section_cfg.include_coverage,
                        include_limitations=dep_section_cfg.include_limitations,
                        include_traceability=dep_section_cfg.include_traceability,
                        include_execution_summary=(dep_section_cfg.include_execution_summary),
                        include_synthesis=dep_section_cfg.include_synthesis,
                        dependency_evidence=dependency_evidence,
                        evidence_pipeline=(
                            dependency_pack_result.evidence_pipeline
                            if dependency_pack_result is not None
                            else (
                                "dependency.manifest"
                                if dependency_evidence is not None
                                else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            dependency_pack_result.evidence_fingerprint
                            if dependency_pack_result is not None
                            else (
                                dependency_evidence.evidence_fingerprint
                                if dependency_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=dep_configuration_fingerprint_payload(
                            loaded_settings,
                            pack_enabled=True,
                        ),
                        dependency_rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=max(executed - matched, 0),
                        rules_not_applicable=skipped,
                        diagnostics=(
                            dependency_pack_result.diagnostics
                            if dependency_pack_result is not None
                            else ()
                        ),
                    )
                dep_write = write_dependency_assessment_artifact(
                    dependency_section,
                    report_paths.run_directory,
                )
                dependency_assessment_artifact = dep_write.path
                dependency_assessment_status = dependency_section.status.value
                dependency_assessment_finding_count = dep_write.finding_count
                dependency_section_for_report = dependency_section
        except Exception as error:  # noqa: BLE001 - isolate dependency pack failures
            dependency_assessment_artifact = None
            dependency_assessment_status = "failed"
            dependency_assessment_finding_count = None
            dependency_section_for_report = None
            dependency_evidence_artifact = None
            dependency_evidence_status = "failed"
            dependency_evidence_declaration_count = None
            warn(
                "Dependency assessment/evidence could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.5.2 — repository-sensitive evidence fallback when not collected above.
        try:
            from codestrata.application.evidence.repository_sensitive.artifacts import (
                write_repository_sensitive_evidence_artifact,
            )
            from codestrata.application.evidence.repository_sensitive.io import (
                load_repository_sensitive_inputs,
            )
            from codestrata.application.evidence.repository_sensitive.service import (
                create_repository_sensitive_evidence_service,
                repository_sensitive_evidence_collection_enabled,
            )

            if (
                repository_sensitive_evidence is None
                and repository_sensitive_evidence_collection_enabled(loaded_settings)
            ):
                rs_settings = loaded_settings.evidence.repository_sensitive
                rs_service = create_repository_sensitive_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                _candidates, texts, binaries, load_errors = load_repository_sensitive_inputs(
                    relative_paths=inventory_paths,
                    repository_root=Path(repository.path),
                    ignore_path_markers=rs_settings.ignore_path_markers,
                    max_files=rs_settings.max_files,
                    max_file_chars=rs_settings.max_file_chars,
                    max_file_bytes=rs_settings.max_file_bytes,
                )
                repository_sensitive_evidence = rs_service.collect(
                    repository_id=str(getattr(repository, "name", None) or repository.path),
                    relative_paths=inventory_paths,
                    file_texts=texts,
                    file_binaries=binaries,
                    load_errors=load_errors,
                    configuration_fingerprint=(
                        f"evidence.repository_sensitive.enabled={rs_settings.enabled}"
                    ),
                )
                rs_write = write_repository_sensitive_evidence_artifact(
                    repository_sensitive_evidence,
                    report_paths.run_directory,
                )
                repository_sensitive_evidence_artifact = rs_write.path
                repository_sensitive_evidence_status = repository_sensitive_evidence.status.value
                repository_sensitive_evidence_artifact_count = rs_write.artifact_count
                repository_sensitive_evidence_configuration_fact_count = (
                    rs_write.configuration_fact_count
                )
        except Exception as error:  # noqa: BLE001 - isolate evidence failures
            if repository_sensitive_evidence_status is None:
                repository_sensitive_evidence_artifact = None
                repository_sensitive_evidence_status = "failed"
                repository_sensitive_evidence_artifact_count = None
                repository_sensitive_evidence_configuration_fact_count = None
                warn(
                    "Repository-sensitive evidence could not be built; "
                    "remaining assessment content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )

        # Phase 4.6.2 — repository-testing evidence (structure/config facts only).
        try:
            from codestrata.application.evidence.repository_testing.artifacts import (
                write_repository_testing_evidence_artifact,
            )
            from codestrata.application.evidence.repository_testing.io import (
                load_repository_testing_inputs,
            )
            from codestrata.application.evidence.repository_testing.service import (
                create_repository_testing_evidence_service,
                repository_testing_evidence_collection_enabled,
            )

            if repository_testing_evidence_collection_enabled(loaded_settings):
                rt_settings = loaded_settings.evidence.repository_testing
                rt_service = create_repository_testing_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                if not inventory_paths:
                    from codestrata.application.evidence.repository_testing.limitations import (
                        standard_limitations,
                    )
                    from codestrata.domain.evidence.repository_testing.enums import (
                        RepositoryTestingParseStatus,
                    )
                    from codestrata.domain.evidence.repository_testing.identifiers import (
                        make_bundle_id,
                    )
                    from codestrata.domain.evidence.repository_testing.models import (
                        AggregatedRepositoryTestingEvidence,
                    )

                    repo_id = str(getattr(repository, "name", None) or repository.path)
                    repository_testing_evidence = AggregatedRepositoryTestingEvidence(
                        bundle_id=make_bundle_id(repository_id=repo_id, fingerprint="insufficient"),
                        repository_id=repo_id,
                        status=RepositoryTestingParseStatus.INSUFFICIENT_EVIDENCE,
                        limitations=standard_limitations(),
                        evidence_fingerprint="insufficient",
                    )
                else:
                    _rt_meta, rt_texts, rt_load_errors = load_repository_testing_inputs(
                        relative_paths=inventory_paths,
                        repository_root=Path(repository.path),
                        ignore_path_markers=rt_settings.ignore_path_markers,
                        max_files=rt_settings.max_files,
                        max_file_chars=rt_settings.max_file_chars,
                        max_file_bytes=rt_settings.max_file_bytes,
                    )
                    repository_testing_evidence = rt_service.collect(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        relative_paths=inventory_paths,
                        file_texts=rt_texts,
                        load_errors=rt_load_errors,
                        configuration_fingerprint=(
                            f"evidence.repository_testing.enabled={rt_settings.enabled}"
                        ),
                    )
                rt_write = write_repository_testing_evidence_artifact(
                    repository_testing_evidence,
                    report_paths.run_directory,
                )
                repository_testing_evidence_artifact = rt_write.path
                repository_testing_evidence_status = repository_testing_evidence.status.value
                repository_testing_evidence_candidate_count = rt_write.candidate_count
                repository_testing_evidence_framework_count = rt_write.framework_count
        except Exception as error:  # noqa: BLE001 - isolate evidence failures
            repository_testing_evidence = None
            repository_testing_evidence_artifact = None
            repository_testing_evidence_status = "failed"
            repository_testing_evidence_candidate_count = None
            repository_testing_evidence_framework_count = None
            warn(
                "Repository-testing evidence could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.7.2 — repository-cloud evidence (technology/deployment signals only).
        try:
            from codestrata.application.evidence.repository_cloud.artifacts import (
                write_repository_cloud_evidence_artifact,
            )
            from codestrata.application.evidence.repository_cloud.io import (
                load_repository_cloud_inputs,
            )
            from codestrata.application.evidence.repository_cloud.service import (
                create_repository_cloud_evidence_service,
                repository_cloud_evidence_collection_enabled,
            )

            if repository_cloud_evidence_collection_enabled(loaded_settings):
                rc_settings = loaded_settings.evidence.repository_cloud
                rc_service = create_repository_cloud_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                if not inventory_paths:
                    from codestrata.application.evidence.repository_cloud.limitations import (
                        standard_limitations as cloud_standard_limitations,
                    )
                    from codestrata.domain.evidence.repository_cloud.enums import (
                        RepositoryCloudParseStatus,
                    )
                    from codestrata.domain.evidence.repository_cloud.identifiers import (
                        make_bundle_id,
                    )
                    from codestrata.domain.evidence.repository_cloud.models import (
                        AggregatedRepositoryCloudEvidence,
                    )

                    repo_id = str(getattr(repository, "name", None) or repository.path)
                    repository_cloud_evidence = AggregatedRepositoryCloudEvidence(
                        bundle_id=make_bundle_id(repository_id=repo_id, fingerprint="insufficient"),
                        repository_id=repo_id,
                        status=RepositoryCloudParseStatus.INSUFFICIENT_EVIDENCE,
                        limitations=cloud_standard_limitations(),
                        evidence_fingerprint="insufficient",
                    )
                else:
                    _rc_meta, rc_texts, rc_load_errors = load_repository_cloud_inputs(
                        relative_paths=inventory_paths,
                        repository_root=Path(repository.path),
                        ignore_path_markers=rc_settings.ignore_path_markers,
                        max_files=rc_settings.max_files,
                        max_file_chars=rc_settings.max_file_chars,
                        max_file_bytes=rc_settings.max_file_bytes,
                    )
                    repository_cloud_evidence = rc_service.collect(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        relative_paths=inventory_paths,
                        file_texts=rc_texts,
                        load_errors=rc_load_errors,
                        configuration_fingerprint=(
                            f"evidence.repository_cloud.enabled={rc_settings.enabled}"
                        ),
                    )
                rc_write = write_repository_cloud_evidence_artifact(
                    repository_cloud_evidence,
                    report_paths.run_directory,
                )
                repository_cloud_evidence_artifact = rc_write.path
                repository_cloud_evidence_status = repository_cloud_evidence.status.value
                repository_cloud_evidence_candidate_count = rc_write.candidate_count
                repository_cloud_evidence_technology_count = rc_write.technology_count
        except Exception as error:  # noqa: BLE001 - isolate evidence failures
            repository_cloud_evidence_artifact = None
            repository_cloud_evidence_status = "failed"
            repository_cloud_evidence_candidate_count = None
            repository_cloud_evidence_technology_count = None
            repository_cloud_evidence = None
            warn(
                "Repository-cloud evidence could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.8.2 — repository AI-readiness evidence (signals only).
        try:
            from codestrata.application.evidence.repository_ai_readiness.artifacts import (
                write_repository_ai_readiness_evidence_artifact,
            )
            from codestrata.application.evidence.repository_ai_readiness.io import (
                load_repository_ai_readiness_inputs,
            )
            from codestrata.application.evidence.repository_ai_readiness.service import (
                create_repository_ai_readiness_evidence_service,
                repository_ai_readiness_evidence_collection_enabled,
            )

            if repository_ai_readiness_evidence_collection_enabled(loaded_settings):
                rar_settings = loaded_settings.evidence.repository_ai_readiness
                rar_service = create_repository_ai_readiness_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                if not inventory_paths:
                    from codestrata.application.evidence.repository_ai_readiness.limitations import (  # noqa: E501
                        standard_limitations as ai_readiness_standard_limitations,
                    )
                    from codestrata.domain.evidence.repository_ai_readiness.enums import (
                        RepositoryAiReadinessParseStatus,
                    )
                    from codestrata.domain.evidence.repository_ai_readiness.identifiers import (
                        make_bundle_id,
                    )
                    from codestrata.domain.evidence.repository_ai_readiness.models import (
                        AggregatedRepositoryAiReadinessEvidence,
                    )

                    repo_id = str(getattr(repository, "name", None) or repository.path)
                    repository_ai_readiness_evidence = AggregatedRepositoryAiReadinessEvidence(
                        bundle_id=make_bundle_id(repository_id=repo_id, fingerprint="insufficient"),
                        repository_id=repo_id,
                        status=RepositoryAiReadinessParseStatus.INSUFFICIENT_EVIDENCE,
                        limitations=ai_readiness_standard_limitations(),
                        evidence_fingerprint="insufficient",
                    )
                else:
                    _rar_meta, rar_texts, rar_load_errors = load_repository_ai_readiness_inputs(
                        relative_paths=inventory_paths,
                        repository_root=Path(repository.path),
                        ignore_path_markers=rar_settings.ignore_path_markers,
                        max_files=rar_settings.max_files,
                        max_file_chars=rar_settings.max_file_chars,
                        max_file_bytes=rar_settings.max_file_bytes,
                    )
                    repository_ai_readiness_evidence = rar_service.collect(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        relative_paths=inventory_paths,
                        file_texts=rar_texts,
                        load_errors=rar_load_errors,
                        configuration_fingerprint=(
                            f"evidence.repository_ai_readiness.enabled={rar_settings.enabled}"
                        ),
                    )
                rar_write = write_repository_ai_readiness_evidence_artifact(
                    repository_ai_readiness_evidence,
                    report_paths.run_directory,
                )
                repository_ai_readiness_evidence_artifact = rar_write.path
                repository_ai_readiness_evidence_status = (
                    repository_ai_readiness_evidence.status.value
                )
                repository_ai_readiness_evidence_candidate_count = rar_write.candidate_count
                repository_ai_readiness_evidence_technology_count = rar_write.technology_count
        except Exception as error:  # noqa: BLE001 - isolate evidence failures
            repository_ai_readiness_evidence_artifact = None
            repository_ai_readiness_evidence_status = "failed"
            repository_ai_readiness_evidence_candidate_count = None
            repository_ai_readiness_evidence_technology_count = None
            repository_ai_readiness_evidence = None
            warn(
                "Repository AI-readiness evidence could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.9.2 — repository performance evidence (signals only).
        try:
            from codestrata.application.evidence.repository_performance.artifacts import (
                write_repository_performance_evidence_artifact,
            )
            from codestrata.application.evidence.repository_performance.io import (
                load_repository_performance_inputs,
            )
            from codestrata.application.evidence.repository_performance.service import (
                create_repository_performance_evidence_service,
                repository_performance_evidence_collection_enabled,
            )

            if repository_performance_evidence_collection_enabled(loaded_settings):
                rpe_settings = loaded_settings.evidence.repository_performance
                rpe_service = create_repository_performance_evidence_service(loaded_settings)
                inventory_paths = tuple(
                    str(path) for path in getattr(repository, "files", ()) or ()
                )
                if not inventory_paths:
                    from codestrata.application.evidence.repository_performance.limitations import (
                        standard_limitations as performance_standard_limitations,
                    )
                    from codestrata.domain.evidence.repository_performance.enums import (
                        RepositoryPerformanceParseStatus,
                    )
                    from codestrata.domain.evidence.repository_performance.identifiers import (
                        make_bundle_id,
                    )
                    from codestrata.domain.evidence.repository_performance.models import (
                        AggregatedRepositoryPerformanceEvidence,
                    )

                    repo_id = str(getattr(repository, "name", None) or repository.path)
                    repository_performance_evidence = AggregatedRepositoryPerformanceEvidence(
                        bundle_id=make_bundle_id(repository_id=repo_id, fingerprint="insufficient"),
                        repository_id=repo_id,
                        status=RepositoryPerformanceParseStatus.INSUFFICIENT_EVIDENCE,
                        limitations=performance_standard_limitations(),
                        evidence_fingerprint="insufficient",
                    )
                else:
                    _rpe_meta, rpe_texts, rpe_load_errors = load_repository_performance_inputs(
                        relative_paths=inventory_paths,
                        repository_root=Path(repository.path),
                        ignore_path_markers=rpe_settings.ignore_path_markers,
                        max_files=rpe_settings.max_files,
                        max_file_chars=rpe_settings.max_file_chars,
                        max_file_bytes=rpe_settings.max_file_bytes,
                    )
                    repository_performance_evidence = rpe_service.collect(
                        repository_id=str(getattr(repository, "name", None) or repository.path),
                        relative_paths=inventory_paths,
                        file_texts=rpe_texts,
                        load_errors=rpe_load_errors,
                        configuration_fingerprint=(
                            f"evidence.repository_performance.enabled={rpe_settings.enabled}"
                        ),
                    )
                rpe_write = write_repository_performance_evidence_artifact(
                    repository_performance_evidence,
                    report_paths.run_directory,
                )
                repository_performance_evidence_artifact = rpe_write.path
                repository_performance_evidence_status = (
                    repository_performance_evidence.status.value
                )
                repository_performance_evidence_candidate_count = rpe_write.candidate_count
                repository_performance_evidence_technology_count = rpe_write.technology_count
        except Exception as error:  # noqa: BLE001 - isolate evidence failures
            repository_performance_evidence_artifact = None
            repository_performance_evidence_status = "failed"
            repository_performance_evidence_candidate_count = None
            repository_performance_evidence_technology_count = None
            repository_performance_evidence = None
            warn(
                "Repository performance evidence could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.7.3 — Cloud Hygiene rules against in-memory repository-cloud evidence.
        cloud_pack_result = None
        try:
            from codestrata.application.cloud.assessment.factory import (
                cloud_pack_enabled as cloud_rules_pack_enabled,
            )
            from codestrata.application.rules.architecture.assessment import (
                merge_rule_evaluations,
            )
            from codestrata.application.rules.cloud.assessment import (
                evaluate_cloud_pack_detailed,
            )

            if cloud_rules_pack_enabled(loaded_settings):
                cloud_pack_result = evaluate_cloud_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_cloud_evidence=repository_cloud_evidence,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    cloud_pack_result.evaluation,
                )
                findings_artifact = write_findings_artifact(
                    rule_evaluation,
                    report_paths.run_directory,
                )
        except Exception as error:  # noqa: BLE001 - isolate cloud rule failures
            cloud_pack_result = None
            warn(
                "Cloud Hygiene rules could not be evaluated; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.6.3 — Test Hygiene rules against in-memory repository-testing evidence.
        testing_pack_result = None
        try:
            from codestrata.application.rules.architecture.assessment import (
                merge_rule_evaluations,
            )
            from codestrata.application.rules.testing.assessment import (
                evaluate_testing_pack_detailed,
            )
            from codestrata.application.testing.assessment.factory import (
                testing_pack_enabled as testing_rules_pack_enabled,
            )

            if testing_rules_pack_enabled(loaded_settings):
                testing_pack_result = evaluate_testing_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_testing_evidence=repository_testing_evidence,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    testing_pack_result.evaluation,
                )
                findings_artifact = write_findings_artifact(
                    rule_evaluation,
                    report_paths.run_directory,
                )
        except Exception as error:  # noqa: BLE001 - isolate testing rule failures
            testing_pack_result = None
            warn(
                "Test Hygiene rules could not be evaluated; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.8.3 — AI Readiness Hygiene rules against in-memory evidence.
        ai_readiness_pack_result = None
        try:
            from codestrata.application.ai_readiness.assessment.factory import (
                ai_readiness_pack_enabled as ai_readiness_rules_pack_enabled,
            )
            from codestrata.application.rules.ai_readiness.assessment import (
                evaluate_ai_readiness_pack_detailed,
            )
            from codestrata.application.rules.architecture.assessment import (
                merge_rule_evaluations,
            )

            if ai_readiness_rules_pack_enabled(loaded_settings):
                ai_readiness_pack_result = evaluate_ai_readiness_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_ai_readiness_evidence=repository_ai_readiness_evidence,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    ai_readiness_pack_result.evaluation,
                )
                findings_artifact = write_findings_artifact(
                    rule_evaluation,
                    report_paths.run_directory,
                )
        except Exception as error:  # noqa: BLE001 - isolate AI readiness rule failures
            ai_readiness_pack_result = None
            warn(
                "AI Readiness Hygiene rules could not be evaluated; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.9.3 — Performance Hygiene rules against in-memory evidence.
        performance_pack_result = None
        try:
            from codestrata.application.performance.assessment.factory import (
                performance_pack_enabled as performance_rules_pack_enabled,
            )
            from codestrata.application.rules.architecture.assessment import (
                merge_rule_evaluations,
            )
            from codestrata.application.rules.performance.assessment import (
                evaluate_performance_pack_detailed,
            )

            if performance_rules_pack_enabled(loaded_settings):
                performance_pack_result = evaluate_performance_pack_detailed(
                    pipeline_result=graph_pipeline_result,
                    settings=loaded_settings,
                    repository_performance_evidence=repository_performance_evidence,
                )
                rule_evaluation = merge_rule_evaluations(
                    rule_evaluation,
                    performance_pack_result.evaluation,
                )
                findings_artifact = write_findings_artifact(
                    rule_evaluation,
                    report_paths.run_directory,
                )
        except Exception as error:  # noqa: BLE001 - isolate performance rule failures
            performance_pack_result = None
            warn(
                "Performance Hygiene rules could not be evaluated; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.5.3 — Security hygiene assessment (Findings + execution facts).
        security_assessment_artifact = None
        security_assessment_status = None
        security_assessment_finding_count = None
        security_section_for_report = None
        try:
            from codestrata.application.security.assessment.artifacts import (
                write_security_assessment_artifact,
            )
            from codestrata.application.security.assessment.factory import (
                configuration_fingerprint_payload as sec_configuration_fingerprint_payload,
            )
            from codestrata.application.security.assessment.factory import (
                create_security_assessment_assembler,
                security_assessment_section_enabled,
                security_assessment_section_settings,
                security_pack_enabled,
            )
            from codestrata.domain.security.ids import HYGIENE_RULE_IDS

            if security_assessment_section_enabled(loaded_settings):
                sec_assembler = create_security_assessment_assembler()
                repo_id = str(getattr(repository, "name", None) or repository.path)
                sec_cfg = security_assessment_section_settings(loaded_settings)
                pack_on = security_pack_enabled(loaded_settings)
                if not pack_on:
                    security_section = sec_assembler.assemble_disabled(
                        repository_id=repo_id,
                        reason="security_pack_disabled",
                        evidence=repository_sensitive_evidence,
                    )
                else:
                    pack_eval = (
                        security_pack_result.evaluation
                        if security_pack_result is not None
                        else None
                    )
                    pack_findings = pack_eval.findings if pack_eval is not None else ()
                    matched = len(pack_findings)
                    executed = len(pack_eval.rules_evaluated) if pack_eval is not None else 0
                    skipped = len(pack_eval.rules_skipped) if pack_eval is not None else 0
                    evidence_on = bool(loaded_settings.evidence.repository_sensitive.enabled)
                    evidence_available = repository_sensitive_evidence is not None
                    security_section = sec_assembler.assemble(
                        repository_id=repo_id,
                        findings=pack_findings,
                        pack_enabled=True,
                        evidence_enabled=evidence_on,
                        evidence_available=evidence_available,
                        include_findings=sec_cfg.include_findings,
                        include_coverage=sec_cfg.include_coverage,
                        include_limitations=sec_cfg.include_limitations,
                        include_traceability=sec_cfg.include_traceability,
                        include_execution_summary=sec_cfg.include_execution_summary,
                        include_synthesis=sec_cfg.include_synthesis,
                        evidence_pipeline=(
                            security_pack_result.evidence_pipeline
                            if security_pack_result is not None
                            else (
                                "repository_sensitive" if evidence_available else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            security_pack_result.evidence_fingerprint
                            if security_pack_result is not None
                            else (
                                repository_sensitive_evidence.evidence_fingerprint
                                if repository_sensitive_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=sec_configuration_fingerprint_payload(
                            loaded_settings,
                            pack_enabled=True,
                        ),
                        security_rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=max(executed - matched, 0),
                        rules_not_applicable=skipped,
                        diagnostics=(
                            security_pack_result.diagnostics
                            if security_pack_result is not None
                            else ()
                        ),
                        repository_sensitive_evidence=repository_sensitive_evidence,
                        rule_execution_facts=(
                            security_pack_result.rule_execution_facts
                            if security_pack_result is not None
                            else ()
                        ),
                    )
                sec_write = write_security_assessment_artifact(
                    security_section,
                    report_paths.run_directory,
                )
                security_assessment_artifact = sec_write.path
                security_assessment_status = security_section.status.value
                security_assessment_finding_count = sec_write.finding_count
                security_section_for_report = security_section
        except Exception as error:  # noqa: BLE001 - isolate security failures
            security_assessment_artifact = None
            security_assessment_status = "failed"
            security_assessment_finding_count = None
            security_section_for_report = None
            warn(
                "Security assessment could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.6.3 — Test Hygiene assessment (Findings from repository-testing evidence).
        testing_assessment_artifact = None
        testing_assessment_status = None
        testing_assessment_finding_count = None
        testing_section_for_report = None
        try:
            from codestrata.application.testing.assessment.artifacts import (
                write_testing_assessment_artifact,
            )
            from codestrata.application.testing.assessment.factory import (
                create_testing_assessment_assembler,
                testing_assessment_section_enabled,
                testing_assessment_section_settings,
                testing_pack_enabled,
            )
            from codestrata.domain.testing.ids import HYGIENE_RULE_IDS

            if testing_assessment_section_enabled(loaded_settings):
                test_assembler = create_testing_assessment_assembler()
                repo_id = str(getattr(repository, "name", None) or repository.path)
                test_cfg = testing_assessment_section_settings(loaded_settings)
                pack_on = testing_pack_enabled(loaded_settings)
                if not pack_on:
                    testing_section = test_assembler.assemble_disabled(
                        repository_id=repo_id,
                        reason="testing_pack_disabled",
                    )
                else:
                    pack_findings = (
                        testing_pack_result.evaluation.findings
                        if testing_pack_result is not None
                        else ()
                    )
                    executed = 0
                    matched = 0
                    not_matched = 0
                    not_applicable = 0
                    failed = 0
                    if testing_pack_result is not None:
                        (
                            executed,
                            matched,
                            not_matched,
                            not_applicable,
                            failed,
                        ) = _count_rule_execution_statuses(testing_pack_result.rule_execution_facts)
                    testing_section = test_assembler.assemble(
                        repository_id=repo_id,
                        findings=pack_findings,
                        evidence=repository_testing_evidence,
                        pack_enabled=True,
                        rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=not_matched,
                        rules_not_applicable=not_applicable,
                        rules_failed=failed,
                        rule_execution_facts=(
                            testing_pack_result.rule_execution_facts
                            if testing_pack_result is not None
                            else ()
                        ),
                        evidence_pipeline=(
                            testing_pack_result.evidence_pipeline
                            if testing_pack_result is not None
                            else (
                                "repository_testing"
                                if repository_testing_evidence is not None
                                else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            testing_pack_result.evidence_fingerprint
                            if testing_pack_result is not None
                            else (
                                repository_testing_evidence.evidence_fingerprint
                                if repository_testing_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=(
                            f"rules.testing.enabled=true|"
                            f"evidence.repository_testing.enabled="
                            f"{loaded_settings.evidence.repository_testing.enabled}"
                        ),
                        diagnostics=(
                            testing_pack_result.diagnostics
                            if testing_pack_result is not None
                            else ()
                        ),
                        include_findings=test_cfg.include_findings,
                        include_coverage=test_cfg.include_coverage,
                        include_limitations=test_cfg.include_limitations,
                        include_traceability=test_cfg.include_traceability,
                        include_execution_summary=test_cfg.include_execution_summary,
                        include_synthesis=test_cfg.include_synthesis,
                    )
                test_write = write_testing_assessment_artifact(
                    testing_section,
                    report_paths.run_directory,
                )
                testing_assessment_artifact = test_write.path
                testing_assessment_status = testing_section.status.value
                testing_assessment_finding_count = test_write.finding_count
                testing_section_for_report = testing_section
        except Exception as error:  # noqa: BLE001 - isolate testing failures
            testing_assessment_artifact = None
            testing_assessment_status = "failed"
            testing_assessment_finding_count = None
            testing_section_for_report = None
            warn(
                "Test assessment could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.7.4 — Cloud Intelligence assessment inventory.
        cloud_assessment_artifact = None
        cloud_assessment_status = None
        cloud_assessment_finding_count = None
        cloud_section_for_report = None
        try:
            from codestrata.application.cloud.assessment.artifacts import (
                write_cloud_assessment_artifact,
            )
            from codestrata.application.cloud.assessment.factory import (
                cloud_analysis_enabled,
                cloud_analysis_settings,
                cloud_pack_enabled,
                create_cloud_assessment_assembler,
            )
            from codestrata.domain.cloud.ids import HYGIENE_RULE_IDS

            if cloud_analysis_enabled(loaded_settings):
                cloud_assembler = create_cloud_assessment_assembler()
                repo_id = str(getattr(repository, "name", None) or repository.path)
                cloud_cfg = cloud_analysis_settings(loaded_settings)
                pack_on = cloud_pack_enabled(loaded_settings)
                if not pack_on:
                    cloud_section = cloud_assembler.assemble_disabled(
                        repository_id=repo_id,
                        reason="cloud_pack_disabled",
                    )
                else:
                    pack_findings = (
                        cloud_pack_result.evaluation.findings
                        if cloud_pack_result is not None
                        else ()
                    )
                    executed = 0
                    matched = 0
                    not_matched = 0
                    not_applicable = 0
                    failed = 0
                    if cloud_pack_result is not None:
                        (
                            executed,
                            matched,
                            not_matched,
                            not_applicable,
                            failed,
                        ) = _count_rule_execution_statuses(cloud_pack_result.rule_execution_facts)
                    cloud_section = cloud_assembler.assemble(
                        repository_id=repo_id,
                        findings=pack_findings,
                        pack_enabled=True,
                        rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=not_matched,
                        rules_not_applicable=not_applicable,
                        rules_failed=failed,
                        rule_execution_facts=(
                            cloud_pack_result.rule_execution_facts
                            if cloud_pack_result is not None
                            else ()
                        ),
                        evidence_pipeline=(
                            cloud_pack_result.evidence_pipeline
                            if cloud_pack_result is not None
                            else (
                                "repository_cloud"
                                if repository_cloud_evidence is not None
                                else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            cloud_pack_result.evidence_fingerprint
                            if cloud_pack_result is not None
                            else (
                                repository_cloud_evidence.evidence_fingerprint
                                if repository_cloud_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=(
                            f"rules.cloud.enabled=true|"
                            f"evidence.repository_cloud.enabled="
                            f"{loaded_settings.evidence.repository_cloud.enabled}"
                        ),
                        diagnostics=(
                            cloud_pack_result.diagnostics if cloud_pack_result is not None else ()
                        ),
                        include_findings=cloud_cfg.include_findings,
                        include_coverage=cloud_cfg.include_coverage,
                        include_limitations=cloud_cfg.include_limitations,
                        include_traceability=cloud_cfg.include_traceability,
                        include_execution_summary=cloud_cfg.include_execution_summary,
                        include_synthesis=cloud_cfg.include_synthesis,
                    )
                cloud_write = write_cloud_assessment_artifact(
                    cloud_section,
                    report_paths.run_directory,
                )
                cloud_assessment_artifact = cloud_write.path
                cloud_assessment_status = cloud_section.status.value
                cloud_assessment_finding_count = cloud_write.finding_count
                cloud_section_for_report = cloud_section
        except Exception as error:  # noqa: BLE001 - isolate cloud failures
            cloud_assessment_artifact = None
            cloud_assessment_status = "failed"
            cloud_assessment_finding_count = None
            cloud_section_for_report = None
            warn(
                "Cloud assessment could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.8.4 — AI Readiness Intelligence inventory (+ synthesis when enabled).
        ai_readiness_assessment_artifact = None
        ai_readiness_assessment_status = None
        ai_readiness_assessment_finding_count = None
        ai_readiness_section_for_report = None
        try:
            from codestrata.application.ai_readiness.assessment.artifacts import (
                write_ai_readiness_assessment_artifact,
            )
            from codestrata.application.ai_readiness.assessment.factory import (
                ai_readiness_analysis_enabled,
                ai_readiness_analysis_settings,
                ai_readiness_pack_enabled,
                create_ai_readiness_assessment_assembler,
            )
            from codestrata.domain.ai_readiness.ids import HYGIENE_RULE_IDS

            if ai_readiness_analysis_enabled(loaded_settings):
                ai_readiness_assembler = create_ai_readiness_assessment_assembler()
                repo_id = str(getattr(repository, "name", None) or repository.path)
                ai_readiness_cfg = ai_readiness_analysis_settings(loaded_settings)
                pack_on = ai_readiness_pack_enabled(loaded_settings)
                if not pack_on:
                    ai_readiness_section = ai_readiness_assembler.assemble_disabled(
                        repository_id=repo_id,
                        reason="ai_readiness_pack_disabled",
                    )
                else:
                    pack_findings = (
                        ai_readiness_pack_result.evaluation.findings
                        if ai_readiness_pack_result is not None
                        else ()
                    )
                    executed = 0
                    matched = 0
                    not_matched = 0
                    not_applicable = 0
                    failed = 0
                    if ai_readiness_pack_result is not None:
                        (
                            executed,
                            matched,
                            not_matched,
                            not_applicable,
                            failed,
                        ) = _count_rule_execution_statuses(
                            ai_readiness_pack_result.rule_execution_facts
                        )
                    ai_readiness_section = ai_readiness_assembler.assemble(
                        repository_id=repo_id,
                        findings=pack_findings,
                        pack_enabled=True,
                        rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=not_matched,
                        rules_not_applicable=not_applicable,
                        rules_failed=failed,
                        rule_execution_facts=(
                            ai_readiness_pack_result.rule_execution_facts
                            if ai_readiness_pack_result is not None
                            else ()
                        ),
                        evidence_pipeline=(
                            ai_readiness_pack_result.evidence_pipeline
                            if ai_readiness_pack_result is not None
                            else (
                                "repository_ai_readiness"
                                if repository_ai_readiness_evidence is not None
                                else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            ai_readiness_pack_result.evidence_fingerprint
                            if ai_readiness_pack_result is not None
                            else (
                                repository_ai_readiness_evidence.evidence_fingerprint
                                if repository_ai_readiness_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=(
                            f"rules.ai_readiness.enabled=true|"
                            f"evidence.repository_ai_readiness.enabled="
                            f"{loaded_settings.evidence.repository_ai_readiness.enabled}"
                        ),
                        diagnostics=(
                            ai_readiness_pack_result.diagnostics
                            if ai_readiness_pack_result is not None
                            else ()
                        ),
                        include_findings=ai_readiness_cfg.include_findings,
                        include_coverage=ai_readiness_cfg.include_coverage,
                        include_limitations=ai_readiness_cfg.include_limitations,
                        include_traceability=ai_readiness_cfg.include_traceability,
                        include_execution_summary=ai_readiness_cfg.include_execution_summary,
                        include_synthesis=ai_readiness_cfg.include_synthesis,
                    )
                ai_readiness_write = write_ai_readiness_assessment_artifact(
                    ai_readiness_section,
                    report_paths.run_directory,
                )
                ai_readiness_assessment_artifact = ai_readiness_write.path
                ai_readiness_assessment_status = ai_readiness_section.status.value
                ai_readiness_assessment_finding_count = ai_readiness_write.finding_count
                ai_readiness_section_for_report = ai_readiness_section
        except Exception as error:  # noqa: BLE001 - isolate ai readiness failures
            ai_readiness_assessment_artifact = None
            ai_readiness_assessment_status = "failed"
            ai_readiness_assessment_finding_count = None
            ai_readiness_section_for_report = None
            warn(
                "AI Readiness assessment could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Phase 4.9.4 — Performance Intelligence inventory (+ synthesis when enabled).
        performance_assessment_artifact = None
        performance_assessment_status = None
        performance_assessment_finding_count = None
        performance_section_for_report = None
        try:
            from codestrata.application.performance.assessment.artifacts import (
                write_performance_assessment_artifact,
            )
            from codestrata.application.performance.assessment.factory import (
                create_performance_assessment_assembler,
                performance_analysis_enabled,
                performance_analysis_settings,
                performance_pack_enabled,
            )
            from codestrata.domain.performance.ids import HYGIENE_RULE_IDS

            if performance_analysis_enabled(loaded_settings):
                performance_assembler = create_performance_assessment_assembler()
                repo_id = str(getattr(repository, "name", None) or repository.path)
                performance_cfg = performance_analysis_settings(loaded_settings)
                pack_on = performance_pack_enabled(loaded_settings)
                if not pack_on:
                    performance_section = performance_assembler.assemble_disabled(
                        repository_id=repo_id,
                        reason="performance_pack_disabled",
                    )
                else:
                    pack_findings = (
                        performance_pack_result.evaluation.findings
                        if performance_pack_result is not None
                        else ()
                    )
                    executed = 0
                    matched = 0
                    not_matched = 0
                    not_applicable = 0
                    failed = 0
                    if performance_pack_result is not None:
                        (
                            executed,
                            matched,
                            not_matched,
                            not_applicable,
                            failed,
                        ) = _count_rule_execution_statuses(
                            performance_pack_result.rule_execution_facts
                        )
                    performance_section = performance_assembler.assemble(
                        repository_id=repo_id,
                        findings=pack_findings,
                        pack_enabled=True,
                        rules_planned=len(HYGIENE_RULE_IDS),
                        rules_executed=executed,
                        rules_matched=matched,
                        rules_not_matched=not_matched,
                        rules_not_applicable=not_applicable,
                        rules_failed=failed,
                        rule_execution_facts=(
                            performance_pack_result.rule_execution_facts
                            if performance_pack_result is not None
                            else ()
                        ),
                        evidence_pipeline=(
                            performance_pack_result.evidence_pipeline
                            if performance_pack_result is not None
                            else (
                                "repository_performance"
                                if repository_performance_evidence is not None
                                else "not_configured"
                            )
                        ),
                        evidence_fingerprint=(
                            performance_pack_result.evidence_fingerprint
                            if performance_pack_result is not None
                            else (
                                repository_performance_evidence.evidence_fingerprint
                                if repository_performance_evidence is not None
                                else ""
                            )
                        ),
                        configuration_payload=(
                            f"rules.performance.enabled=true|"
                            f"evidence.repository_performance.enabled="
                            f"{loaded_settings.evidence.repository_performance.enabled}"
                        ),
                        diagnostics=(
                            performance_pack_result.diagnostics
                            if performance_pack_result is not None
                            else ()
                        ),
                        include_findings=performance_cfg.include_findings,
                        include_coverage=performance_cfg.include_coverage,
                        include_limitations=performance_cfg.include_limitations,
                        include_traceability=performance_cfg.include_traceability,
                        include_execution_summary=performance_cfg.include_execution_summary,
                        include_synthesis=performance_cfg.include_synthesis,
                    )
                performance_write = write_performance_assessment_artifact(
                    performance_section,
                    report_paths.run_directory,
                )
                performance_assessment_artifact = performance_write.path
                performance_assessment_status = performance_section.status.value
                performance_assessment_finding_count = performance_write.finding_count
                performance_section_for_report = performance_section
        except Exception as error:  # noqa: BLE001 - isolate performance failures
            performance_assessment_artifact = None
            performance_assessment_status = "failed"
            performance_assessment_finding_count = None
            performance_section_for_report = None
            warn(
                "Performance assessment could not be built; "
                "remaining assessment content was kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        # Epic 5 Slice 5.11 — consolidate duplicate Findings before recommendations
        # so Recommendation IDs use canonical Finding IDs (no post-creation churn).
        finding_correlation_payload: tuple[dict[str, object], ...] = ()
        try:
            from codestrata.application.findings.consolidation import (
                consolidate_rule_evaluation,
            )
            from codestrata.application.findings.correlation import (
                correlate_rule_evaluation,
            )

            rule_evaluation, _finding_consolidation = consolidate_rule_evaluation(
                rule_evaluation
            )
            # Epic 5 Slice 5.12 — correlate distinct Findings after consolidation.
            rule_evaluation, finding_correlation_result = correlate_rule_evaluation(
                rule_evaluation
            )
            finding_correlation_payload = tuple(
                item.canonical_dict()
                for item in finding_correlation_result.correlations
            )
            findings_artifact = write_findings_artifact(
                rule_evaluation,
                report_paths.run_directory,
            )
        except Exception as error:  # noqa: BLE001 - consolidation must not abort assessment
            warn(
                "Finding consolidation/correlation skipped; continuing with "
                "pre-consolidation findings. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        try:
            with benchmark_recorder.stage("recommendation_generation"):
                recommendation_result = active_recommendation_engine.evaluate_pipeline_result(
                    pipeline_result=graph_pipeline_result,
                    evaluation=rule_evaluation,
                )
                recommendations_artifact = write_recommendations_artifact(
                    recommendation_result,
                    report_paths.run_directory,
                )
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"[recommendation_engine] Recommendation evaluation failed: "
                f"{sanitize_provider_text(str(error))}"
            ) from error
        for line in format_rule_console_summary(
            rule_evaluation,
            recommendation_count=recommendation_result.recommendation_count,
        ):
            active_console.print(line)
        rules_elapsed_ms = round((perf_counter() - rules_started) * 1000, 2)
        benchmark_recorder.record("finding_synthesis", rules_elapsed_ms)

        analysis_context: LLMAnalysisContext | None = None
        assessment_result: ModernizationAssessmentResult | None = None
        ai_ms: float | None = None
        ai_status = AIExecutionStatus.NOT_REQUESTED
        ai_failure_message: str | None = None
        ai_attempt: AIAttemptInfo | None = None
        ai_execution_document: dict[str, object] | None = None
        enrichment_result: AiEnrichmentResult | None = None

        if mode == AssessmentMode.AI_ENHANCED:
            from codestrata.ai.enrichment import DEFAULT_MAX_CONTEXT_CHARACTERS
            from codestrata.ai.enrichment.artifacts import (
                AI_ENRICHMENT_FILENAME,
                try_write_ai_enrichment_artifact,
            )

            resolved_model_id = resolve_assess_model_id(
                cli_model_id=model_id,
                settings=loaded_settings,
            )
            context_limit = (
                max_context_characters
                if max_context_characters is not None
                else DEFAULT_MAX_CONTEXT_CHARACTERS
            )
            ai_started = perf_counter()
            try:
                with benchmark_recorder.stage("ai_enrichment"):
                    (
                        analysis_context,
                        assessment_result,
                        ai_attempt,
                        enrichment_result,
                    ) = _run_ai_assessment(
                        analysis_result=analysis_result,
                        settings=loaded_settings,
                        resolved_model_id=resolved_model_id,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        context_limit=context_limit,
                        provider=provider,
                        prompt_builder=prompt_builder,
                        agent=agent,
                        context_builder=context_builder,
                        rule_evaluation=rule_evaluation,
                        recommendation_result=recommendation_result,
                        repository_graph=graph_pipeline_result.repository_graph,
                        stage=stage,
                    )
                ai_status = AIExecutionStatus.SUCCEEDED
                ai_execution_document = build_ai_execution_document(
                    status=AIExecutionStatus.SUCCEEDED,
                    attempt=ai_attempt,
                    analysis_context=analysis_context,
                    assessment_result=assessment_result,
                    failure_message=None,
                )
                if enrichment_result is not None:
                    written_enrichment = try_write_ai_enrichment_artifact(
                        enrichment_result,
                        report_paths.run_directory,
                    )
                    if written_enrichment is None:
                        warn(
                            "AI enrichment artifact could not be written; "
                            "customer HTML and JSON reports were kept. "
                            f"Expected file: {AI_ENRICHMENT_FILENAME}"
                        )
            except AssessmentCommandError as error:
                ai_status = error.ai_status or AIExecutionStatus.PROVIDER_FAILED
                ai_attempt = error.ai_attempt
                ai_execution_document = error.execution_document
                ai_failure_message = error.customer_message or customer_failure_message(ai_status)
                detail = sanitize_provider_text(str(error))
                if ai_attempt is not None and ai_attempt.failure_detail is None:
                    ai_attempt = ai_attempt.model_copy(update={"failure_detail": detail})
                elif ai_attempt is None:
                    ai_attempt = AIAttemptInfo(
                        model_id=resolved_model_id,
                        stages_completed=stages_for_status(ai_status),
                        failure_code=failure_code_for_status(ai_status),
                        failure_detail=detail,
                    )
                code = failure_code_for_status(ai_status) or "AI_FAILED"
                warnings.append(
                    f"{ai_failure_message} [{code}] "
                    "Deterministic HTML and JSON reports were still written."
                )
                warn(warnings[-1])
                if analysis_context is None:
                    try:
                        from codestrata.ai.contracts import LLMAnalysisContextBuilder

                        analysis_context = (context_builder or LLMAnalysisContextBuilder()).build(
                            analysis_result
                        )
                    except Exception:  # noqa: BLE001 - best effort only
                        analysis_context = None
                if ai_execution_document is None:
                    ai_execution_document = build_ai_execution_document(
                        status=ai_status,
                        attempt=ai_attempt,
                        analysis_context=analysis_context,
                        raw_model_text=None,
                        parsed_model_response=None,
                        accepted_ai_result=None,
                        failure_message=ai_failure_message,
                        failure_detail=(
                            ai_attempt.failure_detail if ai_attempt is not None else None
                        ),
                    )
            ai_ms = round((perf_counter() - ai_started) * 1000, 2)
            if ai_attempt is not None and ai_attempt.latency_ms is None and ai_ms is not None:
                ai_attempt = ai_attempt.model_copy(update={"latency_ms": ai_ms})

        stage("Generating report...")
        # Reuse the run directory created before optional AI so graph artifacts remain
        # alongside HTML/JSON for the same assessment run.
        from codestrata.reporting.html_v2 import (
            build_highlighted_versions,
            default_report_artifacts,
        )

        generated_at = now()
        provisional_total = round((perf_counter() - total_started) * 1000, 2)
        from codestrata.application.runtime_performance.metrics import peak_rss_mb

        peak_memory = peak_rss_mb() if runtime_cfg.capture_peak_rss else None
        include_ai_enrichment = (
            enrichment_result is not None and ai_status == AIExecutionStatus.SUCCEEDED
        )
        architecture_report_section = None
        architecture_report_enabled = loaded_settings.report.sections.architecture.enabled
        architecture_report_status = None
        architecture_report_section_version = None
        architecture_report_finding_count = None
        architecture_report_conclusion_count = None
        architecture_report_recommendation_group_count = None
        architecture_report_adapter_ms = None
        include_architecture_assessment_artifact = architecture_assessment_artifact is not None
        report_architecture_cfg = loaded_settings.report.sections.architecture
        if report_architecture_cfg.enabled and architecture_section_for_report is not None:
            from codestrata.reporting.architecture.adapter import ArchitectureReportAdapter

            adapter_started = perf_counter()
            try:
                architecture_report_section = ArchitectureReportAdapter().adapt(
                    architecture_section_for_report,
                    include_executive_summary=(report_architecture_cfg.include_executive_summary),
                    include_metrics=report_architecture_cfg.include_metrics,
                    include_conclusions=report_architecture_cfg.include_conclusions,
                    include_recommendation_groups=(
                        report_architecture_cfg.include_recommendation_groups
                    ),
                    include_findings=report_architecture_cfg.include_findings,
                    include_coverage=report_architecture_cfg.include_coverage,
                    include_limitations=report_architecture_cfg.include_limitations,
                    include_traceability=report_architecture_cfg.include_traceability,
                    include_strengths=report_architecture_cfg.include_strengths,
                )
                architecture_report_adapter_ms = round((perf_counter() - adapter_started) * 1000, 2)
                architecture_report_status = architecture_report_section.status
                architecture_report_section_version = architecture_report_section.section_version
                architecture_report_finding_count = len(architecture_report_section.findings)
                architecture_report_conclusion_count = len(architecture_report_section.conclusions)
                architecture_report_recommendation_group_count = len(
                    architecture_report_section.recommendation_groups
                )
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                architecture_report_section = None
                architecture_report_adapter_ms = round((perf_counter() - adapter_started) * 1000, 2)
                architecture_report_status = "failed"
                warn(
                    "Architecture report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_architecture_cfg.enabled:
            architecture_report_status = "unavailable"
            warn(
                "Architecture report section enabled, but no architecture assessment "
                "section was available for this run."
            )
        technical_debt_report_section = None
        technical_debt_report_enabled = loaded_settings.report.sections.technical_debt.enabled
        technical_debt_report_status = None
        technical_debt_report_section_version = None
        technical_debt_report_finding_count = None
        technical_debt_report_conclusion_count = None
        technical_debt_report_hotspot_count = None
        technical_debt_report_adapter_ms = None
        report_technical_debt_cfg = loaded_settings.report.sections.technical_debt
        if report_technical_debt_cfg.enabled and technical_debt_section_for_report is not None:
            from codestrata.reporting.technical_debt.adapter import TechnicalDebtReportAdapter

            td_adapter_started = perf_counter()
            try:
                technical_debt_report_section = TechnicalDebtReportAdapter().adapt(
                    technical_debt_section_for_report,
                    include_executive_summary=(report_technical_debt_cfg.include_executive_summary),
                    include_metrics=report_technical_debt_cfg.include_metrics,
                    include_themes=report_technical_debt_cfg.include_themes,
                    include_hotspots=report_technical_debt_cfg.include_hotspots,
                    include_conclusions=report_technical_debt_cfg.include_conclusions,
                    include_recommendations=(report_technical_debt_cfg.include_recommendations),
                    include_test_observation=(report_technical_debt_cfg.include_test_observation),
                    include_coverage=report_technical_debt_cfg.include_coverage,
                    include_limitations=report_technical_debt_cfg.include_limitations,
                    include_traceability=report_technical_debt_cfg.include_traceability,
                )
                technical_debt_report_adapter_ms = round(
                    (perf_counter() - td_adapter_started) * 1000, 2
                )
                technical_debt_report_status = technical_debt_report_section.status
                technical_debt_report_section_version = (
                    technical_debt_report_section.section_version
                )
                technical_debt_report_finding_count = int(
                    technical_debt_report_section.metadata.get("production_finding_count", "0")
                    or "0"
                )
                technical_debt_report_conclusion_count = len(
                    technical_debt_report_section.conclusions
                )
                technical_debt_report_hotspot_count = len(
                    technical_debt_report_section.top_production_hotspots
                )
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                technical_debt_report_section = None
                technical_debt_report_adapter_ms = round(
                    (perf_counter() - td_adapter_started) * 1000, 2
                )
                technical_debt_report_status = "failed"
                warn(
                    "Technical debt report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_technical_debt_cfg.enabled:
            technical_debt_report_status = "unavailable"
            warn(
                "Technical debt report section enabled, but no technical debt "
                "assessment section was available for this run."
            )
        dependency_report_section = None
        dependency_report_enabled = loaded_settings.report.sections.dependency.enabled
        dependency_report_status = None
        dependency_report_section_version = None
        dependency_report_finding_count = None
        dependency_report_conclusion_count = None
        dependency_report_hotspot_count = None
        dependency_report_adapter_ms = None
        report_dependency_cfg = loaded_settings.report.sections.dependency
        if report_dependency_cfg.enabled and dependency_section_for_report is not None:
            from codestrata.reporting.dependency.adapter import DependencyReportAdapter

            dep_adapter_started = perf_counter()
            try:
                dependency_report_section = DependencyReportAdapter().adapt(
                    dependency_section_for_report,
                    include_executive_summary=(report_dependency_cfg.include_executive_summary),
                    include_landscape=report_dependency_cfg.include_landscape,
                    include_production_health=(report_dependency_cfg.include_production_health),
                    include_test_observations=(report_dependency_cfg.include_test_observations),
                    include_hotspots=report_dependency_cfg.include_hotspots,
                    include_conclusions=report_dependency_cfg.include_conclusions,
                    include_recommendations=(report_dependency_cfg.include_recommendations),
                    include_coverage=report_dependency_cfg.include_coverage,
                    include_limitations=report_dependency_cfg.include_limitations,
                    include_traceability=report_dependency_cfg.include_traceability,
                )
                dependency_report_adapter_ms = round(
                    (perf_counter() - dep_adapter_started) * 1000, 2
                )
                dependency_report_status = dependency_report_section.status
                dependency_report_section_version = dependency_report_section.section_version
                dependency_report_finding_count = int(
                    dependency_report_section.metadata.get("production_finding_count", "0") or "0"
                )
                dependency_report_conclusion_count = len(dependency_report_section.conclusions)
                dependency_report_hotspot_count = len(dependency_report_section.manifest_hotspots)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                dependency_report_section = None
                dependency_report_adapter_ms = round(
                    (perf_counter() - dep_adapter_started) * 1000, 2
                )
                dependency_report_status = "failed"
                warn(
                    "Dependency report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_dependency_cfg.enabled:
            dependency_report_status = "unavailable"
            warn(
                "Dependency report section enabled, but no dependency assessment "
                "section was available for this run."
            )
        security_report_section = None
        security_report_enabled = loaded_settings.report.sections.security.enabled
        security_report_status = None
        security_report_section_version = None
        security_report_finding_count = None
        security_report_conclusion_count = None
        security_report_hotspot_count = None
        security_report_adapter_ms = None
        report_security_cfg = loaded_settings.report.sections.security
        if report_security_cfg.enabled and security_section_for_report is not None:
            from codestrata.reporting.security.adapter import SecurityReportAdapter

            sec_adapter_started = perf_counter()
            try:
                security_report_section = SecurityReportAdapter().adapt(
                    security_section_for_report,
                    include_executive_summary=(report_security_cfg.include_executive_summary),
                    include_coverage=report_security_cfg.include_coverage,
                    include_findings=report_security_cfg.include_findings,
                    include_themes=report_security_cfg.include_themes,
                    include_hotspots=report_security_cfg.include_hotspots,
                    include_conclusions=report_security_cfg.include_conclusions,
                    include_recommendations=(report_security_cfg.include_recommendations),
                    include_diagnostics=report_security_cfg.include_diagnostics,
                    include_limitations=report_security_cfg.include_limitations,
                    include_traceability=report_security_cfg.include_traceability,
                )
                security_report_adapter_ms = round((perf_counter() - sec_adapter_started) * 1000, 2)
                security_report_status = security_report_section.status
                security_report_section_version = security_report_section.section_version
                security_report_finding_count = int(
                    security_report_section.metadata.get("production_finding_count", "0") or "0"
                )
                security_report_conclusion_count = len(security_report_section.conclusions)
                security_report_hotspot_count = len(security_report_section.hotspots)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                security_report_section = None
                security_report_adapter_ms = round((perf_counter() - sec_adapter_started) * 1000, 2)
                security_report_status = "failed"
                warn(
                    "Security report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_security_cfg.enabled:
            security_report_status = "unavailable"
            warn(
                "Security report section enabled, but no security assessment "
                "section was available for this run."
            )
        testing_report_section = None
        testing_report_enabled = loaded_settings.report.sections.testing.enabled
        testing_report_status = None
        testing_report_section_version = None
        testing_report_finding_count = None
        testing_report_conclusion_count = None
        testing_report_adapter_ms = None
        report_testing_cfg = loaded_settings.report.sections.testing
        if report_testing_cfg.enabled and testing_section_for_report is not None:
            from codestrata.reporting.testing.adapter import TestingReportAdapter

            test_adapter_started = perf_counter()
            try:
                testing_report_section = TestingReportAdapter().adapt(
                    testing_section_for_report,
                    include_executive_summary=(report_testing_cfg.include_executive_summary),
                    include_coverage=report_testing_cfg.include_coverage,
                    include_inventory=report_testing_cfg.include_inventory,
                    include_execution_summary=(report_testing_cfg.include_execution_summary),
                    include_themes=report_testing_cfg.include_themes,
                    include_conclusions=report_testing_cfg.include_conclusions,
                    include_recommendations=(report_testing_cfg.include_recommendations),
                    include_diagnostics=report_testing_cfg.include_diagnostics,
                    include_limitations=report_testing_cfg.include_limitations,
                    include_traceability=report_testing_cfg.include_traceability,
                )
                testing_report_adapter_ms = round((perf_counter() - test_adapter_started) * 1000, 2)
                testing_report_status = testing_report_section.status
                testing_report_section_version = testing_report_section.section_version
                testing_report_finding_count = int(
                    testing_report_section.metadata.get("finding_count", "0") or "0"
                )
                testing_report_conclusion_count = len(testing_report_section.conclusions)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                testing_report_section = None
                testing_report_adapter_ms = round((perf_counter() - test_adapter_started) * 1000, 2)
                testing_report_status = "failed"
                warn(
                    "Test report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_testing_cfg.enabled:
            testing_report_status = "unavailable"
            warn(
                "Test report section enabled, but no testing assessment "
                "section was available for this run."
            )
        cloud_report_section = None
        cloud_report_enabled = loaded_settings.report.sections.cloud.enabled
        cloud_report_status = None
        cloud_report_section_version = None
        cloud_report_finding_count = None
        cloud_report_conclusion_count = None
        cloud_report_adapter_ms = None
        report_cloud_cfg = loaded_settings.report.sections.cloud
        if report_cloud_cfg.enabled and cloud_section_for_report is not None:
            from codestrata.reporting.cloud.adapter import CloudReportAdapter

            cloud_adapter_started = perf_counter()
            try:
                include_inventory = (
                    report_cloud_cfg.include_inventory and report_cloud_cfg.include_findings
                )
                cloud_report_section = CloudReportAdapter().adapt(
                    cloud_section_for_report,
                    include_executive_summary=(report_cloud_cfg.include_executive_summary),
                    include_coverage=report_cloud_cfg.include_coverage,
                    include_inventory=include_inventory,
                    include_execution_summary=(report_cloud_cfg.include_execution_summary),
                    include_themes=report_cloud_cfg.include_themes,
                    include_conclusions=report_cloud_cfg.include_conclusions,
                    include_recommendations=(report_cloud_cfg.include_recommendations),
                    include_diagnostics=report_cloud_cfg.include_diagnostics,
                    include_limitations=report_cloud_cfg.include_limitations,
                    include_traceability=report_cloud_cfg.include_traceability,
                )
                cloud_report_adapter_ms = round((perf_counter() - cloud_adapter_started) * 1000, 2)
                cloud_report_status = cloud_report_section.status
                cloud_report_section_version = cloud_report_section.section_version
                cloud_report_finding_count = int(
                    cloud_report_section.metadata.get("finding_count", "0") or "0"
                )
                cloud_report_conclusion_count = len(cloud_report_section.conclusions)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                cloud_report_section = None
                cloud_report_adapter_ms = round((perf_counter() - cloud_adapter_started) * 1000, 2)
                cloud_report_status = "failed"
                warn(
                    "Cloud report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_cloud_cfg.enabled:
            cloud_report_status = "unavailable"
            warn(
                "Cloud report section enabled, but no cloud assessment "
                "section was available for this run."
            )
        ai_readiness_report_section = None
        ai_readiness_report_enabled = loaded_settings.report.sections.ai_readiness.enabled
        ai_readiness_report_status = None
        ai_readiness_report_section_version = None
        ai_readiness_report_finding_count = None
        ai_readiness_report_conclusion_count = None
        ai_readiness_report_adapter_ms = None
        report_ai_cfg = loaded_settings.report.sections.ai_readiness
        if report_ai_cfg.enabled and ai_readiness_section_for_report is not None:
            from codestrata.reporting.ai_readiness.adapter import AiReadinessReportAdapter

            ai_adapter_started = perf_counter()
            try:
                include_inventory = (
                    report_ai_cfg.include_inventory and report_ai_cfg.include_findings
                )
                ai_readiness_report_section = AiReadinessReportAdapter().adapt(
                    ai_readiness_section_for_report,
                    include_executive_summary=(report_ai_cfg.include_executive_summary),
                    include_coverage=report_ai_cfg.include_coverage,
                    include_inventory=include_inventory,
                    include_execution_summary=(report_ai_cfg.include_execution_summary),
                    include_themes=report_ai_cfg.include_themes,
                    include_conclusions=report_ai_cfg.include_conclusions,
                    include_recommendations=(report_ai_cfg.include_recommendations),
                    include_diagnostics=report_ai_cfg.include_diagnostics,
                    include_limitations=report_ai_cfg.include_limitations,
                    include_traceability=report_ai_cfg.include_traceability,
                )
                ai_readiness_report_adapter_ms = round(
                    (perf_counter() - ai_adapter_started) * 1000, 2
                )
                ai_readiness_report_status = ai_readiness_report_section.status
                ai_readiness_report_section_version = ai_readiness_report_section.section_version
                ai_readiness_report_finding_count = int(
                    ai_readiness_report_section.metadata.get("finding_count", "0") or "0"
                )
                ai_readiness_report_conclusion_count = len(ai_readiness_report_section.conclusions)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                ai_readiness_report_section = None
                ai_readiness_report_adapter_ms = round(
                    (perf_counter() - ai_adapter_started) * 1000, 2
                )
                ai_readiness_report_status = "failed"
                warn(
                    "AI Readiness report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_ai_cfg.enabled:
            ai_readiness_report_status = "unavailable"
            warn(
                "AI Readiness report section enabled, but no AI Readiness "
                "assessment section was available for this run."
            )
        performance_report_section = None
        performance_report_enabled = loaded_settings.report.sections.performance.enabled
        performance_report_status = None
        performance_report_section_version = None
        performance_report_finding_count = None
        performance_report_conclusion_count = None
        performance_report_adapter_ms = None
        report_perf_cfg = loaded_settings.report.sections.performance
        if report_perf_cfg.enabled and performance_section_for_report is not None:
            from codestrata.reporting.performance.adapter import PerformanceReportAdapter

            perf_adapter_started = perf_counter()
            try:
                include_inventory = (
                    report_perf_cfg.include_inventory and report_perf_cfg.include_findings
                )
                performance_report_section = PerformanceReportAdapter().adapt(
                    performance_section_for_report,
                    include_executive_summary=(report_perf_cfg.include_executive_summary),
                    include_coverage=report_perf_cfg.include_coverage,
                    include_inventory=include_inventory,
                    include_execution_summary=(report_perf_cfg.include_execution_summary),
                    include_themes=report_perf_cfg.include_themes,
                    include_conclusions=report_perf_cfg.include_conclusions,
                    include_recommendations=(report_perf_cfg.include_recommendations),
                    include_diagnostics=report_perf_cfg.include_diagnostics,
                    include_limitations=report_perf_cfg.include_limitations,
                    include_traceability=report_perf_cfg.include_traceability,
                )
                performance_report_adapter_ms = round(
                    (perf_counter() - perf_adapter_started) * 1000, 2
                )
                performance_report_status = performance_report_section.status
                performance_report_section_version = performance_report_section.section_version
                performance_report_finding_count = int(
                    performance_report_section.metadata.get("finding_count", "0") or "0"
                )
                performance_report_conclusion_count = len(performance_report_section.conclusions)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                performance_report_section = None
                performance_report_adapter_ms = round(
                    (perf_counter() - perf_adapter_started) * 1000, 2
                )
                performance_report_status = "failed"
                warn(
                    "Performance report section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        elif report_perf_cfg.enabled:
            performance_report_status = "unavailable"
            warn(
                "Performance report section enabled, but no Performance "
                "assessment section was available for this run."
            )
        roadmap_report_section = None
        roadmap_report_enabled = loaded_settings.report.sections.roadmap.enabled
        roadmap_report_status = None
        roadmap_report_section_version = None
        roadmap_report_initiative_count = None
        roadmap_report_phase_count = None
        roadmap_report_adapter_ms = None
        report_roadmap_cfg = loaded_settings.report.sections.roadmap
        if report_roadmap_cfg.enabled:
            from codestrata.application.roadmap import ModernizationRoadmapEngine
            from codestrata.reporting.roadmap.adapter import RoadmapReportAdapter

            roadmap_adapter_started = perf_counter()
            try:
                roadmap_domain = ModernizationRoadmapEngine().generate_from_artifacts(
                    recommendation_result=recommendation_result,
                    rule_evaluation=rule_evaluation,
                    analysis_result=analysis_result,
                )
                roadmap_report_section = RoadmapReportAdapter().adapt(
                    roadmap_domain,
                    include_assumptions=report_roadmap_cfg.include_assumptions,
                    include_limitations=report_roadmap_cfg.include_limitations,
                    include_evidence=report_roadmap_cfg.include_evidence,
                )
                roadmap_report_adapter_ms = round(
                    (perf_counter() - roadmap_adapter_started) * 1000, 2
                )
                roadmap_report_status = roadmap_report_section.status
                roadmap_report_section_version = roadmap_report_section.section_version
                roadmap_report_initiative_count = roadmap_report_section.initiatives_total
                roadmap_report_phase_count = len(roadmap_report_section.phases)
            except Exception as error:  # noqa: BLE001 - isolate report adapter failures
                roadmap_report_section = None
                roadmap_report_adapter_ms = round(
                    (perf_counter() - roadmap_adapter_started) * 1000, 2
                )
                roadmap_report_status = "failed"
                warn(
                    "Modernization roadmap section could not be built; "
                    "remaining report content was kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )
        report_input = ModernizationReportInput(
            analysis_result=analysis_result,
            assessment_mode=mode,
            analysis_context=analysis_context,
            assessment_result=assessment_result,
            ai_status=ai_status,
            ai_failure_message=ai_failure_message,
            ai_attempt=ai_attempt,
            generated_at_utc=generated_at,
            report_title=report_title.strip() or DEFAULT_ASSESS_REPORT_TITLE,
            organization_name=organization_name,
            repository_reference=repository_reference,
            warnings=tuple(warnings),
            timing=AssessmentTiming(
                total_ms=provisional_total,
                scan_ms=scan_ms,
                analysis_ms=analysis_ms,
                static_analysis_ms=static_analysis_ms,
                ai_ms=ai_ms,
                report_ms=None,
                graph_ms=graph_elapsed_ms,
                rules_ms=rules_elapsed_ms,
                files_loaded=(shared_source_stats.files_loaded if shared_source_stats else None),
                files_skipped=(shared_source_stats.files_skipped if shared_source_stats else None),
                cache_hits=(shared_source_stats.cache_hits if shared_source_stats else None),
                cache_misses=(shared_source_stats.cache_misses if shared_source_stats else None),
                peak_rss_mb=peak_memory,
            ),
            assessment_rule_evaluation=rule_evaluation,
            assessment_recommendation_result=recommendation_result,
            finding_correlations=finding_correlation_payload,
            ai_enrichment=enrichment_result if include_ai_enrichment else None,
            highlighted_versions=build_highlighted_versions(graph_pipeline_result.repository_graph),
            report_artifacts=default_report_artifacts(
                include_ai_enrichment=include_ai_enrichment,
                include_ai_execution=ai_execution_document is not None,
                include_architecture_assessment=include_architecture_assessment_artifact,
            ),
            architecture_report=architecture_report_section,
            technical_debt_report=technical_debt_report_section,
            dependency_report=dependency_report_section,
            security_report=security_report_section,
            testing_report=testing_report_section,
            cloud_report=cloud_report_section,
            ai_readiness_report=ai_readiness_report_section,
            performance_report=performance_report_section,
            roadmap_report=roadmap_report_section,
            knowledge_repository_id=knowledge_session.repository_id,
            knowledge_run_id=knowledge_session.run_id,
            assessment_activation=activation_coverage,
        )
        try:
            if write_reports:
                with benchmark_recorder.stage("report_generation"):
                    try:
                        written_paths = write_modernization_assessment_reports(
                            report_input,
                            report_paths,
                        )
                    except ModernizationReportValidationError as error:
                        # AI bridge/report contract failures must not block deterministic
                        # Assessment Reports. Drop AI assessment payload and retry once.
                        if (
                            assessment_result is not None
                            and ai_status == AIExecutionStatus.SUCCEEDED
                        ):
                            detail = sanitize_provider_text(str(error))
                            ai_status = AIExecutionStatus.VALIDATION_FAILED
                            ai_failure_message = customer_failure_message(ai_status)
                            assessment_result = None
                            include_ai_enrichment = False
                            warnings.append(
                                f"{ai_failure_message} [AI_VALIDATION_FAILED] "
                                "Deterministic HTML and JSON reports were still written. "
                                f"Details: {detail}"
                            )
                            warn(warnings[-1])
                            report_input = report_input.model_copy(
                                update={
                                    "assessment_result": None,
                                    "ai_status": ai_status,
                                    "ai_failure_message": ai_failure_message,
                                    "ai_enrichment": None,
                                    "warnings": tuple(warnings),
                                }
                            )
                            written_paths = write_modernization_assessment_reports(
                                report_input,
                                report_paths,
                            )
                        else:
                            raise
                if ai_execution_document is not None:
                    written = try_write_ai_execution_artifact(
                        written_paths.run_directory,
                        ai_execution_document,
                    )
                    if written is None:
                        warn(
                            "AI execution artifact could not be written; "
                            "customer HTML and JSON reports were kept. "
                            f"Expected file: {AI_EXECUTION_FILENAME}"
                        )
            else:
                report_paths.run_directory.mkdir(parents=True, exist_ok=True)
                written_paths = report_paths
                warn("Report file generation skipped (write_reports=false).")
        except ModernizationReportValidationError as error:
            raise AssessmentCommandError(
                f"Report validation or write failure: {sanitize_provider_text(str(error))}"
            ) from error
        except OSError as error:
            raise AssessmentCommandError(
                f"Report validation or write failure: {sanitize_provider_text(str(error))}"
            ) from error
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"Report validation or write failure: {sanitize_provider_text(str(error))}"
            ) from error

        if write_reports:
            try:
                promoted = promote_staged_report(written_paths)
                # Point subsequent result paths at promoted current/ when staged.
                if promoted != written_paths.run_directory:
                    written_paths = ReportPaths(
                        directory=promoted,
                        text_report=promoted / "report.txt",
                        json_report=promoted / "assessment.json",
                        html_report=promoted / "assessment.html",
                        timestamp=written_paths.timestamp,
                        repository_name=written_paths.repository_name,
                        run_id=written_paths.run_id,
                        heads_directory=promoted / "heads",
                        repository_id=written_paths.repository_id,
                        staging=False,
                        artifact_root=written_paths.artifact_root,
                    )
                    active_console.print(
                        f"Assessment report: assessments/"
                        f"{written_paths.repository_id or written_paths.repository_name}/current/"
                    )
            except Exception as error:  # noqa: BLE001 - retention must not fail assessment
                warn(
                    "Report lifecycle promotion failed; staged assessment reports were kept. "
                    f"Details: {sanitize_provider_text(str(error))}"
                )

        total_ms = round((perf_counter() - total_started) * 1000, 2)

        knowledge_corpus_id = None
        knowledge_document_count = None
        knowledge_chunk_count = None
        knowledge_corpus_artifact_path = None
        knowledge_index_status = None
        knowledge_vector_count = None
        knowledge_index_artifact_path = None
        knowledge_index_fingerprint = None
        # Platform RAG projection/indexing is owned by codestrata_platform.
        # Community assess persists assessment artifacts only (knowledge_session).

        result = _build_command_result(
            repository_name=repository.name,
            report_paths=written_paths,
            mode=mode,
            analysis_result=analysis_result,
            assessment_result=assessment_result,
            ai_status=ai_status,
            ai_attempt=ai_attempt,
            duration_ms=total_ms,
            graph_artifacts=graph_artifacts,
            rule_evaluation=rule_evaluation,
            findings_artifact=findings_artifact,
            recommendation_result=recommendation_result,
            recommendations_artifact=recommendations_artifact,
            architecture_conclusion_count=architecture_conclusion_count,
            architecture_conclusions_artifact=architecture_conclusions_artifact,
            architecture_assessment_status=architecture_assessment_status,
            architecture_assessment_finding_count=architecture_assessment_finding_count,
            architecture_assessment_artifact=architecture_assessment_artifact,
            technical_debt_assessment_status=technical_debt_assessment_status,
            technical_debt_assessment_finding_count=technical_debt_assessment_finding_count,
            technical_debt_assessment_artifact=technical_debt_assessment_artifact,
            dependency_assessment_status=dependency_assessment_status,
            dependency_assessment_finding_count=dependency_assessment_finding_count,
            dependency_assessment_artifact=dependency_assessment_artifact,
            dependency_evidence_status=dependency_evidence_status,
            dependency_evidence_declaration_count=dependency_evidence_declaration_count,
            dependency_evidence_artifact=dependency_evidence_artifact,
            repository_sensitive_evidence_status=repository_sensitive_evidence_status,
            repository_sensitive_evidence_artifact_count=(
                repository_sensitive_evidence_artifact_count
            ),
            repository_sensitive_evidence_configuration_fact_count=(
                repository_sensitive_evidence_configuration_fact_count
            ),
            repository_sensitive_evidence_artifact=(repository_sensitive_evidence_artifact),
            repository_testing_evidence_status=repository_testing_evidence_status,
            repository_testing_evidence_candidate_count=(
                repository_testing_evidence_candidate_count
            ),
            repository_testing_evidence_framework_count=(
                repository_testing_evidence_framework_count
            ),
            repository_testing_evidence_artifact=(repository_testing_evidence_artifact),
            repository_cloud_evidence_status=repository_cloud_evidence_status,
            repository_cloud_evidence_candidate_count=(repository_cloud_evidence_candidate_count),
            repository_cloud_evidence_technology_count=(repository_cloud_evidence_technology_count),
            repository_cloud_evidence_artifact=(repository_cloud_evidence_artifact),
            repository_ai_readiness_evidence_status=(repository_ai_readiness_evidence_status),
            repository_ai_readiness_evidence_candidate_count=(
                repository_ai_readiness_evidence_candidate_count
            ),
            repository_ai_readiness_evidence_technology_count=(
                repository_ai_readiness_evidence_technology_count
            ),
            repository_ai_readiness_evidence_artifact=(repository_ai_readiness_evidence_artifact),
            repository_performance_evidence_status=(repository_performance_evidence_status),
            repository_performance_evidence_candidate_count=(
                repository_performance_evidence_candidate_count
            ),
            repository_performance_evidence_technology_count=(
                repository_performance_evidence_technology_count
            ),
            repository_performance_evidence_artifact=(repository_performance_evidence_artifact),
            security_assessment_status=security_assessment_status,
            security_assessment_finding_count=security_assessment_finding_count,
            security_assessment_artifact=security_assessment_artifact,
            testing_assessment_status=testing_assessment_status,
            testing_assessment_finding_count=testing_assessment_finding_count,
            testing_assessment_artifact=testing_assessment_artifact,
            cloud_assessment_status=cloud_assessment_status,
            cloud_assessment_finding_count=cloud_assessment_finding_count,
            cloud_assessment_artifact=cloud_assessment_artifact,
            ai_readiness_assessment_status=ai_readiness_assessment_status,
            ai_readiness_assessment_finding_count=ai_readiness_assessment_finding_count,
            ai_readiness_assessment_artifact=ai_readiness_assessment_artifact,
            performance_assessment_status=performance_assessment_status,
            performance_assessment_finding_count=performance_assessment_finding_count,
            performance_assessment_artifact=performance_assessment_artifact,
            architecture_report_enabled=architecture_report_enabled,
            architecture_report_status=architecture_report_status,
            architecture_report_section_version=architecture_report_section_version,
            architecture_report_finding_count=architecture_report_finding_count,
            architecture_report_conclusion_count=architecture_report_conclusion_count,
            architecture_report_recommendation_group_count=(
                architecture_report_recommendation_group_count
            ),
            architecture_report_adapter_ms=architecture_report_adapter_ms,
            technical_debt_report_enabled=technical_debt_report_enabled,
            technical_debt_report_status=technical_debt_report_status,
            technical_debt_report_section_version=technical_debt_report_section_version,
            technical_debt_report_finding_count=technical_debt_report_finding_count,
            technical_debt_report_conclusion_count=technical_debt_report_conclusion_count,
            technical_debt_report_hotspot_count=technical_debt_report_hotspot_count,
            technical_debt_report_adapter_ms=technical_debt_report_adapter_ms,
            dependency_report_enabled=dependency_report_enabled,
            dependency_report_status=dependency_report_status,
            dependency_report_section_version=dependency_report_section_version,
            dependency_report_finding_count=dependency_report_finding_count,
            dependency_report_conclusion_count=dependency_report_conclusion_count,
            dependency_report_hotspot_count=dependency_report_hotspot_count,
            dependency_report_adapter_ms=dependency_report_adapter_ms,
            security_report_enabled=security_report_enabled,
            security_report_status=security_report_status,
            security_report_section_version=security_report_section_version,
            security_report_finding_count=security_report_finding_count,
            security_report_conclusion_count=security_report_conclusion_count,
            security_report_hotspot_count=security_report_hotspot_count,
            security_report_adapter_ms=security_report_adapter_ms,
            testing_report_enabled=testing_report_enabled,
            testing_report_status=testing_report_status,
            testing_report_section_version=testing_report_section_version,
            testing_report_finding_count=testing_report_finding_count,
            testing_report_conclusion_count=testing_report_conclusion_count,
            testing_report_adapter_ms=testing_report_adapter_ms,
            cloud_report_enabled=cloud_report_enabled,
            cloud_report_status=cloud_report_status,
            cloud_report_section_version=cloud_report_section_version,
            cloud_report_finding_count=cloud_report_finding_count,
            cloud_report_conclusion_count=cloud_report_conclusion_count,
            cloud_report_adapter_ms=cloud_report_adapter_ms,
            ai_readiness_report_enabled=ai_readiness_report_enabled,
            ai_readiness_report_status=ai_readiness_report_status,
            ai_readiness_report_section_version=ai_readiness_report_section_version,
            ai_readiness_report_finding_count=ai_readiness_report_finding_count,
            ai_readiness_report_conclusion_count=ai_readiness_report_conclusion_count,
            ai_readiness_report_adapter_ms=ai_readiness_report_adapter_ms,
            performance_report_enabled=performance_report_enabled,
            performance_report_status=performance_report_status,
            performance_report_section_version=performance_report_section_version,
            performance_report_finding_count=performance_report_finding_count,
            performance_report_conclusion_count=performance_report_conclusion_count,
            performance_report_adapter_ms=performance_report_adapter_ms,
            roadmap_report_enabled=roadmap_report_enabled,
            roadmap_report_status=roadmap_report_status,
            roadmap_report_section_version=roadmap_report_section_version,
            roadmap_report_initiative_count=roadmap_report_initiative_count,
            roadmap_report_phase_count=roadmap_report_phase_count,
            roadmap_report_adapter_ms=roadmap_report_adapter_ms,
        )
        _print_success_summary(active_console, result, quiet=quiet, json_summary=json_summary)
        try:
            snapshot_id = knowledge_session.complete(
                graph_pipeline_result=graph_pipeline_result,
                rule_evaluation=rule_evaluation,
                recommendation_result=recommendation_result,
                ai_execution_document=ai_execution_document,
                enrichment_result=enrichment_result,
                configured_branch=resolved_branch,
            )
        except KnowledgeStoreError as error:
            raise AssessmentCommandError(
                f"Knowledge persistence failed: {sanitize_provider_text(str(error))}"
            ) from error
        except Exception as error:  # noqa: BLE001 - application boundary
            raise AssessmentCommandError(
                f"Knowledge persistence failed: {sanitize_provider_text(str(error))}"
            ) from error

        platform_ingest_status = "disabled"
        platform_organization_id = None
        platform_workspace_id = None
        platform_repository_id = None
        platform_assessment_id = None
        engine_assessment_id = None
        try:
            from codestrata.integration.commercial.artifacts.policy import (
                ArtifactPublishingPolicy,
            )
            from codestrata.integration.commercial.artifacts.publisher import (
                publish_artifacts_to_platform,
            )
            from codestrata.integration.commercial.configuration import (
                platform_client_from_settings,
                platform_config_from_settings,
            )
            from codestrata.integration.commercial.publisher import (
                publish_assessment_to_platform,
            )

            platform_config = platform_config_from_settings(loaded_settings)
            if platform_config.enabled:
                platform_client = platform_client_from_settings(loaded_settings)
                publish = publish_assessment_to_platform(
                    client=platform_client,
                    config=platform_config,
                    repository=repository,
                    configured_repository_url=loaded_settings.repository.url,
                    html_report_path=result.html_report_path if write_reports else None,
                    json_report_path=result.json_report_path if write_reports else None,
                )
                platform_ingest_status = publish.status
                platform_organization_id = publish.organization_id
                platform_workspace_id = publish.workspace_id
                platform_repository_id = publish.repository_id
                platform_assessment_id = publish.assessment_id
                engine_assessment_id = publish.engine_assessment_id
                if publish.status == "failed" and publish.message:
                    warn(
                        "Platform ingestion failed; local assessment reports were kept. "
                        f"Details: {sanitize_provider_text(publish.message)}"
                    )
                elif publish.status == "succeeded":
                    active_console.print(
                        "[green]Platform ingestion succeeded[/green] "
                        f"(assessment_id={publish.assessment_id})"
                    )
                    artifact_policy = ArtifactPublishingPolicy.from_settings(loaded_settings)
                    if (
                        artifact_policy.publishing_active()
                        and publish.assessment_id
                        and publish.engine_assessment_id
                    ):
                        artifact_batch = publish_artifacts_to_platform(
                            client=platform_client,
                            policy=artifact_policy,
                            engine_assessment_id=publish.engine_assessment_id,
                            platform_assessment_id=publish.assessment_id,
                            repository_name=repository.name,
                            html_report_path=(result.html_report_path if write_reports else None),
                            json_report_path=(result.json_report_path if write_reports else None),
                        )
                        if (
                            artifact_batch.status in {"failed", "partial"}
                            and artifact_batch.message
                        ):
                            warn(
                                "Platform artifact publishing failed; local reports were kept. "
                                f"Details: {sanitize_provider_text(artifact_batch.message)}"
                            )
                        elif artifact_batch.status == "succeeded":
                            active_console.print(
                                "[green]Platform artifact publishing succeeded[/green] "
                                f"({len(artifact_batch.published)} artifact(s))"
                            )
                            if artifact_policy.intelligence_processing_active():
                                try:
                                    intelligence = platform_client.process_assessment_intelligence(
                                        assessment_id=publish.assessment_id,
                                    )
                                    status = str(intelligence.get("status", "unknown"))
                                    active_console.print(
                                        "[green]Platform intelligence ingestion[/green] "
                                        f"(status={status})"
                                    )
                                except Exception as intelligence_error:  # noqa: BLE001
                                    warn(
                                        "Platform intelligence ingestion failed; "
                                        "artifacts were kept. Details: "
                                        f"{sanitize_provider_text(str(intelligence_error))}"
                                    )
        except Exception as error:  # noqa: BLE001 - never fail Community assess
            platform_ingest_status = "failed"
            warn(
                "Platform ingestion failed unexpectedly; local assessment reports were kept. "
                f"Details: {sanitize_provider_text(str(error))}"
            )

        final_result = result.model_copy(
            update={
                "knowledge_repository_id": knowledge_session.repository_id,
                "knowledge_run_id": knowledge_session.run_id,
                "knowledge_snapshot_id": snapshot_id,
                "knowledge_corpus_id": knowledge_corpus_id,
                "knowledge_document_count": knowledge_document_count,
                "knowledge_chunk_count": knowledge_chunk_count,
                "knowledge_corpus_artifact_path": knowledge_corpus_artifact_path,
                "knowledge_index_status": knowledge_index_status,
                "knowledge_vector_count": knowledge_vector_count,
                "knowledge_index_artifact_path": knowledge_index_artifact_path,
                "knowledge_index_fingerprint": knowledge_index_fingerprint,
                "platform_ingest_status": platform_ingest_status,
                "platform_organization_id": platform_organization_id,
                "platform_workspace_id": platform_workspace_id,
                "platform_repository_id": platform_repository_id,
                "platform_assessment_id": platform_assessment_id,
                "engine_assessment_id": engine_assessment_id,
            }
        )
        from codestrata.benchmark.finalize import maybe_write_run_benchmark

        maybe_write_run_benchmark(
            enabled=bool(loaded_settings.analysis.runtime.benchmark_collection),
            recorder=benchmark_recorder,
            label=repository.name,
            repository_path=Path(repository.path),
            run_directory=final_result.run_directory,
            report_json_path=final_result.json_report_path,
            command_result=final_result,
            ai_requested=mode == AssessmentMode.AI_ENHANCED,
        )
        return final_result


def run_assessment(
    repo: str | None,
    output_directory: Path,
    *,
    mode: AssessmentMode = AssessmentMode.DETERMINISTIC,
    model_id: str | None = None,
    branch: str | None = None,
    report_title: str = DEFAULT_ASSESS_REPORT_TITLE,
    organization_name: str | None = None,
    max_output_tokens: int = DEFAULT_ASSESS_MAX_OUTPUT_TOKENS,
    temperature: float = DEFAULT_ASSESS_TEMPERATURE,
    max_context_characters: int | None = None,
    pmd_path: str | None = None,
    pmd_profile: str | None = None,
    static_analysis_enabled: bool | None = None,
    config_path: Path = Path("codestrata.toml"),
    profile: str | None = None,
    assessment_activation: str | None = None,
    settings: CodestrataSettings | None = None,
    analysis_service: AnalysisService | None = None,
    provider: AIModelProvider | None = None,
    prompt_builder: ModernizationPromptBuilder | None = None,
    agent: ModernizationAssessmentAgent | None = None,
    scanner: _RepositoryScanner | None = None,
    context_builder: LLMAnalysisContextBuilder | None = None,
    graph_pipeline: GraphAssessmentPipeline | None = None,
    rule_engine: RuleEngine | None = None,
    recommendation_engine: RecommendationEngine | None = None,
    console: Console | None = None,
    clock: Callable[[], datetime] | None = None,
    verbose: bool = False,
    quiet: bool = False,
    json_summary: bool = False,
    knowledge_store: KnowledgeStore | None = None,
    write_reports: bool = True,
    force_reindex: bool = False,
) -> AssessmentCommandResult:
    """Orchestrate scan → analysis → graph pipeline → optional AI → HTML+JSON reports.

    Repository selection precedence:

    1. Explicit ``repo`` / ``--repo`` argument
    2. ``[repository].path`` from configuration
    3. ``[repository].url`` from configuration
    4. Clear actionable error (never a silent demo repository)
    """

    return AssessmentApplicationService().run(
        repo,
        output_directory,
        mode=mode,
        model_id=model_id,
        branch=branch,
        report_title=report_title,
        organization_name=organization_name,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        max_context_characters=max_context_characters,
        pmd_path=pmd_path,
        pmd_profile=pmd_profile,
        static_analysis_enabled=static_analysis_enabled,
        config_path=config_path,
        profile=profile,
        assessment_activation=assessment_activation,
        settings=settings,
        analysis_service=analysis_service,
        provider=provider,
        prompt_builder=prompt_builder,
        agent=agent,
        scanner=scanner,
        context_builder=context_builder,
        graph_pipeline=graph_pipeline,
        rule_engine=rule_engine,
        recommendation_engine=recommendation_engine,
        console=console,
        clock=clock,
        verbose=verbose,
        quiet=quiet,
        json_summary=json_summary,
        knowledge_store=knowledge_store,
        write_reports=write_reports,
        force_reindex=force_reindex,
    )


def resolve_assess_model_id(
    *,
    cli_model_id: str | None,
    settings: CodestrataSettings,
) -> str:
    """Resolve assess / Modernization Advisor model ID for the active provider."""

    from codestrata.ai.providers.factory import resolve_assess_model_id as _resolve

    return _resolve(cli_model_id=cli_model_id, settings=settings)


def resolve_bedrock_model_id(
    *,
    cli_model_id: str | None,
    settings: CodestrataSettings,
) -> str:
    """Backward-compatible alias for :func:`resolve_assess_model_id`."""

    return resolve_assess_model_id(cli_model_id=cli_model_id, settings=settings)


def modernization_report_basename(repository_name: str) -> str:
    """Return a sanitized assessment report basename (without extension)."""

    return f"{_slugify(repository_name)}-modernization-assessment"


def modernization_report_filename(repository_name: str) -> str:
    """Return a sanitized HTML report filename for a repository."""

    return f"{modernization_report_basename(repository_name)}.html"


def modernization_json_report_filename(repository_name: str) -> str:
    """Return a sanitized JSON report filename for a repository."""

    return f"{modernization_report_basename(repository_name)}.json"


def resolve_assessment_repository(
    cli_repo: str | None,
    settings: CodestrataSettings,
) -> str:
    """Resolve the repository source for ``codestrata assess``.

    Precedence: explicit CLI ``--repo``, then ``repository.path``, then
    ``repository.url``. Never falls back to a hardcoded demo repository.
    """

    if cli_repo is not None and cli_repo.strip():
        return cli_repo.strip()

    configured = configured_repository_source(settings)
    if configured:
        return configured

    raise AssessmentCommandError(
        "No repository configured.\n\n"
        "Fix one of the following:\n"
        "  1. Pass --repo /path/to/repository (local path or GitHub URL)\n"
        "  2. Set [repository].path in codestrata.toml for a local checkout\n"
        "  3. Set [repository].url in codestrata.toml for a GitHub repository\n\n"
        "Examples:\n"
        "  codestrata assess --repo /path/to/repository\n"
        "  codestrata assess --config codestrata.toml"
    )


def is_github_repository_source(repo: str) -> bool:
    """Return whether the repo argument is a GitHub URL."""

    return is_github_repository_source_settings(repo)


def _resolve_pmd_for_assessment(
    *,
    cli_path: str | None,
    settings: CodestrataSettings,
    verbose: bool,
    console: Console,
) -> str | None:
    if not settings.static_analysis.enabled or not settings.static_analysis.pmd.enabled:
        return None

    discovery = resolve_pmd_executable(
        cli_path=cli_path,
        configured=settings.static_analysis.pmd.executable,
    )
    if verbose:
        for line in discovery_diagnostic_lines(discovery):
            console.print(f"[dim]{line}[/dim]")
    if discovery.executable is None:
        return cli_path or settings.static_analysis.pmd.executable

    version = probe_pmd_version(discovery.executable)
    if verbose and version is not None:
        console.print(f"[dim]PMD version probe: {version}[/dim]")
    return discovery.executable


def _run_ai_assessment(
    *,
    analysis_result: AnalysisResult,
    settings: CodestrataSettings,
    resolved_model_id: str,
    temperature: float,
    max_output_tokens: int,
    context_limit: int,
    provider: AIModelProvider | None,
    prompt_builder: ModernizationPromptBuilder | None,
    agent: ModernizationAssessmentAgent | None,
    context_builder: LLMAnalysisContextBuilder | None,
    rule_evaluation: object,
    recommendation_result: object,
    repository_graph: object | None,
    stage: Callable[[str], None],
) -> tuple[
    LLMAnalysisContext,
    ModernizationAssessmentResult,
    AIAttemptInfo,
    AiEnrichmentResult,
]:
    from codestrata.ai.enrichment import (
        AiEnrichmentPromptBuilder,
        AiEnrichmentPromptOptions,
        AiEnrichmentService,
    )
    from codestrata.ai.enrichment.context import (
        AiEnrichmentBudgetError,
        AiEnrichmentContextLimits,
    )
    from codestrata.ai.enrichment.prompt import AiEnrichmentPromptBuildError
    from codestrata.ai.providers.exceptions import (
        AIProviderError,
        AIProviderTimeoutError,
        AIResponseParsingError,
        AIResponseValidationError,
    )
    from codestrata.ai.providers.models import ModelInvocationOptions
    from codestrata.domain.findings import RuleEvaluationResult
    from codestrata.domain.recommendations import RecommendationResult
    from codestrata.domain.repository_graph import RepositoryGraph

    _ = prompt_builder  # Phase 1 prompt builder unused; enrichment has its own prompt.
    _ = agent  # Legacy agent path replaced by single-call enrichment service.

    stage("Building Modernization Advisor context...")
    try:
        active_provider = provider or _create_assess_ai_provider(settings)
    except AIProviderError as error:
        raise _map_provider_error(error, model_id=resolved_model_id) from error

    if not isinstance(rule_evaluation, RuleEvaluationResult):
        raise AssessmentCommandError(
            "Modernization Advisor requires RuleEvaluationResult",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
        )
    if not isinstance(recommendation_result, RecommendationResult):
        raise AssessmentCommandError(
            "Modernization Advisor requires RecommendationResult",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
        )
    graph = repository_graph if isinstance(repository_graph, RepositoryGraph) else None

    stage("Running Modernization Advisor...")
    service = AiEnrichmentService(
        active_provider,
        prompt_builder=AiEnrichmentPromptBuilder(),
        context_builder=context_builder,
    )
    model_options = ModelInvocationOptions(
        model_id=resolved_model_id,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    prompt_options = AiEnrichmentPromptOptions(max_context_characters=context_limit)
    context_limits = AiEnrichmentContextLimits(max_context_characters=context_limit)

    try:
        run = service.run(
            analysis_result=analysis_result,
            rule_evaluation=rule_evaluation,
            recommendation_result=recommendation_result,
            repository_graph=graph,
            model_options=model_options,
            context_limits=context_limits,
            prompt_options=prompt_options,
        )
    except AiEnrichmentBudgetError as error:
        raise AssessmentCommandError(
            f"AI enrichment context budget failure: {sanitize_provider_text(str(error))}",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
            ai_attempt=AIAttemptInfo(
                model_id=resolved_model_id,
                stages_completed=stages_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_code=failure_code_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_detail=sanitize_provider_text(str(error)),
            ),
        ) from error
    except AiEnrichmentPromptBuildError as error:
        raise AssessmentCommandError(
            f"AI enrichment prompt failure: {sanitize_provider_text(str(error))}",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
            ai_attempt=AIAttemptInfo(
                model_id=resolved_model_id,
                stages_completed=stages_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_code=failure_code_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_detail=sanitize_provider_text(str(error)),
            ),
        ) from error
    except AIProviderTimeoutError as error:
        provider_label = (settings.ai.provider or "bedrock").strip().lower()
        raise AssessmentCommandError(
            f"AI provider timeout or throttling ({provider_label}): "
            f"{sanitize_provider_text(str(error))}",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
            ai_attempt=AIAttemptInfo(
                provider=provider_label,
                model_id=resolved_model_id,
                stages_completed=stages_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_code=failure_code_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_detail=sanitize_provider_text(str(error)),
            ),
        ) from error
    except (AIResponseValidationError, AIResponseParsingError) as error:
        raise _map_response_contract_error(error, model_id=resolved_model_id) from error
    except AIProviderError as error:
        raise _map_provider_error(error, model_id=resolved_model_id) from error
    except Exception as error:  # noqa: BLE001 - application boundary
        raise AssessmentCommandError(
            f"AI enrichment failed: {sanitize_provider_text(str(error))}",
            ai_status=AIExecutionStatus.PROVIDER_FAILED,
            customer_message=customer_failure_message(AIExecutionStatus.PROVIDER_FAILED),
            ai_attempt=AIAttemptInfo(
                model_id=resolved_model_id,
                stages_completed=stages_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_code=failure_code_for_status(AIExecutionStatus.PROVIDER_FAILED),
                failure_detail=sanitize_provider_text(str(error)),
            ),
        ) from error

    attempt = attempt_info_from_metadata(
        run.assessment_result.model_metadata,
        status=AIExecutionStatus.SUCCEEDED,
    )
    enrichment: AiEnrichmentResult = run.enrichment
    return run.analysis_context, run.assessment_result, attempt, enrichment


def _map_response_contract_error(
    error: Exception,
    *,
    model_id: str,
) -> AssessmentCommandError:
    from codestrata.ai.providers.exceptions import AIResponseValidationError

    status = (
        AIExecutionStatus.VALIDATION_FAILED
        if isinstance(error, AIResponseValidationError)
        else AIExecutionStatus.PARSING_FAILED
    )
    metadata = getattr(error, "metadata", None)
    raw_text = getattr(error, "raw_response_text", None)
    parsed_payload = getattr(error, "parsed_payload", None)
    validation_details = getattr(error, "validation_details", None) or str(error)
    detail = sanitize_provider_text(str(error))
    if metadata is not None:
        attempt = attempt_info_from_metadata(
            metadata,
            status=status,
            failure_detail=detail,
        )
    else:
        attempt = AIAttemptInfo(
            provider=None,
            model_id=model_id,
            stages_completed=stages_for_status(status),
            failure_code=failure_code_for_status(status),
            failure_detail=detail,
        )
    label = "Invalid model response"
    return AssessmentCommandError(
        f"{label}: {detail}",
        ai_status=status,
        customer_message=customer_failure_message(status),
        ai_attempt=attempt,
        execution_document=build_ai_execution_document(
            status=status,
            attempt=attempt,
            raw_model_text=raw_text if isinstance(raw_text, str) else None,
            parsed_model_response=parsed_payload if isinstance(parsed_payload, dict) else None,
            accepted_ai_result=None,
            failure_message=customer_failure_message(status),
            failure_detail=sanitize_provider_text(str(validation_details)),
        ),
    )


def _map_provider_error(
    error: Exception,
    *,
    model_id: str | None = None,
) -> AssessmentCommandError:
    message = sanitize_provider_text(str(error))
    lowered = message.lower()
    is_auth = (
        "unable to authenticate with aws" in lowered
        or "authentication" in lowered
        or "authenticate" in lowered
        or "expired token" in lowered
        or "sso" in lowered
        or "nocredentials" in lowered
    )
    if is_auth and "unable to authenticate with aws" not in lowered:
        from codestrata.ai.aws_config import format_aws_authentication_error

        message = format_aws_authentication_error()
        is_auth = True

    if is_auth:
        status = AIExecutionStatus.AUTHENTICATION_FAILED
        attempt = AIAttemptInfo(
            provider=None,
            model_id=model_id,
            stages_completed=stages_for_status(status),
            failure_code=failure_code_for_status(status),
            failure_detail=message,
        )
        return AssessmentCommandError(
            message,
            ai_status=status,
            customer_message=customer_failure_message(status),
            ai_attempt=attempt,
            execution_document=build_ai_execution_document(
                status=status,
                attempt=attempt,
                accepted_ai_result=None,
                failure_message=customer_failure_message(status),
                failure_detail=message,
            ),
        )

    status = AIExecutionStatus.PROVIDER_FAILED
    if "model access denied" in lowered or "invalid model or request configuration" in lowered:
        detail = message
    elif (
        "throttl" in lowered
        or "timed out" in lowered
        or "timeout" in lowered
        or "temporary service failure" in lowered
    ):
        detail = f"AI provider timeout or throttling: {message}"
    else:
        detail = f"Model provider failure: {message}"
    attempt = AIAttemptInfo(
        provider=None,
        model_id=model_id,
        stages_completed=stages_for_status(status),
        failure_code=failure_code_for_status(status),
        failure_detail=detail,
    )
    return AssessmentCommandError(
        detail,
        ai_status=status,
        customer_message=customer_failure_message(status),
        ai_attempt=attempt,
        execution_document=build_ai_execution_document(
            status=status,
            attempt=attempt,
            accepted_ai_result=None,
            failure_message=customer_failure_message(status),
            failure_detail=detail,
        ),
    )


def _count_rule_execution_statuses(
    facts: Sequence[Any],
) -> tuple[int, int, int, int, int]:
    """Count executed / matched / not_matched / not_applicable / failed facts."""

    executed = 0
    matched = 0
    not_matched = 0
    not_applicable = 0
    failed = 0
    for fact in facts:
        if bool(getattr(fact, "executed", False)):
            executed += 1
        status = str(getattr(fact, "evaluation_status", "") or "")
        if status == "matched":
            matched += 1
        elif status == "not_matched":
            not_matched += 1
        elif status == "not_applicable":
            not_applicable += 1
        elif status == "failed":
            failed += 1
    return executed, matched, not_matched, not_applicable, failed


def _static_analysis_warnings(analysis_result: AnalysisResult) -> list[str]:
    warnings: list[str] = []
    for result in analysis_result.static_analysis_results:
        if result.status == StaticAnalysisStatus.UNAVAILABLE:
            warnings.append(
                f"{result.provider_name} static analysis was unavailable. "
                "Remaining deterministic analyzers completed."
            )
        elif result.status == StaticAnalysisStatus.FAILED:
            detail = result.error_message or "provider failed"
            warnings.append(
                f"{result.provider_name} static analysis failed: "
                f"{sanitize_provider_text(detail)}. "
                "Remaining deterministic analyzers completed."
            )
    return warnings


def _print_static_analysis_success(
    console: Console,
    analysis_result: AnalysisResult,
) -> None:
    for result in analysis_result.static_analysis_results:
        if result.status != StaticAnalysisStatus.COMPLETED:
            continue
        version = result.provider_version or "unknown"
        profile = result.profile or "standard"
        raw = result.raw_observation_count
        grouped = result.grouped_finding_count
        console.print(
            f"Static analysis: {result.provider_name} {version} "
            f"(profile={profile}, raw={raw}, grouped={grouped})"
        )


def _static_analysis_duration_ms(analysis_result: AnalysisResult) -> float | None:
    durations = [
        item.duration_ms
        for item in analysis_result.static_analysis_results
        if item.duration_ms is not None
    ]
    if not durations:
        return None
    return round(sum(durations), 2)


def _build_command_result(
    *,
    repository_name: str,
    report_paths: ReportPaths,
    mode: AssessmentMode,
    analysis_result: AnalysisResult,
    assessment_result: ModernizationAssessmentResult | None,
    ai_status: AIExecutionStatus,
    ai_attempt: AIAttemptInfo | None,
    duration_ms: float | None,
    graph_artifacts: GraphArtifactWriteResult | None = None,
    rule_evaluation: object | None = None,
    findings_artifact: FindingsArtifactWriteResult | None = None,
    recommendation_result: object | None = None,
    recommendations_artifact: RecommendationsArtifactWriteResult | None = None,
    architecture_conclusion_count: int | None = None,
    architecture_conclusions_artifact: Path | None = None,
    architecture_assessment_status: str | None = None,
    architecture_assessment_finding_count: int | None = None,
    architecture_assessment_artifact: Path | None = None,
    technical_debt_assessment_status: str | None = None,
    technical_debt_assessment_finding_count: int | None = None,
    technical_debt_assessment_artifact: Path | None = None,
    dependency_assessment_status: str | None = None,
    dependency_assessment_finding_count: int | None = None,
    dependency_assessment_artifact: Path | None = None,
    dependency_evidence_status: str | None = None,
    dependency_evidence_declaration_count: int | None = None,
    dependency_evidence_artifact: Path | None = None,
    repository_sensitive_evidence_status: str | None = None,
    repository_sensitive_evidence_artifact_count: int | None = None,
    repository_sensitive_evidence_configuration_fact_count: int | None = None,
    repository_sensitive_evidence_artifact: Path | None = None,
    repository_testing_evidence_status: str | None = None,
    repository_testing_evidence_candidate_count: int | None = None,
    repository_testing_evidence_framework_count: int | None = None,
    repository_testing_evidence_artifact: Path | None = None,
    repository_cloud_evidence_status: str | None = None,
    repository_cloud_evidence_candidate_count: int | None = None,
    repository_cloud_evidence_technology_count: int | None = None,
    repository_cloud_evidence_artifact: Path | None = None,
    repository_ai_readiness_evidence_status: str | None = None,
    repository_ai_readiness_evidence_candidate_count: int | None = None,
    repository_ai_readiness_evidence_technology_count: int | None = None,
    repository_ai_readiness_evidence_artifact: Path | None = None,
    repository_performance_evidence_status: str | None = None,
    repository_performance_evidence_candidate_count: int | None = None,
    repository_performance_evidence_technology_count: int | None = None,
    repository_performance_evidence_artifact: Path | None = None,
    security_assessment_status: str | None = None,
    security_assessment_finding_count: int | None = None,
    security_assessment_artifact: Path | None = None,
    testing_assessment_status: str | None = None,
    testing_assessment_finding_count: int | None = None,
    testing_assessment_artifact: Path | None = None,
    cloud_assessment_status: str | None = None,
    cloud_assessment_finding_count: int | None = None,
    cloud_assessment_artifact: Path | None = None,
    ai_readiness_assessment_status: str | None = None,
    ai_readiness_assessment_finding_count: int | None = None,
    ai_readiness_assessment_artifact: Path | None = None,
    performance_assessment_status: str | None = None,
    performance_assessment_finding_count: int | None = None,
    performance_assessment_artifact: Path | None = None,
    architecture_report_enabled: bool | None = None,
    architecture_report_status: str | None = None,
    architecture_report_section_version: str | None = None,
    architecture_report_finding_count: int | None = None,
    architecture_report_conclusion_count: int | None = None,
    architecture_report_recommendation_group_count: int | None = None,
    architecture_report_adapter_ms: float | None = None,
    technical_debt_report_enabled: bool | None = None,
    technical_debt_report_status: str | None = None,
    technical_debt_report_section_version: str | None = None,
    technical_debt_report_finding_count: int | None = None,
    technical_debt_report_conclusion_count: int | None = None,
    technical_debt_report_hotspot_count: int | None = None,
    technical_debt_report_adapter_ms: float | None = None,
    dependency_report_enabled: bool | None = None,
    dependency_report_status: str | None = None,
    dependency_report_section_version: str | None = None,
    dependency_report_finding_count: int | None = None,
    dependency_report_conclusion_count: int | None = None,
    dependency_report_hotspot_count: int | None = None,
    dependency_report_adapter_ms: float | None = None,
    security_report_enabled: bool | None = None,
    security_report_status: str | None = None,
    security_report_section_version: str | None = None,
    security_report_finding_count: int | None = None,
    security_report_conclusion_count: int | None = None,
    security_report_hotspot_count: int | None = None,
    security_report_adapter_ms: float | None = None,
    testing_report_enabled: bool | None = None,
    testing_report_status: str | None = None,
    testing_report_section_version: str | None = None,
    testing_report_finding_count: int | None = None,
    testing_report_conclusion_count: int | None = None,
    testing_report_adapter_ms: float | None = None,
    cloud_report_enabled: bool | None = None,
    cloud_report_status: str | None = None,
    cloud_report_section_version: str | None = None,
    cloud_report_finding_count: int | None = None,
    cloud_report_conclusion_count: int | None = None,
    cloud_report_adapter_ms: float | None = None,
    ai_readiness_report_enabled: bool | None = None,
    ai_readiness_report_status: str | None = None,
    ai_readiness_report_section_version: str | None = None,
    ai_readiness_report_finding_count: int | None = None,
    ai_readiness_report_conclusion_count: int | None = None,
    ai_readiness_report_adapter_ms: float | None = None,
    performance_report_enabled: bool | None = None,
    performance_report_status: str | None = None,
    performance_report_section_version: str | None = None,
    performance_report_finding_count: int | None = None,
    performance_report_conclusion_count: int | None = None,
    performance_report_adapter_ms: float | None = None,
    roadmap_report_enabled: bool | None = None,
    roadmap_report_status: str | None = None,
    roadmap_report_section_version: str | None = None,
    roadmap_report_initiative_count: int | None = None,
    roadmap_report_phase_count: int | None = None,
    roadmap_report_adapter_ms: float | None = None,
) -> AssessmentCommandResult:
    from codestrata.domain.findings import RuleEvaluationResult
    from codestrata.domain.recommendations import RecommendationResult
    from codestrata.reporting.contract.identifiers import build_finding_id_map
    from codestrata.reporting.customer_universe import (
        merge_customer_findings,
        merge_customer_recommendations,
    )

    evaluation = rule_evaluation if isinstance(rule_evaluation, RuleEvaluationResult) else None
    phase3_recommendations = (
        recommendation_result if isinstance(recommendation_result, RecommendationResult) else None
    )
    customer_findings = merge_customer_findings(
        analysis_result.findings,
        evaluation=evaluation,
    )
    customer_recommendations = merge_customer_recommendations(
        analysis_result.recommendations,
        result=phase3_recommendations,
        finding_id_map=build_finding_id_map(list(analysis_result.findings)),
    )
    findings_count = len(customer_findings)
    deterministic_recommendation_count = len(customer_recommendations)
    graph_fields: dict[str, object] = {}
    if graph_artifacts is not None:
        summary = graph_artifacts.summary
        graph_fields = {
            "graphs_directory": graph_artifacts.directory,
            "knowledge_binding_count": summary.binding_count,
            "repository_graph_node_count": summary.repository_node_count,
            "repository_graph_relationship_count": summary.repository_relationship_count,
            "assessment_graph_node_count": summary.assessment_node_count,
            "assessment_graph_relationship_count": summary.assessment_relationship_count,
        }
    if rule_evaluation is not None:
        graph_fields["rule_finding_count"] = getattr(rule_evaluation, "finding_count", 0)
        graph_fields["rules_evaluated_count"] = len(getattr(rule_evaluation, "rules_evaluated", ()))
    if findings_artifact is not None:
        graph_fields["findings_artifact_path"] = findings_artifact.path
    if recommendation_result is not None:
        graph_fields["phase3_recommendation_count"] = getattr(
            recommendation_result,
            "recommendation_count",
            0,
        )
    if recommendations_artifact is not None:
        graph_fields["recommendations_artifact_path"] = recommendations_artifact.path
    if architecture_conclusion_count is not None:
        graph_fields["architecture_conclusion_count"] = architecture_conclusion_count
    if architecture_conclusions_artifact is not None:
        graph_fields["architecture_conclusions_artifact_path"] = architecture_conclusions_artifact
    if architecture_assessment_status is not None:
        graph_fields["architecture_assessment_status"] = architecture_assessment_status
    if architecture_assessment_finding_count is not None:
        graph_fields["architecture_assessment_finding_count"] = (
            architecture_assessment_finding_count
        )
    if architecture_assessment_artifact is not None:
        graph_fields["architecture_assessment_artifact_path"] = architecture_assessment_artifact
    if technical_debt_assessment_status is not None:
        graph_fields["technical_debt_assessment_status"] = technical_debt_assessment_status
    if technical_debt_assessment_finding_count is not None:
        graph_fields["technical_debt_assessment_finding_count"] = (
            technical_debt_assessment_finding_count
        )
    if technical_debt_assessment_artifact is not None:
        graph_fields["technical_debt_assessment_artifact_path"] = technical_debt_assessment_artifact
    if dependency_assessment_status is not None:
        graph_fields["dependency_assessment_status"] = dependency_assessment_status
    if dependency_assessment_finding_count is not None:
        graph_fields["dependency_assessment_finding_count"] = dependency_assessment_finding_count
    if dependency_assessment_artifact is not None:
        graph_fields["dependency_assessment_artifact_path"] = dependency_assessment_artifact
    if dependency_evidence_status is not None:
        graph_fields["dependency_evidence_status"] = dependency_evidence_status
    if dependency_evidence_declaration_count is not None:
        graph_fields["dependency_evidence_declaration_count"] = (
            dependency_evidence_declaration_count
        )
    if dependency_evidence_artifact is not None:
        graph_fields["dependency_evidence_artifact_path"] = dependency_evidence_artifact
    if repository_sensitive_evidence_status is not None:
        graph_fields["repository_sensitive_evidence_status"] = repository_sensitive_evidence_status
    if repository_sensitive_evidence_artifact_count is not None:
        graph_fields["repository_sensitive_evidence_artifact_count"] = (
            repository_sensitive_evidence_artifact_count
        )
    if repository_sensitive_evidence_configuration_fact_count is not None:
        graph_fields["repository_sensitive_evidence_configuration_fact_count"] = (
            repository_sensitive_evidence_configuration_fact_count
        )
    if repository_sensitive_evidence_artifact is not None:
        graph_fields["repository_sensitive_evidence_artifact_path"] = (
            repository_sensitive_evidence_artifact
        )
    if repository_testing_evidence_status is not None:
        graph_fields["repository_testing_evidence_status"] = repository_testing_evidence_status
    if repository_testing_evidence_candidate_count is not None:
        graph_fields["repository_testing_evidence_candidate_count"] = (
            repository_testing_evidence_candidate_count
        )
    if repository_testing_evidence_framework_count is not None:
        graph_fields["repository_testing_evidence_framework_count"] = (
            repository_testing_evidence_framework_count
        )
    if repository_testing_evidence_artifact is not None:
        graph_fields["repository_testing_evidence_artifact_path"] = (
            repository_testing_evidence_artifact
        )
    if repository_cloud_evidence_status is not None:
        graph_fields["repository_cloud_evidence_status"] = repository_cloud_evidence_status
    if repository_cloud_evidence_candidate_count is not None:
        graph_fields["repository_cloud_evidence_candidate_count"] = (
            repository_cloud_evidence_candidate_count
        )
    if repository_cloud_evidence_technology_count is not None:
        graph_fields["repository_cloud_evidence_technology_count"] = (
            repository_cloud_evidence_technology_count
        )
    if repository_cloud_evidence_artifact is not None:
        graph_fields["repository_cloud_evidence_artifact_path"] = repository_cloud_evidence_artifact
    if repository_ai_readiness_evidence_status is not None:
        graph_fields["repository_ai_readiness_evidence_status"] = (
            repository_ai_readiness_evidence_status
        )
    if repository_ai_readiness_evidence_candidate_count is not None:
        graph_fields["repository_ai_readiness_evidence_candidate_count"] = (
            repository_ai_readiness_evidence_candidate_count
        )
    if repository_ai_readiness_evidence_technology_count is not None:
        graph_fields["repository_ai_readiness_evidence_technology_count"] = (
            repository_ai_readiness_evidence_technology_count
        )
    if repository_ai_readiness_evidence_artifact is not None:
        graph_fields["repository_ai_readiness_evidence_artifact_path"] = (
            repository_ai_readiness_evidence_artifact
        )
    if repository_performance_evidence_status is not None:
        graph_fields["repository_performance_evidence_status"] = (
            repository_performance_evidence_status
        )
    if repository_performance_evidence_candidate_count is not None:
        graph_fields["repository_performance_evidence_candidate_count"] = (
            repository_performance_evidence_candidate_count
        )
    if repository_performance_evidence_technology_count is not None:
        graph_fields["repository_performance_evidence_technology_count"] = (
            repository_performance_evidence_technology_count
        )
    if repository_performance_evidence_artifact is not None:
        graph_fields["repository_performance_evidence_artifact_path"] = (
            repository_performance_evidence_artifact
        )
    if security_assessment_status is not None:
        graph_fields["security_assessment_status"] = security_assessment_status
    if security_assessment_finding_count is not None:
        graph_fields["security_assessment_finding_count"] = security_assessment_finding_count
    if security_assessment_artifact is not None:
        graph_fields["security_assessment_artifact_path"] = security_assessment_artifact
    if testing_assessment_status is not None:
        graph_fields["testing_assessment_status"] = testing_assessment_status
    if testing_assessment_finding_count is not None:
        graph_fields["testing_assessment_finding_count"] = testing_assessment_finding_count
    if testing_assessment_artifact is not None:
        graph_fields["testing_assessment_artifact_path"] = testing_assessment_artifact
    if cloud_assessment_status is not None:
        graph_fields["cloud_assessment_status"] = cloud_assessment_status
    if cloud_assessment_finding_count is not None:
        graph_fields["cloud_assessment_finding_count"] = cloud_assessment_finding_count
    if cloud_assessment_artifact is not None:
        graph_fields["cloud_assessment_artifact_path"] = cloud_assessment_artifact
    if ai_readiness_assessment_status is not None:
        graph_fields["ai_readiness_assessment_status"] = ai_readiness_assessment_status
    if ai_readiness_assessment_finding_count is not None:
        graph_fields["ai_readiness_assessment_finding_count"] = (
            ai_readiness_assessment_finding_count
        )
    if ai_readiness_assessment_artifact is not None:
        graph_fields["ai_readiness_assessment_artifact_path"] = ai_readiness_assessment_artifact
    if performance_assessment_status is not None:
        graph_fields["performance_assessment_status"] = performance_assessment_status
    if performance_assessment_finding_count is not None:
        graph_fields["performance_assessment_finding_count"] = performance_assessment_finding_count
    if performance_assessment_artifact is not None:
        graph_fields["performance_assessment_artifact_path"] = performance_assessment_artifact
    if architecture_report_enabled is not None:
        graph_fields["architecture_report_enabled"] = architecture_report_enabled
    if architecture_report_status is not None:
        graph_fields["architecture_report_status"] = architecture_report_status
    if architecture_report_section_version is not None:
        graph_fields["architecture_report_section_version"] = architecture_report_section_version
    if architecture_report_finding_count is not None:
        graph_fields["architecture_report_finding_count"] = architecture_report_finding_count
    if architecture_report_conclusion_count is not None:
        graph_fields["architecture_report_conclusion_count"] = architecture_report_conclusion_count
    if architecture_report_recommendation_group_count is not None:
        graph_fields["architecture_report_recommendation_group_count"] = (
            architecture_report_recommendation_group_count
        )
    if architecture_report_adapter_ms is not None:
        graph_fields["architecture_report_adapter_ms"] = architecture_report_adapter_ms
    if technical_debt_report_enabled is not None:
        graph_fields["technical_debt_report_enabled"] = technical_debt_report_enabled
    if technical_debt_report_status is not None:
        graph_fields["technical_debt_report_status"] = technical_debt_report_status
    if technical_debt_report_section_version is not None:
        graph_fields["technical_debt_report_section_version"] = (
            technical_debt_report_section_version
        )
    if technical_debt_report_finding_count is not None:
        graph_fields["technical_debt_report_finding_count"] = technical_debt_report_finding_count
    if technical_debt_report_conclusion_count is not None:
        graph_fields["technical_debt_report_conclusion_count"] = (
            technical_debt_report_conclusion_count
        )
    if technical_debt_report_hotspot_count is not None:
        graph_fields["technical_debt_report_hotspot_count"] = technical_debt_report_hotspot_count
    if technical_debt_report_adapter_ms is not None:
        graph_fields["technical_debt_report_adapter_ms"] = technical_debt_report_adapter_ms
    if dependency_report_enabled is not None:
        graph_fields["dependency_report_enabled"] = dependency_report_enabled
    if dependency_report_status is not None:
        graph_fields["dependency_report_status"] = dependency_report_status
    if dependency_report_section_version is not None:
        graph_fields["dependency_report_section_version"] = dependency_report_section_version
    if dependency_report_finding_count is not None:
        graph_fields["dependency_report_finding_count"] = dependency_report_finding_count
    if dependency_report_conclusion_count is not None:
        graph_fields["dependency_report_conclusion_count"] = dependency_report_conclusion_count
    if dependency_report_hotspot_count is not None:
        graph_fields["dependency_report_hotspot_count"] = dependency_report_hotspot_count
    if dependency_report_adapter_ms is not None:
        graph_fields["dependency_report_adapter_ms"] = dependency_report_adapter_ms
    if security_report_enabled is not None:
        graph_fields["security_report_enabled"] = security_report_enabled
    if security_report_status is not None:
        graph_fields["security_report_status"] = security_report_status
    if security_report_section_version is not None:
        graph_fields["security_report_section_version"] = security_report_section_version
    if security_report_finding_count is not None:
        graph_fields["security_report_finding_count"] = security_report_finding_count
    if security_report_conclusion_count is not None:
        graph_fields["security_report_conclusion_count"] = security_report_conclusion_count
    if security_report_hotspot_count is not None:
        graph_fields["security_report_hotspot_count"] = security_report_hotspot_count
    if security_report_adapter_ms is not None:
        graph_fields["security_report_adapter_ms"] = security_report_adapter_ms
    if testing_report_enabled is not None:
        graph_fields["testing_report_enabled"] = testing_report_enabled
    if testing_report_status is not None:
        graph_fields["testing_report_status"] = testing_report_status
    if testing_report_section_version is not None:
        graph_fields["testing_report_section_version"] = testing_report_section_version
    if testing_report_finding_count is not None:
        graph_fields["testing_report_finding_count"] = testing_report_finding_count
    if testing_report_conclusion_count is not None:
        graph_fields["testing_report_conclusion_count"] = testing_report_conclusion_count
    if testing_report_adapter_ms is not None:
        graph_fields["testing_report_adapter_ms"] = testing_report_adapter_ms
    if cloud_report_enabled is not None:
        graph_fields["cloud_report_enabled"] = cloud_report_enabled
    if cloud_report_status is not None:
        graph_fields["cloud_report_status"] = cloud_report_status
    if cloud_report_section_version is not None:
        graph_fields["cloud_report_section_version"] = cloud_report_section_version
    if cloud_report_finding_count is not None:
        graph_fields["cloud_report_finding_count"] = cloud_report_finding_count
    if cloud_report_conclusion_count is not None:
        graph_fields["cloud_report_conclusion_count"] = cloud_report_conclusion_count
    if cloud_report_adapter_ms is not None:
        graph_fields["cloud_report_adapter_ms"] = cloud_report_adapter_ms
    if ai_readiness_report_enabled is not None:
        graph_fields["ai_readiness_report_enabled"] = ai_readiness_report_enabled
    if ai_readiness_report_status is not None:
        graph_fields["ai_readiness_report_status"] = ai_readiness_report_status
    if ai_readiness_report_section_version is not None:
        graph_fields["ai_readiness_report_section_version"] = ai_readiness_report_section_version
    if ai_readiness_report_finding_count is not None:
        graph_fields["ai_readiness_report_finding_count"] = ai_readiness_report_finding_count
    if ai_readiness_report_conclusion_count is not None:
        graph_fields["ai_readiness_report_conclusion_count"] = ai_readiness_report_conclusion_count
    if ai_readiness_report_adapter_ms is not None:
        graph_fields["ai_readiness_report_adapter_ms"] = ai_readiness_report_adapter_ms
    if performance_report_enabled is not None:
        graph_fields["performance_report_enabled"] = performance_report_enabled
    if performance_report_status is not None:
        graph_fields["performance_report_status"] = performance_report_status
    if performance_report_section_version is not None:
        graph_fields["performance_report_section_version"] = performance_report_section_version
    if performance_report_finding_count is not None:
        graph_fields["performance_report_finding_count"] = performance_report_finding_count
    if performance_report_conclusion_count is not None:
        graph_fields["performance_report_conclusion_count"] = performance_report_conclusion_count
    if performance_report_adapter_ms is not None:
        graph_fields["performance_report_adapter_ms"] = performance_report_adapter_ms
    if roadmap_report_enabled is not None:
        graph_fields["roadmap_report_enabled"] = roadmap_report_enabled
    if roadmap_report_status is not None:
        graph_fields["roadmap_report_status"] = roadmap_report_status
    if roadmap_report_section_version is not None:
        graph_fields["roadmap_report_section_version"] = roadmap_report_section_version
    if roadmap_report_initiative_count is not None:
        graph_fields["roadmap_report_initiative_count"] = roadmap_report_initiative_count
    if roadmap_report_phase_count is not None:
        graph_fields["roadmap_report_phase_count"] = roadmap_report_phase_count
    if roadmap_report_adapter_ms is not None:
        graph_fields["roadmap_report_adapter_ms"] = roadmap_report_adapter_ms
    if (
        mode == AssessmentMode.AI_ENHANCED
        and ai_status == AIExecutionStatus.SUCCEEDED
        and assessment_result is not None
    ):
        recommendation = assessment_result.recommendation_result
        metadata = assessment_result.model_metadata
        return AssessmentCommandResult(
            repository_name=repository_name,
            run_directory=report_paths.run_directory,
            html_report_path=report_paths.html_report_path,
            json_report_path=report_paths.json_report_path,
            report_path=report_paths.html_report_path,
            mode=mode,
            findings_count=findings_count,
            technologies_count=len(analysis_result.technologies),
            recommendations_count=deterministic_recommendation_count,
            phases_count=len(recommendation.modernization_phases),
            ai_executed=True,
            input_tokens=metadata.usage.input_tokens,
            output_tokens=metadata.usage.output_tokens,
            model_id=metadata.model_id,
            latency_ms=metadata.latency_ms,
            duration_ms=duration_ms,
            **graph_fields,  # type: ignore[arg-type]
        )

    return AssessmentCommandResult(
        repository_name=repository_name,
        run_directory=report_paths.run_directory,
        html_report_path=report_paths.html_report_path,
        json_report_path=report_paths.json_report_path,
        report_path=report_paths.html_report_path,
        mode=mode,
        findings_count=findings_count,
        technologies_count=len(analysis_result.technologies),
        recommendations_count=deterministic_recommendation_count,
        phases_count=0,
        ai_executed=False,
        input_tokens=ai_attempt.input_tokens if ai_attempt is not None else None,
        output_tokens=ai_attempt.output_tokens if ai_attempt is not None else None,
        model_id=ai_attempt.model_id if ai_attempt is not None else None,
        latency_ms=ai_attempt.latency_ms if ai_attempt is not None else None,
        duration_ms=duration_ms,
        **graph_fields,  # type: ignore[arg-type]
    )


def _write_scan_boundary_diagnostics(
    repository: Repository,
    run_directory: Path,
) -> None:
    """Persist bounded scan-boundary diagnostics for Technical Appendix consumers."""

    import json

    payload = repository.metadata.get("scan_boundary")
    if not isinstance(payload, dict):
        return
    target = run_directory / "scan-boundary-diagnostics.json"
    try:
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        logger.debug("Unable to write scan-boundary diagnostics", exc_info=True)


def _scan_repository(
    repo: str,
    *,
    settings: CodestrataSettings,
    branch: str | None,
    scanner: _RepositoryScanner | None,
) -> Repository:
    compact = repo.strip()
    if not compact:
        raise AssessmentCommandError(
            "Invalid repository path or URL: repository is empty.\n\n"
            "Fix: pass --repo /path/to/repo or configure [repository] in codestrata.toml."
        )

    if scanner is not None:
        return scanner.scan(compact)

    if is_github_repository_source(compact):
        github_scanner = GitHubRepositoryScanner(
            workspace_directory=settings.workspace.directory,
            branch=branch,
            clean_before_clone=settings.workspace.clean_before_clone,
            authentication=settings.repository.authentication,
            ephemeral=True,
        )
        return github_scanner.scan(compact)

    path = Path(compact)
    if not path.exists():
        raise AssessmentCommandError(
            f"Repository path does not exist: {path}\n\n"
            "Fix: create or clone the repository, update [repository].path in "
            "codestrata.toml, or pass a valid --repo path."
        )
    if not path.is_dir():
        raise AssessmentCommandError(
            f"Repository path is not a directory: {path}\n\n"
            "Fix: point --repo or [repository].path at the repository root."
        )
    scanner_impl = LocalRepositoryScanner(
        max_files=settings.analysis.runtime.max_source_files,
        boundary_policy=BoundaryPolicy.from_settings(settings),
    )
    repository = scanner_impl.scan(path)
    repository.metadata["scan_boundary"] = scanner_impl.last_diagnostics.to_dict()
    return repository


def _create_assess_ai_provider(settings: CodestrataSettings) -> AIModelProvider:
    from codestrata.ai.providers.factory import create_assess_ai_provider

    return create_assess_ai_provider(settings)


def _create_bedrock_provider(settings: CodestrataSettings) -> AIModelProvider:
    """Backward-compatible alias for Bedrock-only callers."""

    return _create_assess_ai_provider(settings)


def _safe_repository_reference(repo: str) -> str:
    compact = repo.strip()
    if not compact:
        return "repository"
    if is_github_repository_source(compact):
        return compact
    path = Path(compact)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except (OSError, ValueError):
        if path.is_absolute():
            return path.name
        return str(path)


def _cleanup_ephemeral_github_clone(
    repository: Repository,
    *,
    warn: Callable[[str], None] | None = None,
) -> None:
    """Remove ephemeral GitHub clones after assess; never delete local checkouts."""

    if not repository.ephemeral:
        return
    try:
        removed = dispose_ephemeral_repository(repository)
    except OSError as error:
        message = f"Failed to clean up ephemeral GitHub clone at {repository.path}: {error}"
        logger.warning(message)
        if warn is not None:
            warn(message)
        return
    if removed:
        logger.info("Ephemeral GitHub clone removed: %s", repository.path)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except (OSError, ValueError):
        return str(path)


def _ai_status_for_summary(result: AssessmentCommandResult) -> str:
    if result.mode == AssessmentMode.DETERMINISTIC:
        return "not_requested"
    if result.ai_executed:
        return "succeeded"
    return "fallback"


def _assessment_json_summary(result: AssessmentCommandResult) -> dict[str, object]:
    return {
        "repository": result.repository_name,
        "mode": result.mode.value,
        "duration_ms": result.duration_ms,
        "findings": result.findings_count,
        "recommendations": result.recommendations_count,
        "technologies": result.technologies_count,
        "ai_status": _ai_status_for_summary(result),
        "ai_executed": result.ai_executed,
        "model_id": result.model_id,
        "html_report": _display_path(result.html_report_path),
        "json_report": _display_path(result.json_report_path),
        "run_directory": _display_path(result.run_directory),
    }


def _print_success_summary(
    console: Console,
    result: AssessmentCommandResult,
    *,
    quiet: bool = False,
    json_summary: bool = False,
) -> None:
    if json_summary:
        import json

        # Machine summary on stdout for CI piping.
        print(json.dumps(_assessment_json_summary(result), sort_keys=True), flush=True)
        if quiet:
            return

    ai_status = _ai_status_for_summary(result)
    if result.mode == AssessmentMode.AI_ENHANCED and result.ai_executed:
        mode_label = "AI Enhanced"
    elif result.mode == AssessmentMode.AI_ENHANCED:
        mode_label = "AI requested, deterministic fallback"
    else:
        mode_label = "Deterministic"

    console.print()
    console.print("[green]Report generated successfully.[/green]")
    console.print(f"Repository: {result.repository_name}")
    console.print(f"Languages: {result.technologies_count}")
    console.print(f"Findings: {result.findings_count}")
    if result.duration_ms is not None:
        console.print(f"Duration: {result.duration_ms / 1000:.1f}s")
    if result.mode == AssessmentMode.AI_ENHANCED and not result.ai_executed:
        console.print(
            "[yellow]Warning:[/yellow] AI enhancements skipped "
            "(deterministic Engineering Assessment report was still generated)."
        )
        console.print(f"AI status: {ai_status}")
        if result.model_id:
            console.print(f"AI provider model: {result.model_id}")
    elif result.mode == AssessmentMode.DETERMINISTIC:
        console.print("AI status: not requested (deterministic mode)")
    else:
        console.print(f"AI status: {ai_status}")
    console.print()
    console.print("HTML Report:")
    console.print(f"  {_display_path(result.html_report_path)}")
    console.print("JSON Report:")
    console.print(f"  {_display_path(result.json_report_path)}")
    console.print(f"Report location: {_display_path(result.run_directory)}")
    if quiet:
        console.print("Open report: codestrata open")
        return

    console.print(f"Assessment mode: {mode_label}")
    console.print(f"Engineering Intelligence: {result.recommendations_count} recommendations")
    if result.graphs_directory is not None:
        console.print(f"Graph artifacts: {_display_path(result.graphs_directory)}")
        if result.knowledge_binding_count is not None:
            console.print(f"Knowledge bindings: {result.knowledge_binding_count}")
    if result.rule_finding_count is not None:
        console.print(f"Rule findings: {result.rule_finding_count}")
    if result.findings_artifact_path is not None:
        console.print(f"Findings artifact: {_display_path(result.findings_artifact_path)}")
    if result.phase3_recommendation_count is not None:
        console.print(f"Graph recommendations: {result.phase3_recommendation_count}")
    if result.recommendations_artifact_path is not None:
        console.print(
            f"Recommendations artifact: {_display_path(result.recommendations_artifact_path)}"
        )
    if result.architecture_assessment_status is not None:
        console.print(f"Architecture assessment: {result.architecture_assessment_status}")
    if result.architecture_assessment_finding_count is not None:
        console.print(
            f"Architecture assessment findings: {result.architecture_assessment_finding_count}"
        )
    if result.architecture_assessment_artifact_path is not None:
        console.print(
            "Architecture assessment artifact: "
            f"{_display_path(result.architecture_assessment_artifact_path)}"
        )
    if result.technical_debt_assessment_status is not None:
        console.print(f"Technical debt assessment: {result.technical_debt_assessment_status}")
    if result.technical_debt_assessment_finding_count is not None:
        console.print(
            "Technical debt primary (production) findings: "
            f"{result.technical_debt_assessment_finding_count}"
        )
    if result.technical_debt_assessment_artifact_path is not None:
        console.print(
            "Technical debt assessment artifact: "
            f"{_display_path(result.technical_debt_assessment_artifact_path)}"
        )
    if result.dependency_assessment_status is not None:
        console.print(f"Dependency assessment: {result.dependency_assessment_status}")
    if result.dependency_assessment_finding_count is not None:
        console.print(
            f"Dependency assessment findings: {result.dependency_assessment_finding_count}"
        )
    if result.dependency_assessment_artifact_path is not None:
        console.print(
            "Dependency assessment artifact: "
            f"{_display_path(result.dependency_assessment_artifact_path)}"
        )
    if result.dependency_evidence_status is not None:
        console.print(f"Dependency evidence: {result.dependency_evidence_status}")
    if result.dependency_evidence_declaration_count is not None:
        console.print(
            f"Dependency evidence declarations: {result.dependency_evidence_declaration_count}"
        )
    if result.dependency_evidence_artifact_path is not None:
        console.print(
            "Dependency evidence artifact: "
            f"{_display_path(result.dependency_evidence_artifact_path)}"
        )
    if result.repository_sensitive_evidence_status is not None:
        console.print(
            f"Repository-sensitive evidence: {result.repository_sensitive_evidence_status}"
        )
    if result.repository_sensitive_evidence_artifact_count is not None:
        console.print(
            f"Repository-sensitive artifacts: {result.repository_sensitive_evidence_artifact_count}"
        )
    if result.repository_sensitive_evidence_configuration_fact_count is not None:
        console.print(
            "Repository-sensitive configuration facts: "
            f"{result.repository_sensitive_evidence_configuration_fact_count}"
        )
    if result.repository_sensitive_evidence_artifact_path is not None:
        console.print(
            "Repository-sensitive evidence artifact: "
            f"{_display_path(result.repository_sensitive_evidence_artifact_path)}"
        )
    if result.repository_testing_evidence_status is not None:
        console.print(f"Repository-testing evidence: {result.repository_testing_evidence_status}")
    if result.repository_testing_evidence_candidate_count is not None:
        console.print(
            f"Repository-testing candidates: {result.repository_testing_evidence_candidate_count}"
        )
    if result.repository_testing_evidence_framework_count is not None:
        console.print(
            f"Repository-testing frameworks: {result.repository_testing_evidence_framework_count}"
        )
    if result.repository_testing_evidence_artifact_path is not None:
        console.print(
            "Repository-testing evidence artifact: "
            f"{_display_path(result.repository_testing_evidence_artifact_path)}"
        )
    if result.repository_cloud_evidence_status is not None:
        console.print(f"Repository-cloud evidence: {result.repository_cloud_evidence_status}")
    if result.repository_cloud_evidence_candidate_count is not None:
        console.print(
            "Repository-cloud evidence candidates: "
            f"{result.repository_cloud_evidence_candidate_count}"
        )
    if result.repository_cloud_evidence_technology_count is not None:
        console.print(
            "Repository-cloud evidence technologies: "
            f"{result.repository_cloud_evidence_technology_count}"
        )
    if result.repository_cloud_evidence_artifact_path is not None:
        console.print(
            "Repository-cloud evidence artifact: "
            f"{_display_path(result.repository_cloud_evidence_artifact_path)}"
        )
    if result.repository_ai_readiness_evidence_status is not None:
        console.print(
            f"Repository AI-readiness evidence: {result.repository_ai_readiness_evidence_status}"
        )
    if result.repository_ai_readiness_evidence_candidate_count is not None:
        console.print(
            "Repository AI-readiness evidence candidates: "
            f"{result.repository_ai_readiness_evidence_candidate_count}"
        )
    if result.repository_ai_readiness_evidence_technology_count is not None:
        console.print(
            "Repository AI-readiness evidence technologies: "
            f"{result.repository_ai_readiness_evidence_technology_count}"
        )
    if result.repository_ai_readiness_evidence_artifact_path is not None:
        console.print(
            "Repository AI-readiness evidence artifact: "
            f"{_display_path(result.repository_ai_readiness_evidence_artifact_path)}"
        )
    if result.repository_performance_evidence_status is not None:
        console.print(
            f"Repository performance evidence: {result.repository_performance_evidence_status}"
        )
    if result.repository_performance_evidence_candidate_count is not None:
        console.print(
            "Repository performance evidence candidates: "
            f"{result.repository_performance_evidence_candidate_count}"
        )
    if result.repository_performance_evidence_technology_count is not None:
        console.print(
            "Repository performance evidence technologies: "
            f"{result.repository_performance_evidence_technology_count}"
        )
    if result.repository_performance_evidence_artifact_path is not None:
        console.print(
            "Repository performance evidence artifact: "
            f"{_display_path(result.repository_performance_evidence_artifact_path)}"
        )
    if result.security_assessment_status is not None:
        console.print(f"Security assessment: {result.security_assessment_status}")
    if result.security_assessment_finding_count is not None:
        console.print(f"Security assessment findings: {result.security_assessment_finding_count}")
    if result.security_assessment_artifact_path is not None:
        console.print(
            "Security assessment artifact: "
            f"{_display_path(result.security_assessment_artifact_path)}"
        )
    if result.testing_assessment_status is not None:
        console.print(f"Test assessment: {result.testing_assessment_status}")
    if result.testing_assessment_finding_count is not None:
        console.print(f"Test assessment findings: {result.testing_assessment_finding_count}")
    if result.testing_assessment_artifact_path is not None:
        console.print(
            f"Test assessment artifact: {_display_path(result.testing_assessment_artifact_path)}"
        )
    if result.cloud_assessment_status is not None:
        console.print(f"Cloud assessment: {result.cloud_assessment_status}")
    if result.cloud_assessment_finding_count is not None:
        console.print(f"Cloud assessment findings: {result.cloud_assessment_finding_count}")
    if result.cloud_assessment_artifact_path is not None:
        console.print(
            f"Cloud assessment artifact: {_display_path(result.cloud_assessment_artifact_path)}"
        )
    if result.ai_readiness_assessment_status is not None:
        console.print(f"AI Readiness assessment: {result.ai_readiness_assessment_status}")
    if result.ai_readiness_assessment_finding_count is not None:
        console.print(
            f"AI Readiness assessment findings: {result.ai_readiness_assessment_finding_count}"
        )
    if result.ai_readiness_assessment_artifact_path is not None:
        console.print(
            "AI Readiness assessment artifact: "
            f"{_display_path(result.ai_readiness_assessment_artifact_path)}"
        )
    if result.performance_assessment_status is not None:
        console.print(f"Performance assessment: {result.performance_assessment_status}")
    if result.performance_assessment_finding_count is not None:
        console.print(
            f"Performance assessment findings: {result.performance_assessment_finding_count}"
        )
    if result.performance_assessment_artifact_path is not None:
        console.print(
            "Performance assessment artifact: "
            f"{_display_path(result.performance_assessment_artifact_path)}"
        )
    if result.architecture_report_enabled:
        console.print(
            f"Architecture report section: {result.architecture_report_status or 'unavailable'}"
        )
    if result.technical_debt_report_enabled:
        console.print(
            f"Technical debt report section: {result.technical_debt_report_status or 'unavailable'}"
        )
    if result.dependency_report_enabled:
        console.print(
            f"Dependency report section: {result.dependency_report_status or 'unavailable'}"
        )
    if result.security_report_enabled:
        console.print(f"Security report section: {result.security_report_status or 'unavailable'}")
    if result.testing_report_enabled:
        console.print(f"Test report section: {result.testing_report_status or 'unavailable'}")
    if result.architecture_conclusion_count is not None:
        console.print(f"Architecture conclusions: {result.architecture_conclusion_count}")
    if result.architecture_conclusions_artifact_path is not None:
        console.print(
            "Architecture conclusions artifact: "
            f"{_display_path(result.architecture_conclusions_artifact_path)}"
        )
    if result.mode == AssessmentMode.AI_ENHANCED and not result.ai_executed:
        console.print(
            "AI enhancements: skipped "
            "(optional AI advisor did not produce a validated result; "
            "deterministic report is complete)."
        )
        if result.model_id:
            console.print(f"Configured model: {result.model_id}")
        if result.input_tokens is not None:
            console.print(f"Input tokens: {result.input_tokens}")
        if result.output_tokens is not None:
            console.print(f"Output tokens: {result.output_tokens}")
    if result.ai_executed:
        console.print("AI enhancements: included")
        console.print(f"Modernization phases: {result.phases_count}")
        console.print(
            f"Input tokens: {result.input_tokens if result.input_tokens is not None else '—'}"
        )
        console.print(
            f"Output tokens: {result.output_tokens if result.output_tokens is not None else '—'}"
        )
        console.print(f"Model ID: {result.model_id or '—'}")
        latency = f"{result.latency_ms:.2f}" if result.latency_ms is not None else "—"
        console.print(f"Assessment latency (ms): {latency}")
    console.print()
    console.print("Open report:")
    console.print("  codestrata open")


def _slugify(value: str) -> str:
    compact = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", compact).strip("-")
    return slug or "repository"
