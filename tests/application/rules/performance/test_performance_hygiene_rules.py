"""Performance Hygiene SharedRule tests (Phase 4.9.3)."""

from __future__ import annotations

import random

from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.performance.helpers import (
    active_families,
    evidence_is_usable,
)
from codestrata.application.rules.performance.pack import PerformanceRulePack
from codestrata.application.rules.performance.pack import (
    performance_rules as load_performance_rules,
)
from codestrata.application.rules.performance.registration import register_performance_pack
from codestrata.application.rules.performance.rules import (
    BlockingSleepDetectedRule,
    BroadFoundationsRule,
    CachingDetectedRule,
    ConcurrencyDetectedRule,
    ConcurrencyWithoutConfigRule,
    ConfigControlsDetectedRule,
    DataAccessDetectedRule,
    DataAccessWithoutBatchingRule,
    DataWithoutCachingRule,
    ExecutorConfigDetectedRule,
    FrontendBundleDetectedRule,
    FrontendLazyDetectedRule,
    FrontendLimitedRule,
    LimitedControlsRule,
    MultipleDataAccessDetectedRule,
    ObservabilityDetectedRule,
    ResourceManagementDetectedRule,
    ResourcesWithoutManagementRule,
    SyncIoDetectedRule,
    WithoutObservabilityRule,
)
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config import load_settings
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_performance.enums import (
    EvidenceConfirmationLevel,
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceEvidenceFamily,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.models import (
    AggregatedRepositoryPerformanceEvidence,
    PerformanceBlockingFactEvidence,
    PerformanceCachingFactEvidence,
    PerformanceConcurrencyFactEvidence,
    PerformanceConfigurationFactEvidence,
    PerformanceDataAccessFactEvidence,
    PerformanceFileCandidateEvidence,
    PerformanceFrontendFactEvidence,
    PerformanceObservabilityFactEvidence,
    PerformanceResourceFactEvidence,
    RepositoryPerformanceEvidenceCoverage,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.performance.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    PERFORMANCE_RULE_IDS,
    RULE_ALIAS_TO_ID,
    RULE_DATA_ACCESS,
    RULE_LIMITED_CONTROLS,
)
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


def _data(
    *,
    kind: PerformanceDataAccessKind = PerformanceDataAccessKind.JPA,
    path: str = "src/Repo.java",
    evidence_id: str | None = None,
) -> PerformanceDataAccessFactEvidence:
    return PerformanceDataAccessFactEvidence(
        evidence_id=evidence_id or f"data:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _block(
    *,
    kind: PerformanceBlockingKind = PerformanceBlockingKind.THREAD_SLEEP,
    path: str = "src/Wait.java",
    evidence_id: str | None = None,
) -> PerformanceBlockingFactEvidence:
    return PerformanceBlockingFactEvidence(
        evidence_id=evidence_id or f"block:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _cache(
    *,
    kind: PerformanceCachingKind = PerformanceCachingKind.SPRING_CACHE,
    path: str = "src/Cache.java",
    evidence_id: str | None = None,
) -> PerformanceCachingFactEvidence:
    return PerformanceCachingFactEvidence(
        evidence_id=evidence_id or f"cache:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _conc(
    *,
    kind: PerformanceConcurrencyKind = PerformanceConcurrencyKind.COMPLETABLE_FUTURE,
    path: str = "src/Async.java",
    evidence_id: str | None = None,
) -> PerformanceConcurrencyFactEvidence:
    return PerformanceConcurrencyFactEvidence(
        evidence_id=evidence_id or f"conc:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _resource(
    *,
    kind: PerformanceResourceKind = PerformanceResourceKind.HIKARICP,
    path: str = "src/Pool.java",
    evidence_id: str | None = None,
) -> PerformanceResourceFactEvidence:
    return PerformanceResourceFactEvidence(
        evidence_id=evidence_id or f"res:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _frontend(
    *,
    kind: PerformanceFrontendKind = PerformanceFrontendKind.WEBPACK,
    path: str = "webpack.config.js",
    evidence_id: str | None = None,
) -> PerformanceFrontendFactEvidence:
    return PerformanceFrontendFactEvidence(
        evidence_id=evidence_id or f"fe:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _obs(
    *,
    kind: PerformanceObservabilityKind = PerformanceObservabilityKind.MICROMETER,
    path: str = "src/Metrics.java",
    evidence_id: str | None = None,
) -> PerformanceObservabilityFactEvidence:
    return PerformanceObservabilityFactEvidence(
        evidence_id=evidence_id or f"obs:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _config(
    *,
    kind: PerformanceConfigurationKind = PerformanceConfigurationKind.THREAD_POOL,
    path: str = "application.yml",
    evidence_id: str | None = None,
) -> PerformanceConfigurationFactEvidence:
    return PerformanceConfigurationFactEvidence(
        evidence_id=evidence_id or f"cfg:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _candidate(
    *,
    path: str = "marker.txt",
    family: PerformanceEvidenceFamily = PerformanceEvidenceFamily.CACHING,
) -> PerformanceFileCandidateEvidence:
    return PerformanceFileCandidateEvidence(
        evidence_id=f"cand:{path}",
        path=path,
        family=family,
        confirmation_level=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        provenance=_prov(),
    )


def _bundle(
    *,
    data: tuple[PerformanceDataAccessFactEvidence, ...] = (),
    blocking: tuple[PerformanceBlockingFactEvidence, ...] = (),
    caching: tuple[PerformanceCachingFactEvidence, ...] = (),
    concurrency: tuple[PerformanceConcurrencyFactEvidence, ...] = (),
    resource: tuple[PerformanceResourceFactEvidence, ...] = (),
    frontend: tuple[PerformanceFrontendFactEvidence, ...] = (),
    obs: tuple[PerformanceObservabilityFactEvidence, ...] = (),
    config: tuple[PerformanceConfigurationFactEvidence, ...] = (),
    candidates: tuple[PerformanceFileCandidateEvidence, ...] = (),
    status: RepositoryPerformanceParseStatus = RepositoryPerformanceParseStatus.SUCCEEDED,
) -> AggregatedRepositoryPerformanceEvidence:
    technologies = sorted(
        {
            *(item.kind.value for item in data),
            *(item.kind.value for item in blocking),
            *(item.kind.value for item in caching),
            *(item.kind.value for item in concurrency),
            *(item.kind.value for item in resource),
            *(item.kind.value for item in frontend),
            *(item.kind.value for item in obs),
            *(item.kind.value for item in config),
        }
    )
    total = (
        len(data)
        + len(blocking)
        + len(caching)
        + len(concurrency)
        + len(resource)
        + len(frontend)
        + len(obs)
        + len(config)
        + len(candidates)
    )
    return AggregatedRepositoryPerformanceEvidence(
        repository_id="fixture",
        status=status,
        file_candidates=candidates,
        data_access_facts=data,
        blocking_operations_facts=blocking,
        caching_facts=caching,
        concurrency_async_facts=concurrency,
        resource_management_facts=resource,
        frontend_performance_facts=frontend,
        observability_profiling_facts=obs,
        configuration_controls_facts=config,
        coverage=RepositoryPerformanceEvidenceCoverage(
            candidate_files_discovered=max(1, total) if total else 0,
            candidate_files_inspected=1 if total else 0,
            data_access_facts=len(data),
            blocking_operations_facts=len(blocking),
            caching_facts=len(caching),
            concurrency_async_facts=len(concurrency),
            resource_management_facts=len(resource),
            frontend_performance_facts=len(frontend),
            observability_profiling_facts=len(obs),
            configuration_controls_facts=len(config),
            technologies_represented=tuple(technologies),
        ),
        evidence_fingerprint="deadbeef",
    )


def _context(
    evidence: AggregatedRepositoryPerformanceEvidence | None,
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("java",)),
        repository_performance_evidence=evidence,
    )


def test_pack_registration_and_catalog() -> None:
    registry = RuleRegistry()
    pack = register_performance_pack(registry)
    assert pack.pack_id == PACK_ID
    assert len(load_performance_rules()) == 20
    assert len(load_performance_rules()) == len(HYGIENE_RULE_IDS)
    assert PERFORMANCE_RULE_IDS == HYGIENE_RULE_IDS
    assert DEFERRED_RULE_IDS == ()
    assert registry.size == len(HYGIENE_RULE_IDS)
    rule_ids = [str(rule.metadata.rule_id) for rule in load_performance_rules()]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids) == set(HYGIENE_RULE_IDS)
    assert RULE_ALIAS_TO_ID["PERF-001"] == RULE_DATA_ACCESS
    assert RULE_ALIAS_TO_ID["PERF-072"] == RULE_LIMITED_CONTROLS
    assert PerformanceRulePack().included_rule_ids == HYGIENE_RULE_IDS

    mapper = RuleFindingMapper()
    evidence = _bundle(data=(_data(),))
    context = _context(evidence)
    matches = []
    for rule in load_performance_rules():
        if rule.evaluate_applicability(context).is_applicable:
            matches.extend(rule.evaluate(context).matches)
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.PERFORMANCE for rid in HYGIENE_RULE_IDS},
    )
    assert findings
    assert all(item.category is FindingCategory.PERFORMANCE for item in findings)
    assert all(
        item.severity in {FindingSeverity.INFORMATIONAL, FindingSeverity.LOW} for item in findings
    )


def test_rules_performance_gate_defaults(tmp_path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.performance.enabled is False
    assert settings.rules.performance.perf_001.enabled is True
    assert settings.analysis.performance.enabled is False

    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.performance]
        enabled = true
        """,
        encoding="utf-8",
    )
    enabled = load_settings(config)
    assert enabled.rules.performance.enabled is True
    assert enabled.analysis.performance.enabled is False


def test_unusable_and_empty_evidence_not_applicable() -> None:
    rule = DataAccessDetectedRule()
    assert not rule.evaluate_applicability(_context(None)).is_applicable

    insufficient = _bundle(
        data=(_data(),),
        status=RepositoryPerformanceParseStatus.INSUFFICIENT_EVIDENCE,
    )
    assert not evidence_is_usable(insufficient)
    assert not rule.evaluate_applicability(_context(insufficient)).is_applicable

    empty = _bundle()
    assert not evidence_is_usable(empty)
    assert not rule.evaluate_applicability(_context(empty)).is_applicable
    assert not DataWithoutCachingRule().evaluate_applicability(_context(empty)).is_applicable


def test_perf001_data_access() -> None:
    rule = DataAccessDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(data=(_data(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL
    assert "jpa" in result.matches[0].summary


def test_perf002_multiple_data_access() -> None:
    rule = MultipleDataAccessDetectedRule()
    assert rule.evaluate(_context(_bundle(data=(_data(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(
        _context(
            _bundle(
                data=(
                    _data(kind=PerformanceDataAccessKind.JPA),
                    _data(kind=PerformanceDataAccessKind.HIBERNATE, path="h.java"),
                )
            )
        )
    )
    assert result.status is RuleResultStatus.MATCHED
    assert "hibernate" in result.matches[0].summary


def test_perf003_data_without_batching_suppressed() -> None:
    rule = DataAccessWithoutBatchingRule()
    gap = _bundle(data=(_data(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW

    with_controls = _bundle(
        data=(_data(),),
        config=(_config(kind=PerformanceConfigurationKind.DATASOURCE_CONFIG),),
    )
    assert rule.evaluate(_context(with_controls)).status is RuleResultStatus.NOT_MATCHED


def test_perf010_blocking_sleep() -> None:
    rule = BlockingSleepDetectedRule()
    assert (
        rule.evaluate(
            _context(_bundle(blocking=(_block(kind=PerformanceBlockingKind.SYNC_HTTP_CLIENT),)))
        ).status
        is RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(blocking=(_block(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_perf011_sync_io() -> None:
    rule = SyncIoDetectedRule()
    assert rule.evaluate(_context(_bundle(blocking=(_block(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(
        _context(_bundle(blocking=(_block(kind=PerformanceBlockingKind.SYNC_HTTP_CLIENT),)))
    )
    assert result.status is RuleResultStatus.MATCHED


def test_perf020_caching() -> None:
    rule = CachingDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(caching=(_cache(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_perf021_data_without_caching_suppressed() -> None:
    rule = DataWithoutCachingRule()
    gap = _bundle(data=(_data(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW

    with_cache = _bundle(data=(_data(),), caching=(_cache(),))
    assert rule.evaluate(_context(with_cache)).status is RuleResultStatus.NOT_MATCHED


def test_perf030_concurrency() -> None:
    rule = ConcurrencyDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(concurrency=(_conc(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_perf031_executor_config() -> None:
    rule = ExecutorConfigDetectedRule()
    assert rule.evaluate(_context(_bundle(concurrency=(_conc(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    from_exec = rule.evaluate(
        _context(
            _bundle(
                concurrency=(_conc(kind=PerformanceConcurrencyKind.EXECUTOR_SERVICE),),
            )
        )
    )
    assert from_exec.status is RuleResultStatus.MATCHED
    from_cfg = rule.evaluate(
        _context(_bundle(config=(_config(kind=PerformanceConfigurationKind.THREAD_POOL),)))
    )
    assert from_cfg.status is RuleResultStatus.MATCHED


def test_perf032_concurrency_without_config_suppressed() -> None:
    rule = ConcurrencyWithoutConfigRule()
    gap = _bundle(concurrency=(_conc(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW

    with_cfg = _bundle(
        concurrency=(_conc(),),
        config=(_config(kind=PerformanceConfigurationKind.EXECUTOR_CONFIG),),
    )
    assert rule.evaluate(_context(with_cfg)).status is RuleResultStatus.NOT_MATCHED


def test_perf040_resource_mgmt() -> None:
    rule = ResourceManagementDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(resource=(_resource(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_perf041_resources_without_mgmt_suppressed() -> None:
    rule = ResourcesWithoutManagementRule()
    gap = _bundle(data=(_data(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW

    with_res = _bundle(data=(_data(),), resource=(_resource(),))
    assert rule.evaluate(_context(with_res)).status is RuleResultStatus.NOT_MATCHED


def test_perf050_frontend_bundle() -> None:
    rule = FrontendBundleDetectedRule()
    assert (
        rule.evaluate(
            _context(_bundle(frontend=(_frontend(kind=PerformanceFrontendKind.LAZY_LOADING),)))
        ).status
        is RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(frontend=(_frontend(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_perf051_frontend_lazy() -> None:
    rule = FrontendLazyDetectedRule()
    assert rule.evaluate(_context(_bundle(frontend=(_frontend(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(
        _context(_bundle(frontend=(_frontend(kind=PerformanceFrontendKind.CODE_SPLITTING),)))
    )
    assert result.status is RuleResultStatus.MATCHED


def test_perf052_frontend_limited_suppressed() -> None:
    rule = FrontendLimitedRule()
    # Current taxonomy: every known frontend kind is bundle or lazy, so match
    # requires a future kind; verify suppression by 050/051 and empty frontend.
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    assert rule.evaluate(_context(_bundle(frontend=(_frontend(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    assert (
        rule.evaluate(
            _context(_bundle(frontend=(_frontend(kind=PerformanceFrontendKind.LAZY_LOADING),)))
        ).status
        is RuleResultStatus.NOT_MATCHED
    )


def test_perf060_observability() -> None:
    rule = ObservabilityDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(obs=(_obs(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_perf061_without_observability_suppressed() -> None:
    rule = WithoutObservabilityRule()
    with_obs = _bundle(data=(_data(),), obs=(_obs(),))
    assert rule.evaluate(_context(with_obs)).status is RuleResultStatus.NOT_MATCHED

    config_only = _bundle(config=(_config(),))
    assert rule.evaluate(_context(config_only)).status is RuleResultStatus.NOT_MATCHED

    gap = _bundle(data=(_data(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_perf070_config_controls() -> None:
    rule = ConfigControlsDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(config=(_config(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_perf071_broad_foundations() -> None:
    rule = BroadFoundationsRule()
    two = _bundle(data=(_data(),), caching=(_cache(),))
    assert len(active_families(two)) == 2
    assert rule.evaluate(_context(two)).status is RuleResultStatus.NOT_MATCHED

    three = _bundle(data=(_data(),), caching=(_cache(),), concurrency=(_conc(),))
    assert len(active_families(three)) == 3
    result = rule.evaluate(_context(three))
    assert result.status is RuleResultStatus.MATCHED
    assert "does not establish that the repository is performant" in (
        result.matches[0].summary.lower()
    )


def test_perf072_limited_controls_suppressed() -> None:
    rule = LimitedControlsRule()
    broad = _bundle(data=(_data(),), caching=(_cache(),), concurrency=(_conc(),))
    assert rule.evaluate(_context(broad)).status is RuleResultStatus.NOT_MATCHED

    config_only = _bundle(config=(_config(),))
    assert rule.evaluate(_context(config_only)).status is RuleResultStatus.NOT_MATCHED

    limited = _bundle(data=(_data(),), caching=(_cache(),))
    result = rule.evaluate(_context(limited))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_determinism_stable_finding_ids() -> None:
    facts = [_data(path=f"repo_{i}.java", evidence_id=f"d{i}") for i in range(5)]
    shuffled = list(facts)
    random.Random(7).shuffle(shuffled)
    left = DataAccessDetectedRule().evaluate(_context(_bundle(data=tuple(facts))))
    right = DataAccessDetectedRule().evaluate(_context(_bundle(data=tuple(shuffled))))
    assert left.matches[0].subject_keys == right.matches[0].subject_keys

    mapper = RuleFindingMapper()
    findings_left = mapper.map_matches(
        left.matches,
        category_by_rule={RULE_DATA_ACCESS: RuleCategory.PERFORMANCE},
    )
    findings_right = mapper.map_matches(
        right.matches,
        category_by_rule={RULE_DATA_ACCESS: RuleCategory.PERFORMANCE},
    )
    assert findings_left[0].id == findings_right[0].id
    left_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_left])
    right_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_right])
    assert left_bytes == right_bytes


def test_no_remediation_or_advice() -> None:
    result = DataWithoutCachingRule().evaluate(_context(_bundle(data=(_data(),))))
    assert result.matches[0].remediation.startswith("Observation only:")
    text = dumps_stable_json([item.model_dump(mode="json") for item in result.matches])
    assert "modernize" not in text.lower()
    assert "bottleneck" not in text.lower()
    assert "is performant" not in text.lower()
    assert "is slow" not in text.lower()
    assert "/Users/" not in text
