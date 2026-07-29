"""Shared default analysis pipeline construction for CLI commands."""

from __future__ import annotations

from codestrata import __version__
from codestrata.config.settings import CodestrataSettings
from codestrata.extensions.analyzers import resolve_enabled_analyzers
from codestrata.services.analysis_service import AnalysisService
from codestrata.services.analyzers import (
    ArchitectureAnalyzer,
    BuildDiscoveryAnalyzer,
    BuildMetadataAnalyzer,
    CicdDiscoveryAnalyzer,
    CloudReadinessAnalyzer,
    CompositeAnalyzer,
    DependencyDiscoveryAnalyzer,
    DependencyHealthAnalyzer,
    DependencyMetadataAnalyzer,
    RepositoryMetricsAnalyzer,
    SecurityAnalyzer,
)
from codestrata.services.contracts import Analyzer
from codestrata.services.detectors.composite_technology_detector import (
    CompositeTechnologyDetector,
)
from codestrata.services.detectors.csharp_technology_detector import CsharpTechnologyDetector
from codestrata.services.detectors.java_technology_detector import JavaTechnologyDetector
from codestrata.services.detectors.javascript_technology_detector import (
    JavaScriptTechnologyDetector,
)
from codestrata.services.detectors.php_technology_detector import PhpTechnologyDetector
from codestrata.services.detectors.python_technology_detector import PythonTechnologyDetector
from codestrata.static_analysis.providers import PmdProvider
from codestrata.static_analysis.service import StaticAnalysisService


def builtin_analyzers() -> list[Analyzer]:
    """Return the first-party Phase 1 analyzer list (Community default)."""

    return [
        RepositoryMetricsAnalyzer(),
        BuildDiscoveryAnalyzer(),
        BuildMetadataAnalyzer(),
        DependencyDiscoveryAnalyzer(),
        DependencyMetadataAnalyzer(),
        DependencyHealthAnalyzer(),
        CicdDiscoveryAnalyzer(),
        SecurityAnalyzer(),
        ArchitectureAnalyzer(),
        CloudReadinessAnalyzer(),
    ]


def create_default_analysis_service(
    settings: CodestrataSettings,
    *,
    pmd_executable: str | None = None,
    static_analysis_enabled: bool | None = None,
    pmd_profile: str | None = None,
) -> AnalysisService:
    """Create the standard CodeStrata analysis service from application settings."""

    technology_detector = CompositeTechnologyDetector(
        detectors=[
            JavaTechnologyDetector(),
            JavaScriptTechnologyDetector(),
            PhpTechnologyDetector(),
            CsharpTechnologyDetector(),
            PythonTechnologyDetector(),
        ]
    )

    static_analysis_settings = settings.static_analysis
    enabled = (
        static_analysis_settings.enabled
        if static_analysis_enabled is None
        else static_analysis_enabled
    )
    providers = []
    if static_analysis_settings.pmd.enabled:
        profile = pmd_profile or static_analysis_settings.pmd.profile
        providers.append(
            PmdProvider(
                executable=pmd_executable or static_analysis_settings.pmd.executable,
                profile=profile,
                rulesets=static_analysis_settings.pmd.rulesets,
                timeout_seconds=static_analysis_settings.pmd.timeout_seconds,
                enabled=True,
            )
        )

    static_analysis_service = StaticAnalysisService(
        providers=providers,
        enabled=enabled,
        fail_on_provider_error=static_analysis_settings.fail_on_provider_error,
    )

    analyzers: list[Analyzer] = builtin_analyzers()
    analyzers.extend(
        resolve_enabled_analyzers(
            settings.extensions.analyzers.enabled,
            strict=True,
        )
    )

    return AnalysisService(
        technology_detector=technology_detector,
        analyzer=CompositeAnalyzer(analyzers=analyzers),
        analyzer_version=__version__,
        static_analysis_service=static_analysis_service,
    )
