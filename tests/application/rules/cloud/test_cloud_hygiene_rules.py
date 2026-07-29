"""Cloud Hygiene SharedRule tests (Phase 4.7.3)."""

from __future__ import annotations

import random

from codestrata.application.rules.cloud.helpers import (
    active_families,
    evidence_is_usable,
    known_platforms,
)
from codestrata.application.rules.cloud.pack import CloudRulePack
from codestrata.application.rules.cloud.pack import cloud_rules as load_cloud_rules
from codestrata.application.rules.cloud.registration import register_cloud_pack
from codestrata.application.rules.cloud.rules import (
    CloudDeploymentPipelineDetectedRule,
    CloudNativeRepositoryIndicatorsRule,
    CloudPlatformDetectedRule,
    ContainerizationDetectedRule,
    DeploymentWithoutPlatformRule,
    InfrastructureAsCodePresentRule,
    KubernetesDeploymentDetectedRule,
    ManagedCloudServicesDetectedRule,
    MultipleCloudProvidersRule,
    MultipleIaCTechnologiesRule,
    ServerlessDeploymentDetectedRule,
)
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config import load_settings
from codestrata.domain.cloud.ids import (
    CLOUD_RULE_IDS,
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    RULE_ALIAS_TO_ID,
    RULE_CONTAINERIZATION,
    RULE_DEPLOYMENT_WITHOUT_PLATFORM,
    RULE_MULTIPLE_PLATFORMS,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudIaCKind,
    CloudManagedServiceKind,
    CloudOrchestrationKind,
    CloudPlatformKind,
    CloudServerlessKind,
    EvidenceConfirmationLevel,
    RepositoryCloudParseStatus,
)
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
    CloudContainerFactEvidence,
    CloudDeploymentFactEvidence,
    CloudIaCFactEvidence,
    CloudManagedServiceFactEvidence,
    CloudOrchestrationFactEvidence,
    CloudPlatformFactEvidence,
    CloudServerlessFactEvidence,
    RepositoryCloudEvidenceCoverage,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus, RuleSeverity
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _platform(
    *,
    platform: CloudPlatformKind,
    path: str = "infra/main.tf",
    evidence_id: str | None = None,
    confirmation: EvidenceConfirmationLevel = (EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED),
) -> CloudPlatformFactEvidence:
    return CloudPlatformFactEvidence(
        evidence_id=evidence_id or f"plat:{platform.value}:{path}",
        platform=platform,
        path=path,
        confirmation_level=confirmation,
        provenance=_prov(),
    )


def _container(
    *,
    kind: CloudContainerKind = CloudContainerKind.DOCKER,
    path: str = "Dockerfile",
    evidence_id: str | None = None,
) -> CloudContainerFactEvidence:
    return CloudContainerFactEvidence(
        evidence_id=evidence_id or f"ctr:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _orchestration(
    *,
    kind: CloudOrchestrationKind = CloudOrchestrationKind.KUBERNETES,
    path: str = "k8s/deploy.yaml",
    evidence_id: str | None = None,
) -> CloudOrchestrationFactEvidence:
    return CloudOrchestrationFactEvidence(
        evidence_id=evidence_id or f"orch:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _iac(
    *,
    kind: CloudIaCKind = CloudIaCKind.TERRAFORM,
    path: str = "terraform/main.tf",
    evidence_id: str | None = None,
) -> CloudIaCFactEvidence:
    return CloudIaCFactEvidence(
        evidence_id=evidence_id or f"iac:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _serverless(
    *,
    kind: CloudServerlessKind = CloudServerlessKind.SERVERLESS_FRAMEWORK,
    path: str = "serverless.yml",
    evidence_id: str | None = None,
) -> CloudServerlessFactEvidence:
    return CloudServerlessFactEvidence(
        evidence_id=evidence_id or f"sls:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _managed(
    *,
    service: CloudManagedServiceKind = CloudManagedServiceKind.S3,
    path: str = "terraform/s3.tf",
    evidence_id: str | None = None,
) -> CloudManagedServiceFactEvidence:
    return CloudManagedServiceFactEvidence(
        evidence_id=evidence_id or f"ms:{service.value}:{path}",
        service=service,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _deployment(
    *,
    system: CloudDeploymentSystem = CloudDeploymentSystem.GITHUB_ACTIONS,
    path: str = ".github/workflows/deploy.yml",
    evidence_id: str | None = None,
) -> CloudDeploymentFactEvidence:
    return CloudDeploymentFactEvidence(
        evidence_id=evidence_id or f"dep:{system.value}:{path}",
        system=system,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _bundle(
    *,
    platforms: tuple[CloudPlatformFactEvidence, ...] = (),
    containers: tuple[CloudContainerFactEvidence, ...] = (),
    orchestration: tuple[CloudOrchestrationFactEvidence, ...] = (),
    iac: tuple[CloudIaCFactEvidence, ...] = (),
    serverless: tuple[CloudServerlessFactEvidence, ...] = (),
    managed: tuple[CloudManagedServiceFactEvidence, ...] = (),
    deployment: tuple[CloudDeploymentFactEvidence, ...] = (),
    status: RepositoryCloudParseStatus = RepositoryCloudParseStatus.SUCCEEDED,
) -> AggregatedRepositoryCloudEvidence:
    technologies = sorted(
        {
            *(item.platform.value for item in platforms),
            *(item.kind.value for item in containers),
            *(item.kind.value for item in orchestration),
            *(item.kind.value for item in iac),
            *(item.kind.value for item in serverless),
            *(item.service.value for item in managed),
            *(item.system.value for item in deployment),
        }
    )
    return AggregatedRepositoryCloudEvidence(
        repository_id="fixture",
        status=status,
        platform_facts=platforms,
        container_facts=containers,
        orchestration_facts=orchestration,
        iac_facts=iac,
        serverless_facts=serverless,
        managed_service_facts=managed,
        deployment_facts=deployment,
        coverage=RepositoryCloudEvidenceCoverage(
            candidate_files_discovered=max(
                1,
                len(platforms)
                + len(containers)
                + len(orchestration)
                + len(iac)
                + len(serverless)
                + len(managed)
                + len(deployment),
            ),
            candidate_files_inspected=1,
            platform_facts=len(platforms),
            container_facts=len(containers),
            orchestration_facts=len(orchestration),
            iac_facts=len(iac),
            serverless_facts=len(serverless),
            managed_service_facts=len(managed),
            deployment_facts=len(deployment),
            technologies_represented=tuple(technologies),
        ),
        evidence_fingerprint="deadbeef",
    )


def _context(
    evidence: AggregatedRepositoryCloudEvidence | None,
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        repository_cloud_evidence=evidence,
    )


def test_pack_registration_and_catalog() -> None:
    registry = RuleRegistry()
    pack = register_cloud_pack(registry)
    assert pack.pack_id == PACK_ID
    assert len(load_cloud_rules()) == 11
    assert len(load_cloud_rules()) == len(HYGIENE_RULE_IDS)
    assert CLOUD_RULE_IDS == HYGIENE_RULE_IDS
    assert DEFERRED_RULE_IDS == ()
    assert registry.size == len(HYGIENE_RULE_IDS)
    rule_ids = [str(rule.metadata.rule_id) for rule in load_cloud_rules()]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids) == set(HYGIENE_RULE_IDS)
    assert RULE_ALIAS_TO_ID["CLOUD-001"] == RULE_MULTIPLE_PLATFORMS
    assert RULE_ALIAS_TO_ID["CLOUD-061"] == RULE_DEPLOYMENT_WITHOUT_PLATFORM
    assert CloudRulePack().included_rule_ids == HYGIENE_RULE_IDS

    mapper = RuleFindingMapper()
    evidence = _bundle(containers=(_container(),))
    context = _context(evidence)
    matches = []
    for rule in load_cloud_rules():
        if rule.evaluate_applicability(context).is_applicable:
            matches.extend(rule.evaluate(context).matches)
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.CLOUD for rid in HYGIENE_RULE_IDS},
    )
    assert findings
    assert all(item.category is FindingCategory.CLOUD for item in findings)
    assert all(
        item.severity in {FindingSeverity.INFORMATIONAL, FindingSeverity.LOW} for item in findings
    )


def test_cloud001_multiple_platforms() -> None:
    rule = MultipleCloudProvidersRule()
    single = _bundle(platforms=(_platform(platform=CloudPlatformKind.AWS),))
    assert rule.evaluate(_context(single)).status is RuleResultStatus.NOT_MATCHED

    multi = _bundle(
        platforms=(
            _platform(platform=CloudPlatformKind.AWS, path="aws.tf"),
            _platform(platform=CloudPlatformKind.AZURE, path="azure.bicep"),
        )
    )
    result = rule.evaluate(_context(multi))
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert result.matches[0].severity is RuleSeverity.LOW
    assert "aws,azure" in result.matches[0].summary


def test_cloud002_single_platform_suppressed_when_multiple() -> None:
    rule = CloudPlatformDetectedRule()
    empty = rule.evaluate(_context(_bundle()))
    assert empty.status is RuleResultStatus.NOT_MATCHED

    single = _bundle(platforms=(_platform(platform=CloudPlatformKind.GCP),))
    result = rule.evaluate(_context(single))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL
    assert "gcp" in result.matches[0].summary

    multi = _bundle(
        platforms=(
            _platform(platform=CloudPlatformKind.AWS),
            _platform(platform=CloudPlatformKind.GCP, path="gcp.tf"),
        )
    )
    assert rule.evaluate(_context(multi)).status is RuleResultStatus.NOT_MATCHED


def test_cloud010_containerization() -> None:
    rule = ContainerizationDetectedRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    result = rule.evaluate(
        _context(
            _bundle(
                containers=(
                    _container(kind=CloudContainerKind.DOCKER),
                    _container(
                        kind=CloudContainerKind.DOCKER_COMPOSE,
                        path="docker-compose.yml",
                    ),
                )
            )
        )
    )
    assert result.status is RuleResultStatus.MATCHED
    assert "docker" in result.matches[0].summary


def test_cloud011_kubernetes() -> None:
    rule = KubernetesDeploymentDetectedRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    one = rule.evaluate(_context(_bundle(orchestration=(_orchestration(),))))
    assert one.status is RuleResultStatus.MATCHED
    assert one.matches[0].severity is RuleSeverity.INFORMATIONAL

    multi = rule.evaluate(
        _context(
            _bundle(
                orchestration=(
                    _orchestration(kind=CloudOrchestrationKind.KUBERNETES),
                    _orchestration(kind=CloudOrchestrationKind.HELM, path="Chart.yaml"),
                )
            )
        )
    )
    assert multi.matches[0].severity is RuleSeverity.LOW


def test_cloud020_iac_present() -> None:
    rule = InfrastructureAsCodePresentRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    result = rule.evaluate(_context(_bundle(iac=(_iac(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_cloud021_multiple_iac() -> None:
    rule = MultipleIaCTechnologiesRule()
    one = _bundle(iac=(_iac(),))
    assert rule.evaluate(_context(one)).status is RuleResultStatus.NOT_MATCHED
    multi = _bundle(
        iac=(
            _iac(kind=CloudIaCKind.TERRAFORM),
            _iac(kind=CloudIaCKind.BICEP, path="main.bicep"),
        )
    )
    result = rule.evaluate(_context(multi))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_cloud030_serverless() -> None:
    rule = ServerlessDeploymentDetectedRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    result = rule.evaluate(_context(_bundle(serverless=(_serverless(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_cloud040_deployment_pipeline() -> None:
    rule = CloudDeploymentPipelineDetectedRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    result = rule.evaluate(_context(_bundle(deployment=(_deployment(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert "github_actions" in result.matches[0].summary


def test_cloud050_managed_services() -> None:
    rule = ManagedCloudServicesDetectedRule()
    assert rule.evaluate(_context(_bundle())).status is RuleResultStatus.NOT_MATCHED
    few = rule.evaluate(
        _context(
            _bundle(
                managed=(
                    _managed(service=CloudManagedServiceKind.S3),
                    _managed(
                        service=CloudManagedServiceKind.DYNAMODB,
                        path="ddb.tf",
                    ),
                )
            )
        )
    )
    assert few.matches[0].severity is RuleSeverity.INFORMATIONAL

    many = rule.evaluate(
        _context(
            _bundle(
                managed=(
                    _managed(service=CloudManagedServiceKind.S3),
                    _managed(service=CloudManagedServiceKind.DYNAMODB, path="ddb.tf"),
                    _managed(service=CloudManagedServiceKind.RDS, path="rds.tf"),
                )
            )
        )
    )
    assert many.matches[0].severity is RuleSeverity.LOW


def test_cloud060_cloud_native_indicators() -> None:
    rule = CloudNativeRepositoryIndicatorsRule()
    two = _bundle(
        containers=(_container(),),
        deployment=(_deployment(),),
    )
    assert len(active_families(two)) == 2
    assert rule.evaluate(_context(two)).status is RuleResultStatus.NOT_MATCHED

    three = _bundle(
        containers=(_container(),),
        orchestration=(_orchestration(),),
        deployment=(_deployment(),),
    )
    assert len(active_families(three)) == 3
    result = rule.evaluate(_context(three))
    assert result.status is RuleResultStatus.MATCHED
    assert "does not establish cloud readiness" in result.matches[0].summary.lower()


def test_cloud061_deployment_without_platform() -> None:
    rule = DeploymentWithoutPlatformRule()
    with_platform = _bundle(
        platforms=(_platform(platform=CloudPlatformKind.AWS),),
        containers=(_container(),),
    )
    assert known_platforms(with_platform)
    assert rule.evaluate(_context(with_platform)).status is RuleResultStatus.NOT_MATCHED

    no_assets = _bundle(platforms=())
    assert rule.evaluate(_context(no_assets)).status is RuleResultStatus.NOT_MATCHED

    assets = _bundle(containers=(_container(),), iac=(_iac(),))
    result = rule.evaluate(_context(assets))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_unusable_evidence_not_applicable() -> None:
    rule = ContainerizationDetectedRule()
    insufficient = _bundle(
        containers=(_container(),),
        status=RepositoryCloudParseStatus.INSUFFICIENT_EVIDENCE,
    )
    assert not evidence_is_usable(insufficient)
    assert not rule.evaluate_applicability(_context(insufficient)).is_applicable
    assert not rule.evaluate_applicability(_context(None)).is_applicable


def test_determinism_stable_finding_ids() -> None:
    facts = [_container(path=f"Dockerfile.{i}", evidence_id=f"c{i}") for i in range(5)]
    shuffled = list(facts)
    random.Random(7).shuffle(shuffled)
    left = ContainerizationDetectedRule().evaluate(_context(_bundle(containers=tuple(facts))))
    right = ContainerizationDetectedRule().evaluate(_context(_bundle(containers=tuple(shuffled))))
    assert left.matches[0].subject_keys == right.matches[0].subject_keys

    mapper = RuleFindingMapper()
    findings_left = mapper.map_matches(
        left.matches,
        category_by_rule={RULE_CONTAINERIZATION: RuleCategory.CLOUD},
    )
    findings_right = mapper.map_matches(
        right.matches,
        category_by_rule={RULE_CONTAINERIZATION: RuleCategory.CLOUD},
    )
    assert findings_left[0].id == findings_right[0].id
    left_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_left])
    right_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_right])
    assert left_bytes == right_bytes


def test_no_remediation_or_advice() -> None:
    result = MultipleCloudProvidersRule().evaluate(
        _context(
            _bundle(
                platforms=(
                    _platform(platform=CloudPlatformKind.AWS),
                    _platform(platform=CloudPlatformKind.AZURE, path="az.bicep"),
                )
            )
        )
    )
    assert result.matches[0].remediation.startswith("Observation only:")
    text = dumps_stable_json([item.model_dump(mode="json") for item in result.matches])
    assert "modernize" not in text.lower()
    assert "migrate to" not in text.lower()
    assert "/Users/" not in text


def test_rules_cloud_gate_defaults(tmp_path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.cloud.enabled is False
    assert settings.rules.cloud.cloud_001.enabled is True
