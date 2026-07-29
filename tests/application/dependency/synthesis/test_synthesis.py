"""Phase 4.4.5 dependency synthesis tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.dependency.assessment.artifacts import (
    dependency_assessment_payload,
    write_dependency_assessment_artifact,
)
from codestrata.application.dependency.assessment.assembler import (
    DependencyAssessmentAssembler,
)
from codestrata.domain.dependency.assessment.enums import DependencyAssessmentStatus
from codestrata.domain.dependency.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.dependency.ids import (
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.dependency.synthesis.enums import (
    DependencyConclusionAudience,
    DependencyConclusionKind,
    DependencyRecommendationKind,
    DependencySynthesisStatus,
    DependencyThemeKind,
)
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
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.services.artifact_serialization import dumps_stable_json


def _provenance(path: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="dependency.test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
    )


def _decl(
    *,
    evidence_id: str,
    identity: str,
    path: str,
    kind: DependencyDeclarationKind = DependencyDeclarationKind.RUNTIME,
    classification: SourceClassification = SourceClassification.SOURCE,
    resolution: DependencyVersionResolutionStatus = (
        DependencyVersionResolutionStatus.RESOLVED
    ),
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
    raw_version: str | None = "1.0.0",
) -> DependencyDeclarationEvidence:
    return DependencyDeclarationEvidence(
        evidence_id=evidence_id,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=raw_version,
        version_availability=DependencyEvidenceAvailability.AVAILABLE,
        version_resolution_status=resolution,
        source=DependencySourceLocation(path=path, line_start=1, line_end=1),
        classification=classification,
        provenance=_provenance(path),
    )


def _manifest(
    *,
    path: str,
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
    status: DependencyParseStatus = DependencyParseStatus.SUCCEEDED,
    classification: SourceClassification = SourceClassification.SOURCE,
    unsupported: tuple[str, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> DependencyManifestEvidence:
    return DependencyManifestEvidence(
        evidence_id=f"ev:manifest:{path}",
        path=path,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        parse_status=status,
        classification=classification,
        unsupported_constructs=unsupported,
        diagnostics=diagnostics,
        provenance=_provenance(path),
    )


def _evidence(
    *,
    manifests: tuple[DependencyManifestEvidence, ...],
    declarations: tuple[DependencyDeclarationEvidence, ...],
    status: DependencyParseStatus = DependencyParseStatus.SUCCEEDED,
) -> AggregatedDependencyEvidence:
    return AggregatedDependencyEvidence(
        repository_id="repo:test",
        status=status,
        manifests=manifests,
        declarations=declarations,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=len(manifests),
            manifests_supported=len(manifests),
            manifests_parsed=sum(
                1
                for item in manifests
                if item.parse_status is DependencyParseStatus.SUCCEEDED
            ),
            manifests_partially_parsed=sum(
                1
                for item in manifests
                if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
            ),
            declarations_collected=len(declarations),
            unsupported_construct_count=sum(
                len(item.unsupported_constructs) for item in manifests
            ),
        ),
        evidence_fingerprint="fp-synth",
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    identity: str,
    classification: str = "source",
    severity: FindingSeverity = FindingSeverity.MEDIUM,
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{identity} on {path}",
        severity=severity,
        category=FindingCategory.DEPENDENCY,
        subject_keys=(path, identity),
        metadata={
            "classification": classification,
            "path": path,
            "ecosystem": "maven",
            "normalized_identity": identity,
            "confidence": "high",
            "taxonomy_id": "dependency.unknown",
            "evidence_id": f"ev:{identity}",
        },
    )


def test_schema_version_1_2_0() -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"


def test_synthesis_gate_disabled_and_not_requested() -> None:
    assembler = DependencyAssessmentAssembler()
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(_decl(evidence_id="d1", identity="a:a", path="pom.xml"),),
    )
    off = assembler.assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        include_synthesis=False,
    )
    assert off.synthesis.status is DependencySynthesisStatus.NOT_REQUESTED
    assert off.conclusions == ()
    assert off.recommendations == ()

    disabled = assembler.assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=False,
        evidence_enabled=False,
        dependency_evidence=None,
        include_synthesis=True,
    )
    assert disabled.status is DependencyAssessmentStatus.DISABLED
    assert disabled.synthesis.status is DependencySynthesisStatus.DISABLED
    assert any(
        item.kind is DependencyConclusionKind.DISABLED for item in disabled.conclusions
    )


def test_no_production_findings_and_test_observations() -> None:
    findings = (
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="tests/fixtures/pom.xml",
            identity="com.example:missing",
            classification="test",
        ),
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="tests/fixtures/requirements.txt",
            identity="httpx",
            classification="test",
        ),
    )
    evidence = _evidence(
        manifests=(
            _manifest(path="pom.xml"),
            _manifest(
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
            ),
            _manifest(
                path="tests/fixtures/requirements.txt",
                ecosystem=DependencyEcosystem.PYTHON,
                manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                classification=SourceClassification.TEST,
            ),
        ),
        declarations=(
            _decl(evidence_id="p1", identity="com.example:lib", path="pom.xml"),
            _decl(
                evidence_id="t1",
                identity="com.example:missing",
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
                resolution=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
                raw_version="${missing.version}",
            ),
            _decl(
                evidence_id="t2",
                identity="httpx",
                path="tests/fixtures/requirements.txt",
                classification=SourceClassification.TEST,
                ecosystem=DependencyEcosystem.PYTHON,
                manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
            ),
        ),
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    kinds = {item.kind for item in section.conclusions}
    assert DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS in kinds
    assert DependencyConclusionKind.TEST_FIXTURE_FINDINGS_PRESENT in kinds
    assert DependencyConclusionKind.PRODUCTION_HYGIENE_FINDINGS_PRESENT not in kinds
    assert DependencyConclusionKind.DECLARED_DEPENDENCIES_ONLY in kinds
    assert section.finding_ids == ()
    assert len(section.all_finding_ids) == 2

    prod_health = [
        item
        for item in section.conclusions
        if item.audience is DependencyConclusionAudience.PRODUCTION_HEALTH
    ]
    assert all(
        item.kind is DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS
        for item in prod_health
    )
    test_recs = [
        item
        for item in section.recommendations
        if item.kind is DependencyRecommendationKind.REVIEW_TEST_FIXTURE_DECLARATIONS
    ]
    assert len(test_recs) == 1
    remediations = [
        item
        for item in section.recommendations
        if item.kind
        in {
            DependencyRecommendationKind.DEFINE_UNRESOLVED_LOCAL_VERSION,
            DependencyRecommendationKind.REMOVE_DUPLICATE_DECLARATIONS,
            DependencyRecommendationKind.REVIEW_DEPENDENCY_HYGIENE_FINDINGS,
        }
    ]
    assert not remediations


def test_production_findings_present_and_rule_themes() -> None:
    findings = (
        _finding(
            rule_id=RULE_MUTABLE_VERSION,
            path="pom.xml",
            identity="com.example:snap",
            severity=FindingSeverity.HIGH,
        ),
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="pom.xml",
            identity="com.example:dup",
        ),
    )
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(
            _decl(
                evidence_id="d1",
                identity="com.example:snap",
                path="pom.xml",
                raw_version="1.0.0-SNAPSHOT",
            ),
            _decl(evidence_id="d2", identity="com.example:dup", path="pom.xml"),
        ),
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:prod",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    kinds = {item.kind for item in section.conclusions}
    assert DependencyConclusionKind.PRODUCTION_HYGIENE_FINDINGS_PRESENT in kinds
    assert DependencyConclusionKind.MUTABLE_VERSIONS_PRESENT in kinds
    assert DependencyConclusionKind.DUPLICATE_DECLARATIONS_PRESENT in kinds
    assert DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS not in kinds
    theme_kinds = {item.kind for item in section.themes}
    assert DependencyThemeKind.MUTABLE_VERSION_USAGE in theme_kinds
    assert DependencyThemeKind.DUPLICATE_DECLARATIONS in theme_kinds
    assert DependencyThemeKind.DECLARATION_HYGIENE in theme_kinds

    for rec in section.recommendations:
        assert rec.conclusion_ids
        assert all(cid in section.conclusion_ids for cid in rec.conclusion_ids)
    assert any(
        edge.relation.value == "recommendation_to_conclusion"
        for edge in section.traceability.edges
    )
    assert any(
        edge.relation.value == "conclusion_to_finding"
        for edge in section.traceability.edges
    )


def test_gradle_interpolation_coverage_not_finding() -> None:
    unsupported = (
        "build.gradle:42:unsupported_version_resolution:"
        "gradle_interpolation_uninspected:runtimeOnly:"
        "org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
    )
    diagnostics = (
        "version_resolution_unsupported:gradle_property_or_dynamic:"
        "build.gradle:runtimeOnly:org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
    )
    evidence = _evidence(
        manifests=(
            _manifest(
                path="build.gradle",
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
                unsupported=unsupported,
                diagnostics=diagnostics,
            ),
        ),
        declarations=(
            _decl(
                evidence_id="g1",
                identity="org.webjars.npm:bootstrap",
                path="build.gradle",
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                raw_version="${webjarsBootstrapVersion}",
                resolution=DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION,
            ),
        ),
        status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:petclinic",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    kinds = {item.kind for item in section.conclusions}
    assert DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS in kinds
    assert DependencyConclusionKind.UNSUPPORTED_RESOLUTION_COVERAGE in kinds
    assert DependencyConclusionKind.UNRESOLVED_VERSIONS_PRESENT not in kinds
    assert section.finding_ids == ()
    assert any(
        item.kind is DependencyRecommendationKind.EXPAND_GRADLE_RESOLUTION_COVERAGE
        for item in section.recommendations
    )
    assert not any(
        item.kind is DependencyRecommendationKind.DEFINE_UNRESOLVED_LOCAL_VERSION
        for item in section.recommendations
    )


def test_insufficient_evidence_and_determinism(tmp_path: Path) -> None:
    empty = AggregatedDependencyEvidence(
        repository_id="repo:empty",
        status=DependencyParseStatus.NOT_APPLICABLE,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=0, manifests_supported=0
        ),
        evidence_fingerprint="fp-empty",
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=empty,
    )
    assert section.status is DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE
    assert section.synthesis.status is DependencySynthesisStatus.INSUFFICIENT_EVIDENCE
    assert any(
        item.kind is DependencyConclusionKind.INSUFFICIENT_EVIDENCE
        for item in section.conclusions
    )

    findings = (
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="pom.xml",
            identity="com.example:x",
        ),
    )
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(
            _decl(
                evidence_id="d1",
                identity="com.example:x",
                path="pom.xml",
                resolution=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
                raw_version="${x}",
            ),
        ),
    )
    assembler = DependencyAssessmentAssembler()
    left = assembler.assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        evidence_fingerprint=evidence.evidence_fingerprint,
    )
    right = assembler.assemble(
        repository_id="repo:demo",
        findings=tuple(reversed(findings)),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        evidence_fingerprint=evidence.evidence_fingerprint,
    )
    assert left.theme_ids == right.theme_ids
    assert left.conclusion_ids == right.conclusion_ids
    assert left.recommendation_ids == right.recommendation_ids
    assert dumps_stable_json(dependency_assessment_payload(left)) == dumps_stable_json(
        dependency_assessment_payload(right)
    )
    text = write_dependency_assessment_artifact(left, tmp_path).path.read_text(
        encoding="utf-8"
    )
    assert "/Users/" not in text
    assert '"vulnerabilities"' not in text
    assert '"licenses"' not in text
    assert "dependency_health_score" not in text
    assert '"priority_score"' not in text
    assert "financial cost" not in text.lower()
    assert "effort hours" not in text.lower()
    assert "upgrade to the latest" not in text.lower()
    assert "vulnerable package" not in text.lower()


def test_webjars_npm_coordinate_is_not_npm_ecosystem_coverage() -> None:
    """Maven/Gradle org.webjars.npm:* must not imply npm/package.json relevance."""

    diagnostics = (
        "version_resolution_unsupported:gradle_property_or_dynamic:"
        "build.gradle:runtimeOnly:org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
    )
    evidence = _evidence(
        manifests=(
            _manifest(
                path="build.gradle",
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
                diagnostics=diagnostics,
                unsupported=(
                    "build.gradle:1:unsupported_version_resolution:"
                    "gradle_interpolation_uninspected:runtimeOnly:"
                    "org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
                ),
            ),
        ),
        declarations=(
            _decl(
                evidence_id="g1",
                identity="org.webjars.npm:bootstrap",
                path="build.gradle",
                ecosystem=DependencyEcosystem.GRADLE,
                manifest_type=DependencyManifestType.BUILD_GRADLE,
                raw_version="${webjarsBootstrapVersion}",
                resolution=DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION,
            ),
        ),
        status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:petclinic",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    kinds = {item.kind for item in section.conclusions}
    theme_kinds = {item.kind for item in section.themes}
    assert DependencyConclusionKind.UNSUPPORTED_ECOSYSTEM_COVERAGE not in kinds
    assert DependencyThemeKind.PARTIAL_ECOSYSTEM_COVERAGE not in theme_kinds
    assert DependencyConclusionKind.UNSUPPORTED_RESOLUTION_COVERAGE in kinds


def test_unknown_role_separation() -> None:
    findings = (
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="vendor/odd/pom.xml",
            identity="com.example:unk",
            classification="unknown",
        ),
    )
    evidence = _evidence(
        manifests=(
            _manifest(path="pom.xml"),
            _manifest(
                path="vendor/odd/pom.xml",
                classification=SourceClassification.UNKNOWN,
            ),
        ),
        declarations=(
            _decl(evidence_id="p1", identity="com.example:ok", path="pom.xml"),
            _decl(
                evidence_id="u1",
                identity="com.example:unk",
                path="vendor/odd/pom.xml",
                classification=SourceClassification.UNKNOWN,
            ),
        ),
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    assert section.finding_ids == ()
    assert len(section.all_finding_ids) == 1
    assert section.finding_inventory.unknown.finding_count == 1
    assert DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS in {
        item.kind for item in section.conclusions
    }
    assert DependencyConclusionKind.PRODUCTION_HYGIENE_FINDINGS_PRESENT not in {
        item.kind for item in section.conclusions
    }
