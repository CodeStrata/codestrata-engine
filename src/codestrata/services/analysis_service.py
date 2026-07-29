"""Application service that orchestrates repository analysis."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from codestrata import RULESET_VERSION
from codestrata.models import AnalysisResult, Finding, Repository, RepositoryFacts
from codestrata.services.contracts import Analyzer, RecommendationEngine, TechnologyDetector
from codestrata.services.recommendation_engine import ModernizationRecommendationEngine
from codestrata.services.technology_facts import technology_facts_from_detections
from codestrata.static_analysis.models import StaticAnalysisResult
from codestrata.static_analysis.ordering import sort_findings
from codestrata.static_analysis.service import StaticAnalysisService

logger = logging.getLogger(__name__)


class AnalysisService:
    """Coordinate technology detection and repository analysis."""

    def __init__(
        self,
        technology_detector: TechnologyDetector,
        analyzer: Analyzer,
        analyzer_version: str,
        recommendation_engine: RecommendationEngine | None = None,
        static_analysis_service: StaticAnalysisService | None = None,
    ) -> None:
        self._technology_detector = technology_detector
        self._analyzer = analyzer
        self._analyzer_version = analyzer_version
        self._recommendation_engine = recommendation_engine or ModernizationRecommendationEngine()
        self._static_analysis_service = static_analysis_service

    def analyze(
        self,
        repository: Repository,
        *,
        static_analysis_output_directory: Path | None = None,
    ) -> AnalysisResult:
        """Analyze a scanned repository and return structured results."""

        started_at = datetime.now(UTC)
        start_time = perf_counter()

        logger.info(
            "Repository analysis started",
            extra={
                "repository_name": repository.name,
                "repository_path": str(repository.path),
                "stage": "analysis",
                "file_count": len(repository.files),
            },
        )

        try:
            technologies = self._technology_detector.detect(repository)

            logger.info(
                "Technology detection completed",
                extra={
                    "repository_name": repository.name,
                    "stage": "technology_detection",
                    "technology_count": len(technologies),
                },
            )

            analyzer_result = self._analyzer.analyze(
                repository=repository,
                technologies=technologies,
            )

            facts = analyzer_result.facts.merge(
                RepositoryFacts(
                    technology=technology_facts_from_detections(technologies),
                )
            )

            static_analysis_results: list[StaticAnalysisResult] = []
            provider_findings: list[Finding] = []
            if self._static_analysis_service is not None:
                static_analysis_results, provider_findings = self._static_analysis_service.analyze(
                    repository=repository,
                    technologies=technologies,
                    output_directory=static_analysis_output_directory,
                )

            findings = sort_findings([*analyzer_result.findings, *provider_findings])

            recommendations = self._recommendation_engine.generate(
                facts=facts,
                findings=findings,
                technologies=technologies,
            )

            completed_at = datetime.now(UTC)
            duration_ms = round((perf_counter() - start_time) * 1000, 2)

            logger.info(
                "Repository analysis completed",
                extra={
                    "repository_name": repository.name,
                    "stage": "analysis",
                    "technology_count": len(technologies),
                    "finding_count": len(findings),
                    "recommendation_count": len(recommendations),
                    "duration_ms": duration_ms,
                },
            )

            return AnalysisResult(
                repository=repository,
                technologies=technologies,
                facts=facts,
                findings=findings,
                recommendations=recommendations,
                static_analysis_results=static_analysis_results,
                started_at=started_at,
                completed_at=completed_at,
                analyzer_version=self._analyzer_version,
                ruleset_version=RULESET_VERSION,
            )

        except Exception:
            logger.exception(
                "Repository analysis failed",
                extra={
                    "repository_name": repository.name,
                    "stage": "analysis",
                },
            )
            raise
