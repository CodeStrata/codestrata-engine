"""Performance Hygiene SharedRules (Phase 4.9.3).

Rules consume AggregatedRepositoryPerformanceEvidence only. They never re-read
repository files, invent performance scores, or claim bottlenecks.
"""

from __future__ import annotations

from codestrata.application.rules.performance.helpers import (
    PerformanceFact,
    _sorted_matches,
    active_families,
    confidence_from_levels,
    evidence_is_usable,
    evidence_summary,
    known_blocking_sleep_kinds,
    known_caching_kinds,
    known_concurrency_kinds,
    known_configuration_kinds,
    known_data_access_control_kinds,
    known_data_access_kinds,
    known_executor_concurrency_kinds,
    known_executor_config_kinds,
    known_frontend_bundle_kinds,
    known_frontend_kinds,
    known_frontend_lazy_kinds,
    known_observability_kinds,
    known_resource_kinds,
    known_sync_io_kinds,
    make_metadata,
    match,
    path_evidence_from_facts,
    performance_assets_present,
    repository_performance_evidence,
)
from codestrata.domain.evidence.repository_performance.enums import (
    PerformanceBlockingKind,
    PerformanceFrontendKind,
)
from codestrata.domain.performance.ids import (
    RULE_BLOCKING_SLEEP,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_CONFIG_CONTROLS,
    RULE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_EXECUTOR_CONFIG,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_LIMITED_CONTROLS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_OBSERVABILITY,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_SYNC_IO,
    RULE_WITHOUT_OBSERVABILITY,
)
from codestrata.domain.performance.taxonomy import PerformanceCategory
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleSeverity, RuleSkipReason
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult


def _performance_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = repository_performance_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Repository performance evidence unavailable",
        )
    if not evidence_is_usable(evidence):
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=f"Repository performance evidence status is {evidence.status.value}",
        )
    return RuleApplicability.applicable()


class DataAccessDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DATA_ACCESS,
            title="Data access framework or repository patterns detected",
            description=(
                "Detects repository-observable data access framework or repository "
                "patterns. Does not claim inefficient queries or performance risk."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_data_access_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.data_access_facts if item.kind in kinds]
        category = PerformanceCategory.INEFFICIENT_DATA_ACCESS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DATA_ACCESS,
                message=f"data_access_kinds={joined}",
                performance_category=category,
                attributes={"data_access_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="data_access_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DATA_ACCESS,
                    title="Data access framework or repository patterns detected",
                    summary=(
                        "Repository performance evidence includes data access "
                        f"framework or repository patterns ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_DATA_ACCESS, "data_access", joined),
                )
            ]
        )


class MultipleDataAccessDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_MULTIPLE_DATA_ACCESS,
            title="Multiple data access framework kinds detected",
            description=(
                "Detects two or more distinct known data access kinds. Does not "
                "claim conflicting stacks or performance impact."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_data_access_kinds(evidence)
        if len(kinds) < 2:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.data_access_facts if item.kind in kinds]
        category = PerformanceCategory.INEFFICIENT_DATA_ACCESS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_MULTIPLE_DATA_ACCESS,
                message=f"data_access_kinds={joined}; kind_count={len(kinds)}",
                performance_category=category,
                attributes={
                    "data_access_kinds": joined,
                    "data_access_kind_count": str(len(kinds)),
                },
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="data_access_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_MULTIPLE_DATA_ACCESS,
                    title="Multiple data access framework kinds detected",
                    summary=(
                        "Repository performance evidence includes multiple distinct "
                        f"data access kinds ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_MULTIPLE_DATA_ACCESS, "multiple_data_access", joined),
                )
            ]
        )


class DataAccessWithoutBatchingRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DATA_ACCESS_WITHOUT_BATCHING,
            title="Data access without observable batching or timeout controls",
            description=(
                "Observes known data access facts when no datasource or timeout "
                "configuration kinds are present. Does not claim missing batching."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if not known_data_access_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if known_data_access_control_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        kinds = known_data_access_kinds(evidence)
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.data_access_facts if item.kind in kinds]
        category = PerformanceCategory.BATCHING_PAGINATION
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DATA_ACCESS_WITHOUT_BATCHING,
                message=f"data_access_kinds={joined}; data_access_control_kinds=0",
                performance_category=category,
                attributes={
                    "data_access_kinds": joined,
                    "data_access_control_kinds": "",
                },
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="data_access_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DATA_ACCESS_WITHOUT_BATCHING,
                    title="Data access without observable batching or timeout controls",
                    summary=(
                        "Repository performance evidence includes data access "
                        "patterns without known datasource or timeout configuration "
                        "signals among inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_DATA_ACCESS_WITHOUT_BATCHING,
                        "data_without_batching",
                        joined,
                    ),
                )
            ]
        )


class BlockingSleepDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_BLOCKING_SLEEP,
            title="Thread sleep signals detected",
            description=(
                "Detects thread-sleep blocking operation signals. Does not claim "
                "a latency bottleneck."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_blocking_sleep_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [
            item
            for item in evidence.blocking_operations_facts
            if item.kind is PerformanceBlockingKind.THREAD_SLEEP
        ]
        category = PerformanceCategory.BLOCKING_OPERATIONS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_BLOCKING_SLEEP,
                message=f"blocking_sleep_kinds={joined}",
                performance_category=category,
                attributes={"blocking_sleep_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="blocking_sleep_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_BLOCKING_SLEEP,
                    title="Thread sleep signals detected",
                    summary=(
                        f"Repository performance evidence includes thread sleep signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_BLOCKING_SLEEP, "blocking_sleep", joined),
                )
            ]
        )


class SyncIoDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_SYNC_IO,
            title="Synchronous I/O signals detected",
            description=(
                "Detects sync HTTP client, blocking DB call, or blocking file I/O "
                "signals. Does not claim the repository is slow."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_sync_io_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.blocking_operations_facts if item.kind in kinds]
        category = PerformanceCategory.BLOCKING_OPERATIONS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_SYNC_IO,
                message=f"sync_io_kinds={joined}",
                performance_category=category,
                attributes={"sync_io_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="sync_io_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_SYNC_IO,
                    title="Synchronous I/O signals detected",
                    summary=(
                        "Repository performance evidence includes synchronous I/O "
                        f"signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_SYNC_IO, "sync_io", joined),
                )
            ]
        )


class CachingDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CACHING,
            title="Caching signals detected",
            description=(
                "Detects repository-observable caching framework or cache manager signals."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_caching_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.caching_facts if item.kind in kinds]
        category = PerformanceCategory.CACHING
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CACHING,
                message=f"caching_kinds={joined}",
                performance_category=category,
                attributes={"caching_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="caching_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CACHING,
                    title="Caching signals detected",
                    summary=(
                        f"Repository performance evidence includes caching signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_CACHING, "caching", joined),
                )
            ]
        )


class DataWithoutCachingRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DATA_WITHOUT_CACHING,
            title="Data access without observable caching signals",
            description=(
                "Observes known data access facts when no known caching facts are "
                "present. Suppressed when caching signals match."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if known_caching_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if not known_data_access_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        kinds = known_data_access_kinds(evidence)
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.data_access_facts if item.kind in kinds]
        category = PerformanceCategory.CACHING
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DATA_WITHOUT_CACHING,
                message=f"data_access_kinds={joined}; caching_kinds=0",
                performance_category=category,
                attributes={"data_access_kinds": joined, "caching_kinds": ""},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="data_access_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DATA_WITHOUT_CACHING,
                    title="Data access without observable caching signals",
                    summary=(
                        "Repository performance evidence includes data access "
                        "patterns without known caching signals among inspected "
                        "candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_DATA_WITHOUT_CACHING, "data_without_caching", joined),
                )
            ]
        )


class ConcurrencyDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CONCURRENCY,
            title="Concurrency or async signals detected",
            description=("Detects repository-observable concurrency or async execution signals."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_concurrency_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.concurrency_async_facts if item.kind in kinds]
        category = PerformanceCategory.CONCURRENCY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CONCURRENCY,
                message=f"concurrency_kinds={joined}",
                performance_category=category,
                attributes={"concurrency_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="concurrency_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CONCURRENCY,
                    title="Concurrency or async signals detected",
                    summary=(
                        "Repository performance evidence includes concurrency or "
                        f"async signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_CONCURRENCY, "concurrency", joined),
                )
            ]
        )


class ExecutorConfigDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_EXECUTOR_CONFIG,
            title="Executor concurrency or executor configuration detected",
            description=(
                "Detects executor-service/virtual-thread concurrency or "
                "thread-pool/executor configuration signals."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        exec_kinds = known_executor_concurrency_kinds(evidence)
        config_kinds = known_executor_config_kinds(evidence)
        if not exec_kinds and not config_kinds:
            return SharedRuleEvaluationResult.not_matched()
        exec_joined = ",".join(item.value for item in exec_kinds)
        config_joined = ",".join(item.value for item in config_kinds)
        facts: list[PerformanceFact] = [
            *[item for item in evidence.concurrency_async_facts if item.kind in exec_kinds],
            *[item for item in evidence.configuration_controls_facts if item.kind in config_kinds],
        ]
        category = PerformanceCategory.CONCURRENCY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_EXECUTOR_CONFIG,
                message=(
                    f"executor_concurrency_kinds={exec_joined}; "
                    f"executor_config_kinds={config_joined}"
                ),
                performance_category=category,
                attributes={
                    "executor_concurrency_kinds": exec_joined,
                    "executor_config_kinds": config_joined,
                },
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="executor_config_fact"
            ),
        ]
        subject = exec_joined or config_joined
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_EXECUTOR_CONFIG,
                    title="Executor concurrency or executor configuration detected",
                    summary=(
                        "Repository performance evidence includes executor "
                        "concurrency or executor configuration signals "
                        f"(concurrency={exec_joined or 'none'}; "
                        f"config={config_joined or 'none'})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_EXECUTOR_CONFIG, "executor_config", subject),
                )
            ]
        )


class ConcurrencyWithoutConfigRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CONCURRENCY_WITHOUT_CONFIG,
            title="Concurrency without observable executor configuration",
            description=(
                "Observes known concurrency facts when no thread-pool or executor "
                "configuration kinds are present."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if not known_concurrency_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if known_executor_config_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        kinds = known_concurrency_kinds(evidence)
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.concurrency_async_facts if item.kind in kinds]
        category = PerformanceCategory.CONCURRENCY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CONCURRENCY_WITHOUT_CONFIG,
                message=f"concurrency_kinds={joined}; executor_config_kinds=0",
                performance_category=category,
                attributes={"concurrency_kinds": joined, "executor_config_kinds": ""},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="concurrency_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CONCURRENCY_WITHOUT_CONFIG,
                    title="Concurrency without observable executor configuration",
                    summary=(
                        "Repository performance evidence includes concurrency "
                        "signals without known thread-pool or executor configuration "
                        "among inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_CONCURRENCY_WITHOUT_CONFIG,
                        "concurrency_without_config",
                        joined,
                    ),
                )
            ]
        )


class ResourceManagementDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_RESOURCE_MGMT,
            title="Resource management signals detected",
            description=("Detects connection pool or resource-lifecycle management signals."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_resource_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.resource_management_facts if item.kind in kinds]
        category = PerformanceCategory.RESOURCE_MANAGEMENT
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_RESOURCE_MGMT,
                message=f"resource_kinds={joined}",
                performance_category=category,
                attributes={"resource_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="resource_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_RESOURCE_MGMT,
                    title="Resource management signals detected",
                    summary=(
                        "Repository performance evidence includes resource "
                        f"management signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_RESOURCE_MGMT, "resource_management", joined),
                )
            ]
        )


class ResourcesWithoutManagementRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_RESOURCES_WITHOUT_MGMT,
            title="Data or blocking signals without resource management evidence",
            description=(
                "Observes data access or blocking sleep/sync I/O when no known "
                "resource management facts are present. Suppressed when resource "
                "management matches."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if known_resource_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        has_data = bool(known_data_access_kinds(evidence))
        has_blocking = bool(known_blocking_sleep_kinds(evidence) or known_sync_io_kinds(evidence))
        if not has_data and not has_blocking:
            return SharedRuleEvaluationResult.not_matched()
        facts: list[PerformanceFact] = [
            *[item for item in evidence.data_access_facts if item.kind.value != "unknown"],
            *[
                item
                for item in evidence.blocking_operations_facts
                if item.kind is PerformanceBlockingKind.THREAD_SLEEP
                or item.kind.value in {"sync_http_client", "blocking_db_call", "blocking_file_io"}
            ],
        ]
        category = PerformanceCategory.RESOURCE_MANAGEMENT
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_RESOURCES_WITHOUT_MGMT,
                message="data_or_blocking=true; resource_kinds=0",
                performance_category=category,
                attributes={"data_or_blocking": "true", "resource_kinds": ""},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="resource_gap_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_RESOURCES_WITHOUT_MGMT,
                    title="Data or blocking signals without resource management evidence",
                    summary=(
                        "Repository performance evidence includes data access or "
                        "blocking signals without known resource management facts "
                        "among inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_RESOURCES_WITHOUT_MGMT,
                        "resources_without_mgmt",
                        "0",
                    ),
                )
            ]
        )


class FrontendBundleDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_FRONTEND_BUNDLE,
            title="Frontend bundle tooling signals detected",
            description=("Detects webpack, Vite, or bundle configuration frontend signals."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_frontend_bundle_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.frontend_performance_facts if item.kind in kinds]
        category = PerformanceCategory.FRONTEND_RENDERING_BUNDLE
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_FRONTEND_BUNDLE,
                message=f"frontend_bundle_kinds={joined}",
                performance_category=category,
                attributes={"frontend_bundle_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="frontend_bundle_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_FRONTEND_BUNDLE,
                    title="Frontend bundle tooling signals detected",
                    summary=(
                        "Repository performance evidence includes frontend bundle "
                        f"tooling signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_FRONTEND_BUNDLE, "frontend_bundle", joined),
                )
            ]
        )


class FrontendLazyDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_FRONTEND_LAZY,
            title="Frontend lazy loading or code splitting detected",
            description=("Detects lazy loading or code splitting frontend signals."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_frontend_lazy_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.frontend_performance_facts if item.kind in kinds]
        category = PerformanceCategory.FRONTEND_RENDERING_BUNDLE
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_FRONTEND_LAZY,
                message=f"frontend_lazy_kinds={joined}",
                performance_category=category,
                attributes={"frontend_lazy_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="frontend_lazy_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_FRONTEND_LAZY,
                    title="Frontend lazy loading or code splitting detected",
                    summary=(
                        "Repository performance evidence includes frontend lazy "
                        f"loading or code splitting signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_FRONTEND_LAZY, "frontend_lazy", joined),
                )
            ]
        )


class FrontendLimitedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_FRONTEND_LIMITED,
            title="Limited frontend bundle or lazy-loading evidence",
            description=(
                "Observes known frontend facts without bundle tooling or lazy/"
                "code-splitting kinds. Suppressed when those detections match."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if known_frontend_bundle_kinds(evidence) or known_frontend_lazy_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if not known_frontend_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        kinds = known_frontend_kinds(evidence)
        joined = ",".join(item.value for item in kinds)
        facts = [
            item
            for item in evidence.frontend_performance_facts
            if item.kind is not PerformanceFrontendKind.UNKNOWN
        ]
        category = PerformanceCategory.FRONTEND_RENDERING_BUNDLE
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_FRONTEND_LIMITED,
                message=f"frontend_kinds={joined}; bundle=0; lazy=0",
                performance_category=category,
                attributes={
                    "frontend_kinds": joined,
                    "frontend_bundle_kinds": "",
                    "frontend_lazy_kinds": "",
                },
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="frontend_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_FRONTEND_LIMITED,
                    title="Limited frontend bundle or lazy-loading evidence",
                    summary=(
                        "Repository performance evidence includes frontend signals "
                        "without known bundle tooling or lazy-loading kinds among "
                        "inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_FRONTEND_LIMITED, "frontend_limited", joined),
                )
            ]
        )


class ObservabilityDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_OBSERVABILITY,
            title="Observability or profiling signals detected",
            description=("Detects metrics, tracing, profiling, or related observability signals."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_observability_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.observability_profiling_facts if item.kind in kinds]
        category = PerformanceCategory.OBSERVABILITY_PROFILING
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_OBSERVABILITY,
                message=f"observability_kinds={joined}",
                performance_category=category,
                attributes={"observability_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="observability_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_OBSERVABILITY,
                    title="Observability or profiling signals detected",
                    summary=(
                        "Repository performance evidence includes observability or "
                        f"profiling signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_OBSERVABILITY, "observability", joined),
                )
            ]
        )


class WithoutObservabilityRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_WITHOUT_OBSERVABILITY,
            title="Performance assets without observability evidence",
            description=(
                "Observes data access, blocking, caching, concurrency, resource, or "
                "frontend signals when no known observability facts are present."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        if known_observability_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        has_non_obs = bool(
            known_data_access_kinds(evidence)
            or known_blocking_sleep_kinds(evidence)
            or known_sync_io_kinds(evidence)
            or known_caching_kinds(evidence)
            or known_concurrency_kinds(evidence)
            or known_resource_kinds(evidence)
            or known_frontend_kinds(evidence)
        )
        if not has_non_obs:
            return SharedRuleEvaluationResult.not_matched()
        facts: list[PerformanceFact] = [
            *[item for item in evidence.data_access_facts if item.kind.value != "unknown"],
            *[item for item in evidence.blocking_operations_facts if item.kind.value != "unknown"],
            *[item for item in evidence.caching_facts if item.kind.value != "unknown"],
            *[item for item in evidence.concurrency_async_facts if item.kind.value != "unknown"],
            *[item for item in evidence.resource_management_facts if item.kind.value != "unknown"],
            *[item for item in evidence.frontend_performance_facts if item.kind.value != "unknown"],
        ]
        category = PerformanceCategory.OBSERVABILITY_PROFILING
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_WITHOUT_OBSERVABILITY,
                message="performance_assets=true; observability_kinds=0",
                performance_category=category,
                attributes={
                    "performance_assets": "true",
                    "observability_kinds": "",
                },
            ),
            *path_evidence_from_facts(
                facts=facts,
                performance_category=category,
                label="performance_asset",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_WITHOUT_OBSERVABILITY,
                    title="Performance assets without observability evidence",
                    summary=(
                        "Repository performance evidence includes performance-related "
                        "assets without known observability or profiling signals. "
                        "This does not claim observability is absent."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_WITHOUT_OBSERVABILITY,
                        "without_observability",
                        "0",
                    ),
                )
            ]
        )


class ConfigControlsDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CONFIG_CONTROLS,
            title="Performance configuration control signals detected",
            description=(
                "Detects thread-pool, executor, cache, datasource, or timeout "
                "configuration signals."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        kinds = known_configuration_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.configuration_controls_facts if item.kind in kinds]
        category = PerformanceCategory.CONFIGURATION_CONTROLS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CONFIG_CONTROLS,
                message=f"configuration_kinds={joined}",
                performance_category=category,
                attributes={"configuration_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, performance_category=category, label="configuration_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CONFIG_CONTROLS,
                    title="Performance configuration control signals detected",
                    summary=(
                        "Repository performance evidence includes configuration "
                        f"control signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_CONFIG_CONTROLS, "configuration_controls", joined),
                )
            ]
        )


class BroadFoundationsRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_BROAD_FOUNDATIONS,
            title="Broad performance evidence foundations",
            description=(
                "Detects three or more distinct performance evidence families. "
                "Does not establish that the repository is performant."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        families = active_families(evidence)
        if len(families) < 3:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(families)
        category = PerformanceCategory.MISCELLANEOUS
        levels = [
            *(item.confirmation_level for item in evidence.data_access_facts),
            *(item.confirmation_level for item in evidence.blocking_operations_facts),
            *(item.confirmation_level for item in evidence.caching_facts),
            *(item.confirmation_level for item in evidence.concurrency_async_facts),
            *(item.confirmation_level for item in evidence.resource_management_facts),
            *(item.confirmation_level for item in evidence.frontend_performance_facts),
            *(item.confirmation_level for item in evidence.observability_profiling_facts),
            *(item.confirmation_level for item in evidence.configuration_controls_facts),
        ]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_BROAD_FOUNDATIONS,
                message=f"family_count={len(families)}; families={joined}",
                performance_category=category,
                attributes={
                    "families": joined,
                    "family_count": str(len(families)),
                    "technologies": ",".join(evidence.coverage.technologies_represented),
                },
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_BROAD_FOUNDATIONS,
                    title="Broad performance evidence foundations",
                    summary=(
                        f"Observed {len(families)} performance evidence families "
                        f"({joined}). This does not establish that the repository "
                        "is performant."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels(levels),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_BROAD_FOUNDATIONS, "broad_foundations", joined),
                )
            ]
        )


class LimitedControlsRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LIMITED_CONTROLS,
            title="Limited performance evidence foundations",
            description=(
                "Observes performance assets with fewer than three active evidence "
                "families. Does not claim controls are insufficient."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _performance_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_performance_evidence(context)
        assert evidence is not None
        families = active_families(evidence)
        if len(families) >= 3:
            return SharedRuleEvaluationResult.not_matched()
        if not performance_assets_present(evidence):
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(families)
        category = PerformanceCategory.MISCELLANEOUS
        facts: list[PerformanceFact] = [
            *[item for item in evidence.data_access_facts if item.kind.value != "unknown"],
            *[item for item in evidence.blocking_operations_facts if item.kind.value != "unknown"],
            *[item for item in evidence.caching_facts if item.kind.value != "unknown"],
            *[item for item in evidence.concurrency_async_facts if item.kind.value != "unknown"],
            *[item for item in evidence.resource_management_facts if item.kind.value != "unknown"],
            *[item for item in evidence.frontend_performance_facts if item.kind.value != "unknown"],
            *[
                item
                for item in evidence.observability_profiling_facts
                if item.kind.value != "unknown"
            ],
        ]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_LIMITED_CONTROLS,
                message=f"family_count={len(families)}; families={joined}",
                performance_category=category,
                attributes={
                    "families": joined,
                    "family_count": str(len(families)),
                },
            ),
            *path_evidence_from_facts(
                facts=facts,
                performance_category=category,
                label="limited_foundation_fact",
            ),
        ]
        family_word = "family" if len(families) == 1 else "families"
        suffix = f" ({joined})" if joined else ""
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_LIMITED_CONTROLS,
                    title="Limited performance evidence foundations",
                    summary=(
                        "Repository performance evidence includes performance-related "
                        f"assets with {len(families)} active evidence "
                        f"{family_word}{suffix}. This does not establish "
                        "performance gaps."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_LIMITED_CONTROLS,
                        "limited_controls",
                        joined or "0",
                    ),
                )
            ]
        )
