"""Phase 4.4.4 dependency inventory, hotspots, and status-semantics tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.dependency.assessment.artifacts import (
    dependency_assessment_payload,
    write_dependency_assessment_artifact,
)
from codestrata.application.dependency.assessment.assembler import (
    DependencyAssessmentAssembler,
)
from codestrata.application.dependency.assessment.inventory import (
    build_aggregation_inventory,
    build_declaration_inventory,
    build_diagnostics_summary,
    build_evidence_summary,
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    build_manifest_inventory,
    map_source_role,
)
from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencySourceRole,
)
from codestrata.domain.dependency.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.dependency.ids import (
    RULE_DUPLICATE_DECLARATION,
    RULE_UNRESOLVED_VERSION,
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
    is_management: bool = False,
    raw_version: str | None = "1.0.0",
    resolution: DependencyVersionResolutionStatus = (
        DependencyVersionResolutionStatus.RESOLVED
    ),
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
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
        is_dependency_management=is_management,
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
    failed = sum(
        1 for item in manifests if item.parse_status is DependencyParseStatus.FAILED
    )
    partial = sum(
        1
        for item in manifests
        if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
    )
    succeeded = sum(
        1
        for item in manifests
        if item.parse_status is DependencyParseStatus.SUCCEEDED
    )
    return AggregatedDependencyEvidence(
        repository_id="repo:test",
        status=status,
        manifests=manifests,
        declarations=declarations,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=len(manifests),
            manifests_supported=len(manifests),
            manifests_parsed=succeeded,
            manifests_partially_parsed=partial,
            manifests_failed=failed,
            declarations_collected=len(declarations),
            unsupported_construct_count=sum(
                len(item.unsupported_constructs) for item in manifests
            ),
        ),
        evidence_fingerprint="fp-inventory-test",
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


def test_assessment_schema_version_is_1_2_0() -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    section = DependencyAssessmentAssembler().assemble_empty(repository_id="repo:x")
    assert section.section_version == "1.2.0"
    assert section.metadata.get("assessment_milestone") == "4.4.5"


def test_role_partitions_and_production_primary_findings() -> None:
    findings = (
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="pom.xml",
            identity="com.example:prod",
            severity=FindingSeverity.HIGH,
        ),
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="tests/fixtures/requirements.txt",
            identity="httpx",
            classification="test",
        ),
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="vendor/odd/pom.xml",
            identity="com.example:unk",
            classification="unknown",
        ),
    )
    refs = build_finding_references(findings)
    inventory = build_finding_inventory(refs)
    assert inventory.production.finding_count == 1
    assert inventory.test.finding_count == 1
    assert inventory.unknown.finding_count == 1
    assert inventory.total_finding_count == 3

    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=_evidence(
            manifests=(
                _manifest(path="pom.xml"),
                _manifest(
                    path="tests/fixtures/requirements.txt",
                    ecosystem=DependencyEcosystem.PYTHON,
                    manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                    classification=SourceClassification.TEST,
                ),
                _manifest(
                    path="vendor/odd/pom.xml",
                    classification=SourceClassification.UNKNOWN,
                ),
            ),
            declarations=(
                _decl(evidence_id="d1", identity="com.example:prod", path="pom.xml"),
                _decl(
                    evidence_id="d2",
                    identity="httpx",
                    path="tests/fixtures/requirements.txt",
                    classification=SourceClassification.TEST,
                    ecosystem=DependencyEcosystem.PYTHON,
                    manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                ),
                _decl(
                    evidence_id="d3",
                    identity="com.example:unk",
                    path="vendor/odd/pom.xml",
                    classification=SourceClassification.UNKNOWN,
                ),
            ),
        ),
    )
    assert section.finding_ids == inventory.production.finding_ids
    assert len(section.finding_ids) == 1
    assert len(section.all_finding_ids) == 3
    assert set(section.all_finding_ids) == {
        *inventory.production.finding_ids,
        *inventory.test.finding_ids,
        *inventory.unknown.finding_ids,
    }
    assert section.execution_summary.visible_finding_count == 1
    assert section.execution_summary.total_finding_count == 3
    assert section.execution_summary.test_finding_count == 1


def test_declaration_kind_and_management_plugin_separation() -> None:
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(
            _decl(
                evidence_id="a",
                identity="com.example:active",
                path="pom.xml",
                kind=DependencyDeclarationKind.RUNTIME,
            ),
            _decl(
                evidence_id="m",
                identity="com.example:managed",
                path="pom.xml",
                kind=DependencyDeclarationKind.DEPENDENCY_MANAGEMENT,
                is_management=True,
                resolution=DependencyVersionResolutionStatus.NOT_APPLICABLE,
            ),
            _decl(
                evidence_id="p",
                identity="org.apache.maven.plugins:compiler",
                path="pom.xml",
                kind=DependencyDeclarationKind.PLUGIN,
                resolution=DependencyVersionResolutionStatus.NOT_APPLICABLE,
            ),
            _decl(
                evidence_id="t",
                identity="junit:junit",
                path="pom.xml",
                kind=DependencyDeclarationKind.TEST,
            ),
        ),
    )
    decl_inv = build_declaration_inventory(evidence)
    assert decl_inv.production.active_declaration_count == 2  # runtime + test kind
    assert decl_inv.production.dependency_management_count == 1
    assert decl_inv.production.plugin_count == 1
    assert decl_inv.total_declaration_count == 4

    agg = build_aggregation_inventory(evidence)
    kinds = {item.label: item.count for item in agg.by_declaration_kind}
    assert kinds["runtime"] == 1
    assert kinds["dependency_management"] == 1
    assert kinds["plugin"] == 1
    assert kinds["test"] == 1

    man_inv = build_manifest_inventory(
        evidence=evidence, finding_refs=()
    )
    entry = man_inv.entries[0]
    assert entry.active_declaration_count == 2
    assert entry.dependency_management_count == 1
    assert entry.plugin_count == 1
    assert entry.test_or_development_count == 1


def test_hotspot_ordering_and_ids_deterministic() -> None:
    findings = (
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="a/pom.xml",
            identity="com.example:a",
            severity=FindingSeverity.LOW,
        ),
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="b/pom.xml",
            identity="com.example:b",
            severity=FindingSeverity.HIGH,
        ),
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="b/pom.xml",
            identity="com.example:b2",
            severity=FindingSeverity.MEDIUM,
        ),
        _finding(
            rule_id=RULE_DUPLICATE_DECLARATION,
            path="tests/fixtures/pom.xml",
            identity="com.example:t",
            classification="test",
            severity=FindingSeverity.HIGH,
        ),
    )
    refs = build_finding_references(findings)
    evidence = _evidence(
        manifests=(
            _manifest(path="a/pom.xml"),
            _manifest(path="b/pom.xml"),
            _manifest(
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
            ),
        ),
        declarations=(
            _decl(evidence_id="a1", identity="com.example:a", path="a/pom.xml"),
            _decl(evidence_id="b1", identity="com.example:b", path="b/pom.xml"),
            _decl(
                evidence_id="t1",
                identity="com.example:t",
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
            ),
        ),
    )
    man_inv = build_manifest_inventory(evidence=evidence, finding_refs=refs)
    hotspots = build_hotspot_inventory(manifest_inventory=man_inv, finding_refs=refs)
    assert [item.path for item in hotspots.production] == ["b/pom.xml", "a/pom.xml"]
    assert hotspots.production[0].highest_severity == "high"
    assert len(hotspots.production[0].distinct_rule_ids) == 2
    assert hotspots.test[0].path == "tests/fixtures/pom.xml"
    left = build_hotspot_inventory(manifest_inventory=man_inv, finding_refs=refs)
    right = build_hotspot_inventory(manifest_inventory=man_inv, finding_refs=refs)
    assert [item.hotspot_id for item in left.production] == [
        item.hotspot_id for item in right.production
    ]


def test_gradle_interpolation_is_diagnostic_not_finding() -> None:
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
    assert section.status is DependencyAssessmentStatus.SUCCEEDED
    assert section.finding_ids == ()
    assert section.all_finding_ids == ()
    summary = build_diagnostics_summary(evidence)
    assert summary.production_count >= 1
    assert any(
        item.diagnostic_code == "unsupported_gradle_resolution"
        for item in summary.records
    )
    assert "unsupported_gradle_resolution" in section.diagnostics


def test_production_parse_failure_partial_status() -> None:
    evidence = _evidence(
        manifests=(
            _manifest(path="pom.xml", status=DependencyParseStatus.FAILED),
            _manifest(
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
            ),
        ),
        declarations=(
            _decl(
                evidence_id="t1",
                identity="junit:junit",
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
            ),
        ),
        status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    assert section.status is DependencyAssessmentStatus.PARTIALLY_SUCCEEDED
    assert section.execution_summary.production_parse_failures == 1
    assert section.execution_summary.test_fixture_parse_failures == 0


def test_test_fixture_parse_failure_remains_succeeded() -> None:
    evidence = _evidence(
        manifests=(
            _manifest(path="pom.xml"),
            _manifest(
                path="tests/fixtures/pom.xml",
                classification=SourceClassification.TEST,
                status=DependencyParseStatus.FAILED,
            ),
        ),
        declarations=(
            _decl(evidence_id="p1", identity="com.example:lib", path="pom.xml"),
        ),
        status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
    )
    section = DependencyAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
    )
    assert section.status is DependencyAssessmentStatus.SUCCEEDED
    assert section.execution_summary.production_parse_failures == 0
    assert section.execution_summary.test_fixture_parse_failures == 1
    assert "evidence_status:partially_succeeded" in section.diagnostics


def test_no_supported_manifests_and_disabled_failed() -> None:
    empty = AggregatedDependencyEvidence(
        repository_id="repo:empty",
        status=DependencyParseStatus.NOT_APPLICABLE,
        coverage=DependencyEvidenceCoverage(manifests_discovered=0, manifests_supported=0),
        evidence_fingerprint="fp-empty",
    )
    insufficient = DependencyAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=empty,
    )
    assert insufficient.status is DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE

    failed_ev = AggregatedDependencyEvidence(
        repository_id="repo:fail",
        status=DependencyParseStatus.FAILED,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=1, manifests_supported=1, manifests_failed=1
        ),
        evidence_fingerprint="fp-fail",
    )
    failed = DependencyAssessmentAssembler().assemble(
        repository_id="repo:fail",
        findings=(),
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=failed_ev,
    )
    assert failed.status is DependencyAssessmentStatus.FAILED

    disabled = DependencyAssessmentAssembler().assemble(
        repository_id="repo:off",
        findings=(),
        pack_enabled=False,
        evidence_enabled=False,
        dependency_evidence=None,
    )
    assert disabled.status is DependencyAssessmentStatus.DISABLED


def test_traceability_and_no_absolute_paths_repeat_identity(tmp_path: Path) -> None:
    findings = (
        _finding(
            rule_id=RULE_UNRESOLVED_VERSION,
            path="pom.xml",
            identity="com.example:missing",
        ),
    )
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(
            _decl(
                evidence_id="d1",
                identity="com.example:missing",
                path="pom.xml",
                resolution=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
                raw_version="${missing.version}",
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
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        dependency_evidence=evidence,
        evidence_fingerprint=evidence.evidence_fingerprint,
    )
    assert dumps_stable_json(dependency_assessment_payload(left)) == dumps_stable_json(
        dependency_assessment_payload(right)
    )
    written = write_dependency_assessment_artifact(left, tmp_path)
    text = written.path.read_text(encoding="utf-8")
    assert "/Users/" not in text
    assert "C:\\" not in text
    assert left.manifest_inventory.entries[0].evidence_id
    assert left.finding_summaries[0].evidence_ids
    assert any(
        edge.relation.value == "section_to_manifest"
        for edge in left.traceability.edges
    )
    assert any(
        edge.relation.value == "section_to_hotspot" for edge in left.traceability.edges
    )


def test_no_scores_or_external_metadata_fields_on_section() -> None:
    from codestrata.domain.dependency.assessment.models import DependencyAssessmentSection

    fields = set(DependencyAssessmentSection.model_fields)
    forbidden = {
        "dependency_health_score",
        "priority_score",
        "frameworks",
        "vulnerabilities",
        "licenses",
        "cves",
        "executive_summary",
        "modernization_candidates",
        "upgrade_candidates",
        "financial_cost",
        "effort_hours",
    }
    assert forbidden.isdisjoint(fields)
    # Synthesis fields are present as of 4.4.5.
    assert "themes" in fields
    assert "conclusions" in fields
    assert "recommendations" in fields
    assert "synthesis" in fields


def test_evidence_summary_and_source_role_mapping() -> None:
    assert map_source_role("source", path="src/main/pom.xml") is DependencySourceRole.PRODUCTION
    assert map_source_role("test", path="src/test/pom.xml") is DependencySourceRole.TEST
    evidence = _evidence(
        manifests=(_manifest(path="pom.xml"),),
        declarations=(
            _decl(evidence_id="a", identity="a:a", path="pom.xml"),
            _decl(
                evidence_id="b",
                identity="b:b",
                path="pom.xml",
                resolution=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
                raw_version="${x}",
            ),
        ),
    )
    summary = build_evidence_summary(evidence)
    assert summary.declarations_collected == 2
    assert summary.proven_unresolved_count == 1
    assert summary.production_declaration_count == 2
    assert "maven" in summary.ecosystems
