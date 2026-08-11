"""Dependency hygiene SharedRule tests (Phase 4.4.3)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.rules.dependency.helpers import (
    is_exact_version,
    is_mutable_version,
)
from codestrata.application.rules.dependency.pack import DependencyRulePack, dependency_rules
from codestrata.application.rules.dependency.registration import register_dependency_pack
from codestrata.application.rules.dependency.rules import (
    ConflictingExactVersionsRule,
    DuplicateDeclarationRule,
    MutableVersionRule,
    UnboundedRequirementRule,
    UnresolvedVersionRule,
)
from codestrata.application.rules.facade import RuleExecutionFacade
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import load_settings
from codestrata.domain.dependency.ids import (
    HYGIENE_RULE_IDS,
    PACK_ID,
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
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
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.enums import (
    RuleCategory,
    MatchEvidenceConfidence,
    RuleResultStatus,
    RuleSeverity,
)


def _provenance(path: str = "pom.xml") -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="dependency.maven.manifest",
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
    path: str = "pom.xml",
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    manifest_type: DependencyManifestType = DependencyManifestType.POM_XML,
    kind: DependencyDeclarationKind = DependencyDeclarationKind.RUNTIME,
    raw_version: str | None = "1.0.0",
    resolved: str | None = None,
    availability: DependencyEvidenceAvailability = DependencyEvidenceAvailability.AVAILABLE,
    resolution_status: DependencyVersionResolutionStatus | None = None,
    profile: str | None = None,
    group_name: str | None = None,
    configuration_name: str | None = None,
    marker: str | None = None,
    extras: tuple[str, ...] = (),
    optional: bool = False,
    is_management: bool = False,
    is_editable: bool = False,
    is_local_path: bool = False,
    classification: SourceClassification = SourceClassification.SOURCE,
    line: int = 1,
) -> DependencyDeclarationEvidence:
    if resolution_status is None:
        if availability is DependencyEvidenceAvailability.AVAILABLE and raw_version:
            resolution_status = DependencyVersionResolutionStatus.RESOLVED
        elif raw_version:
            resolution_status = DependencyVersionResolutionStatus.NOT_APPLICABLE
        else:
            resolution_status = DependencyVersionResolutionStatus.NOT_APPLICABLE
    return DependencyDeclarationEvidence(
        evidence_id=evidence_id,
        ecosystem=ecosystem,
        manifest_type=manifest_type,
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=resolved if resolved is not None else raw_version,
        version_availability=availability,
        version_resolution_status=resolution_status,
        optional=optional,
        profile=profile,
        extras=extras,
        environment_marker=marker,
        configuration_name=configuration_name,
        group_name=group_name,
        is_editable=is_editable,
        is_local_path=is_local_path,
        is_dependency_management=is_management,
        source=DependencySourceLocation(
            path=path, line_start=line, line_end=line, snippet=identity
        ),
        classification=classification,
        provenance=_provenance(path),
    )


def _manifest(
    *,
    path: str = "pom.xml",
    unresolved: tuple[str, ...] = (),
    unsupported: tuple[str, ...] = (),
    classification: SourceClassification = SourceClassification.SOURCE,
) -> DependencyManifestEvidence:
    return DependencyManifestEvidence(
        evidence_id=f"ev:manifest:{path}",
        path=path,
        ecosystem=DependencyEcosystem.MAVEN,
        manifest_type=DependencyManifestType.POM_XML,
        parse_status=(
            DependencyParseStatus.PARTIALLY_SUCCEEDED
            if unresolved or unsupported
            else DependencyParseStatus.SUCCEEDED
        ),
        classification=classification,
        unresolved_expressions=unresolved,
        unsupported_constructs=unsupported,
        provenance=_provenance(path),
    )


def _evidence(
    declarations: tuple[DependencyDeclarationEvidence, ...] = (),
    manifests: tuple[DependencyManifestEvidence, ...] | None = None,
) -> AggregatedDependencyEvidence:
    if manifests is None:
        paths = sorted({item.source.path for item in declarations}) or ["pom.xml"]
        manifests = tuple(_manifest(path=path) for path in paths)
    return AggregatedDependencyEvidence(
        repository_id="repo:test",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=manifests,
        declarations=declarations,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=len(manifests),
            manifests_supported=len(manifests),
            manifests_parsed=len(manifests),
            declarations_collected=len(declarations),
        ),
        evidence_fingerprint="fp-test",
    )


def _context(
    evidence: AggregatedDependencyEvidence | None,
    languages: tuple[str, ...] = ("java", "python"),
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(
            repository_id="repo:test",
            relative_paths=("pom.xml", "pyproject.toml", "composer.json"),
        ),
        languages=LanguageInventoryView(languages=languages),
        dependency_evidence=evidence,
        policy=RuleExecutionPolicy(),
    )


def test_pack_registration_and_rule_ids() -> None:
    pack = DependencyRulePack()
    assert pack.pack_id == PACK_ID
    assert pack.included_rule_ids == HYGIENE_RULE_IDS
    rules = dependency_rules()
    assert {str(rule.metadata.rule_id) for rule in rules} == set(HYGIENE_RULE_IDS)
    registry = RuleRegistry()
    register_dependency_pack(registry)
    assert registry.size == len(HYGIENE_RULE_IDS)


def test_rules_not_applicable_without_evidence() -> None:
    result = UnresolvedVersionRule().evaluate(_context(None))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_unresolved_version_matches_and_skips_resolved_managed() -> None:
    unresolved = _decl(
        evidence_id="ev:u1",
        identity="com.example:missing-prop",
        raw_version="${missing.version}",
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
    )
    resolved = _decl(
        evidence_id="ev:r1",
        identity="com.example:ok",
        raw_version="${lib.version}",
        resolved="1.2.3",
        availability=DependencyEvidenceAvailability.AVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.RESOLVED,
    )
    managed = _decl(
        evidence_id="ev:m1",
        identity="com.example:managed",
        raw_version=None,
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
        is_management=True,
        kind=DependencyDeclarationKind.DEPENDENCY_MANAGEMENT,
    )
    active_managed = _decl(
        evidence_id="ev:a1",
        identity="com.example:managed",
        raw_version=None,
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
    )
    local = _decl(
        evidence_id="ev:l1",
        identity="./local-pkg",
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
        raw_version=None,
        is_local_path=True,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
    )
    evidence = _evidence(
        (unresolved, resolved, managed, active_managed, local),
        manifests=(
            _manifest(path="pom.xml", unresolved=("com.example:missing-prop:${missing.version}",)),
        ),
    )
    result = UnresolvedVersionRule().evaluate(_context(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert "${missing.version}" in result.matches[0].summary


def test_unresolved_gradle_interpolation_is_diagnostic_not_finding() -> None:
    """Unsupported Gradle interpolation must not produce unresolved-version findings."""

    manifest = DependencyManifestEvidence(
        evidence_id="ev:g",
        path="build.gradle",
        ecosystem=DependencyEcosystem.GRADLE,
        manifest_type=DependencyManifestType.BUILD_GRADLE,
        parse_status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
        unresolved_expressions=(),
        unsupported_constructs=(
            "build.gradle:42:unsupported_version_resolution:"
            "gradle_interpolation_uninspected:runtimeOnly:"
            "org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
        ),
        diagnostics=(
            "version_resolution_unsupported:gradle_property_or_dynamic:"
            "build.gradle:runtimeOnly:org.webjars.npm:bootstrap:${webjarsBootstrapVersion}",
        ),
        provenance=_provenance("build.gradle"),
    )
    unsupported_decl = _decl(
        evidence_id="ev:g1",
        identity="org.webjars.npm:bootstrap",
        path="build.gradle",
        ecosystem=DependencyEcosystem.GRADLE,
        manifest_type=DependencyManifestType.BUILD_GRADLE,
        raw_version="${webjarsBootstrapVersion}",
        resolved=None,
        availability=DependencyEvidenceAvailability.UNSUPPORTED,
        resolution_status=DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION,
    )
    evidence = AggregatedDependencyEvidence(
        repository_id="repo:test",
        status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
        manifests=(manifest,),
        declarations=(unsupported_decl,),
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=1,
            manifests_supported=1,
            manifests_partially_parsed=1,
            unsupported_construct_count=1,
        ),
    )
    result = UnresolvedVersionRule().evaluate(_context(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED
    assert manifest.diagnostics
    assert any(
        "unsupported_version_resolution" in item
        for item in manifest.unsupported_constructs
    )


def test_parent_bom_uncertainty_does_not_match_unresolved_version() -> None:
    managed = _decl(
        evidence_id="ev:bom",
        identity="org.springframework.boot:spring-boot-starter-web",
        raw_version=None,
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
    )
    evidence = _evidence(
        (managed,),
        manifests=(
            _manifest(
                path="pom.xml",
                unsupported=(
                    "pom.xml:parent_not_fetched:org.springframework.boot:spring-boot-starter-parent",
                ),
            ),
        ),
    )
    result = UnresolvedVersionRule().evaluate(_context(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_generic_unavailable_without_proven_status_does_not_match() -> None:
    """Do not infer proven absence from UNAVAILABLE alone."""

    item = _decl(
        evidence_id="ev:legacy",
        identity="com.example:legacy",
        raw_version="${maybe.missing}",
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
    )
    result = UnresolvedVersionRule().evaluate(_context(_evidence((item,))))
    assert result.status is RuleResultStatus.NOT_MATCHED

def test_mutable_version_bounded_syntax() -> None:
    assert is_mutable_version("1.0.0-SNAPSHOT")
    assert is_mutable_version("latest")
    assert is_mutable_version("latest.release")
    assert is_mutable_version("RELEASE")
    assert is_mutable_version("1.+")
    assert is_mutable_version("+")
    assert not is_mutable_version("1.2.3")
    assert not is_mutable_version(">=1.0,<2.0")
    assert not is_exact_version(">=1.0,<2.0")
    assert is_exact_version("1.2.3")

    snapshot = _decl(
        evidence_id="ev:s",
        identity="com.example:snap",
        raw_version="1.0.0-SNAPSHOT",
    )
    stable = _decl(
        evidence_id="ev:st",
        identity="com.example:stable",
        raw_version="1.2.3",
    )
    ranged = _decl(
        evidence_id="ev:rg",
        identity="demo",
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.PYPROJECT_TOML,
        raw_version=">=1.0,<2.0",
    )
    result = MutableVersionRule().evaluate(_context(_evidence((snapshot, stable, ranged))))
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert "SNAPSHOT" in result.matches[0].summary


def test_unbounded_python_requirement() -> None:
    bare = _decl(
        evidence_id="ev:py1",
        identity="requests",
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
        path="requirements.txt",
        raw_version=None,
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
        extras=("security",),
        marker='python_version >= "3.10"',
    )
    pinned = _decl(
        evidence_id="ev:py2",
        identity="httpx",
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
        path="requirements.txt",
        raw_version="==0.27.0",
    )
    editable = _decl(
        evidence_id="ev:py3",
        identity="localpkg",
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
        path="requirements.txt",
        raw_version=None,
        is_editable=True,
    )
    java = _decl(
        evidence_id="ev:j1",
        identity="com.example:lib",
        raw_version=None,
        resolved=None,
        availability=DependencyEvidenceAvailability.UNAVAILABLE,
    )
    result = UnboundedRequirementRule().evaluate(
        _context(_evidence((bare, pinned, editable, java)))
    )
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert "requests" in result.matches[0].summary
    assert "security" in result.matches[0].summary
    assert "python_version" in result.matches[0].summary


def test_composer_unbounded_and_mutable_versions() -> None:
    wildcard = _decl(
        evidence_id="ev:c1",
        identity="vendor/wildcard",
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        path="composer.json",
        raw_version="*",
        group_name="require",
    )
    pinned = _decl(
        evidence_id="ev:c2",
        identity="laravel/framework",
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        path="composer.json",
        raw_version="^11.0",
        group_name="require",
    )
    floating = _decl(
        evidence_id="ev:c3",
        identity="vendor/dev-branch",
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        path="composer.json",
        raw_version="dev-main",
        group_name="require-dev",
    )
    duplicate_a = _decl(
        evidence_id="ev:c4",
        identity="vendor/dup",
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        path="composer.json",
        raw_version="1.2.3",
        group_name="require",
        line=10,
    )
    duplicate_b = _decl(
        evidence_id="ev:c5",
        identity="vendor/dup",
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        path="composer.json",
        raw_version="1.2.3",
        group_name="require",
        line=20,
    )
    evidence = _evidence((wildcard, pinned, floating, duplicate_a, duplicate_b))
    context = _context(evidence, languages=("php",))
    unbounded = UnboundedRequirementRule().evaluate(context)
    assert unbounded.status is RuleResultStatus.MATCHED
    assert any("vendor/wildcard" in item.summary for item in unbounded.matches)
    mutable = MutableVersionRule().evaluate(context)
    assert mutable.status is RuleResultStatus.MATCHED
    assert any(
        "dev-main" in (item.summary or "") or "dev-branch" in item.summary
        for item in mutable.matches
    )
    assert is_mutable_version("dev-master")
    assert not is_mutable_version("^11.0")
    duplicates = DuplicateDeclarationRule().evaluate(context)
    assert duplicates.status is RuleResultStatus.MATCHED
    assert DependencyRulePack().supported_languages == (
        "java",
        "python",
        "php",
        "csharp",
    )


def test_conflicting_exact_versions_same_context_only() -> None:
    a = _decl(evidence_id="ev:c1", identity="com.example:lib", raw_version="1.0.0", line=1)
    b = _decl(evidence_id="ev:c2", identity="com.example:lib", raw_version="2.0.0", line=2)
    same = _decl(evidence_id="ev:c3", identity="com.example:lib", raw_version="1.0.0", line=3)
    other_profile = _decl(
        evidence_id="ev:c4",
        identity="com.example:lib",
        raw_version="3.0.0",
        profile="release",
        line=4,
    )
    managed = _decl(
        evidence_id="ev:c5",
        identity="com.example:lib",
        raw_version="9.0.0",
        is_management=True,
        kind=DependencyDeclarationKind.DEPENDENCY_MANAGEMENT,
        line=5,
    )
    other_module = _decl(
        evidence_id="ev:c6",
        identity="com.example:lib",
        raw_version="4.0.0",
        path="module-b/pom.xml",
        line=1,
    )
    result = ConflictingExactVersionsRule().evaluate(
        _context(_evidence((a, b, same, other_profile, managed, other_module)))
    )
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert result.matches[0].severity is RuleSeverity.HIGH
    assert "1.0.0" in result.matches[0].summary
    assert "2.0.0" in result.matches[0].summary
    assert len(result.matches[0].evidence) == 3  # a, b, same (1.0 and 2.0 participants)


def test_duplicate_declaration_group() -> None:
    a = _decl(evidence_id="ev:d1", identity="com.example:dup", raw_version="1.0.0", line=1)
    b = _decl(evidence_id="ev:d2", identity="com.example:dup", raw_version="1.0.0", line=2)
    different = _decl(
        evidence_id="ev:d3", identity="com.example:dup", raw_version="2.0.0", line=3
    )
    result = DuplicateDeclarationRule().evaluate(_context(_evidence((a, b, different))))
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert result.matches[0].severity is RuleSeverity.LOW
    assert result.matches[0].confidence is MatchEvidenceConfidence.HIGH
    assert len(result.matches[0].evidence) == 2


def test_source_role_preserved_and_no_absolute_paths() -> None:
    test_decl = _decl(
        evidence_id="ev:t1",
        identity="com.example:test-only",
        path="tests/fixtures/pom.xml",
        raw_version="1.0.0-SNAPSHOT",
        classification=SourceClassification.TEST,
    )
    result = MutableVersionRule().evaluate(_context(_evidence((test_decl,))))
    assert result.status is RuleResultStatus.MATCHED
    attrs = result.matches[0].evidence[0].attributes
    assert attrs["classification"] == "test"
    assert not str(result.matches[0].evidence[0].safe_location).startswith("/")


def test_finding_mapper_category_and_deterministic_ids() -> None:
    conflict_a = _decl(
        evidence_id="ev:f1", identity="com.example:lib", raw_version="1.0.0", line=1
    )
    conflict_b = _decl(
        evidence_id="ev:f2", identity="com.example:lib", raw_version="2.0.0", line=2
    )
    evidence = _evidence((conflict_a, conflict_b))
    context = _context(evidence)
    registry = RuleRegistry()
    register_dependency_pack(registry, for_execution=True)
    facade = RuleExecutionFacade(shared_registry=registry)
    platform = facade.execute_shared(context)
    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.DEPENDENCY
        for record in platform.records
    }
    findings = mapper.map_matches(platform.matches, category_by_rule=category_by_rule)
    assert findings
    assert all(item.category is FindingCategory.DEPENDENCY for item in findings)
    again = mapper.map_matches(platform.matches, category_by_rule=category_by_rule)
    assert [item.id for item in findings] == [item.id for item in again]
    assert all("/Users/" not in item.id for item in findings)


def test_discovery_registers_dependency_pack(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    service = create_rule_analysis_service(settings=settings)
    ids = {str(rule.metadata.rule_id) for rule in service.registry.list_rules()}
    assert HYGIENE_RULE_IDS[0] in ids


def test_per_rule_disable(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.dependency]
        enabled = true

        [rules.dependency.mutable_version]
        enabled = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    registry = RuleRegistry()
    register_dependency_pack(registry, settings=settings.rules, for_execution=True)
    ids = {str(rule.metadata.rule_id) for rule in registry.list_rules()}
    assert RULE_MUTABLE_VERSION not in ids
    assert RULE_UNRESOLVED_VERSION in ids
    assert RULE_UNBOUNDED_REQUIREMENT in ids
    assert RULE_CONFLICTING_EXACT_VERSIONS in ids
    assert RULE_DUPLICATE_DECLARATION in ids
