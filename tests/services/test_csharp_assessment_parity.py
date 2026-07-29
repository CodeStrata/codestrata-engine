"""Phase 5.18 C# assessment parity checks."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.language.complexity.service import (
    ComplexityEvidenceService,
)
from codestrata.application.rules.architecture.pack import ArchitectureRulePack
from codestrata.application.rules.dependency.pack import DependencyRulePack
from codestrata.application.rules.dependency.rules import UnboundedRequirementRule
from codestrata.application.rules.security.pack import SecurityRulePack
from codestrata.application.rules.technical_debt.pack import TechnicalDebtRulePack
from codestrata.application.rules.testing.pack import TestingRulePack
from codestrata.config.settings import ComplexityEvidenceSettings
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.enums import RuleResultStatus
from codestrata.models import Repository
from codestrata.services.detectors.csharp_technology_detector import CsharpTechnologyDetector

ROOT = Path(__file__).resolve().parents[3]  # monorepo root
SAMPLE = ROOT / "test-fixtures" / "sample-csharp-app"


def test_packs_include_csharp() -> None:
    for pack in (
        ArchitectureRulePack(),
        SecurityRulePack(),
        TechnicalDebtRulePack(),
        DependencyRulePack(),
        TestingRulePack(),
    ):
        assert "csharp" in pack.supported_languages


def test_sample_csharp_app_complexity_collects() -> None:
    paths = tuple(
        path.relative_to(SAMPLE).as_posix()
        for path in SAMPLE.rglob("*.cs")
        if path.is_file()
    )
    texts = {
        relative: (SAMPLE / relative).read_text(encoding="utf-8")
        for relative in paths
    }
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(
                update={"enabled": False}
            ),
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False}),
            "php": ComplexityEvidenceSettings().php.model_copy(update={"enabled": False}),
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:sample-csharp",
        relative_paths=paths,
        file_texts=texts,
    )
    assert "language.csharp.complexity" in result.contributing_provider_ids
    assert result.files
    assert result.callables


def test_sample_csharp_app_detector() -> None:
    files = sorted(
        str(path.relative_to(SAMPLE)).replace("\\", "/")
        for path in SAMPLE.rglob("*")
        if path.is_file()
    )
    technologies = CsharpTechnologyDetector().detect(
        Repository(name="sample-csharp-app", path=SAMPLE, files=files)
    )
    names = {item.name for item in technologies}
    assert "C#" in names
    assert "ASP.NET Core" in names
    assert "Entity Framework Core" in names
    assert "xUnit" in names


def test_nuget_unbounded_star_rule() -> None:
    provenance = EvidenceProvenance(
        provider_id="dependency.nuget.manifest",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
        origin=EvidenceOrigin.MANIFEST,
        source_path="App.csproj",
    )
    declaration = DependencyDeclarationEvidence(
        evidence_id="ev:nuget-star",
        ecosystem=DependencyEcosystem.NUGET,
        manifest_type=DependencyManifestType.CSPROJ,
        declaration_kind=DependencyDeclarationKind.RUNTIME,
        normalized_identity="newtonsoft.json",
        original_identity="Newtonsoft.Json",
        raw_version="*",
        resolved_version_local="*",
        version_availability=DependencyEvidenceAvailability.AVAILABLE,
        version_resolution_status=DependencyVersionResolutionStatus.RESOLVED,
        extras=(),
        environment_marker=None,
        group_name="PackageReference",
        is_editable=False,
        is_local_path=False,
        source=DependencySourceLocation(
            path="App.csproj",
            line_start=1,
            line_end=1,
            snippet="Newtonsoft.Json:*",
        ),
        classification=SourceClassification.SOURCE,
        provenance=provenance,
    )
    evidence = AggregatedDependencyEvidence(
        repository_id="repo",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=(
            DependencyManifestEvidence(
                evidence_id="manifest:app",
                path="App.csproj",
                ecosystem=DependencyEcosystem.NUGET,
                manifest_type=DependencyManifestType.CSPROJ,
                parse_status=DependencyParseStatus.SUCCEEDED,
                classification=SourceClassification.SOURCE,
                declaration_count=1,
                unsupported_constructs=(),
                diagnostics=(),
                provenance=provenance,
            ),
        ),
        declarations=(declaration,),
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=1,
            manifests_supported=1,
            manifests_parsed=1,
            manifests_partially_parsed=0,
            manifests_failed=0,
            manifests_excluded=0,
            declarations_collected=1,
            unsupported_construct_count=0,
            unresolved_expression_count=0,
        ),
        contributing_provider_ids=("dependency.nuget.manifest",),
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(
            repository_id="repo:test",
            relative_paths=("App.csproj",),
        ),
        languages=LanguageInventoryView(languages=("csharp",)),
        dependency_evidence=evidence,
        policy=RuleExecutionPolicy(),
    )
    result = UnboundedRequirementRule().evaluate(context)
    assert result.status is RuleResultStatus.MATCHED
