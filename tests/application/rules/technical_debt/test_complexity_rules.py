"""Technical Debt complexity rule pack tests (Phase 4.3.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.rules.facade import RuleExecutionFacade
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.technical_debt.pack import (
    TechnicalDebtRulePack,
    technical_debt_rules,
)
from codestrata.application.rules.technical_debt.registration import register_technical_debt_pack
from codestrata.application.rules.technical_debt.rules import (
    DeepNestingRule,
    ExcessiveBranchingRule,
    ExcessiveParametersRule,
    LargeCallableRule,
    OversizedTypeRule,
)
from codestrata.application.technical_debt.assessment.factory import technical_debt_pack_enabled
from codestrata.config.settings import load_settings
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.complexity.enums import (
    ComplexityCallableKind,
    ComplexityTypeKind,
)
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    CallableComplexityEvidence,
    IntMetric,
    SourceSpan,
    TypeComplexityEvidence,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.enums import RuleCategory, RuleConfidence, RuleResultStatus
from codestrata.domain.technical_debt.ids import (
    COMPLEXITY_RULE_IDS,
    PACK_ID,
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_EXCESSIVE_PARAMETERS,
    RULE_LARGE_CALLABLE,
    RULE_OVERSIZED_TYPE,
)


def _provenance() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="language.python.complexity",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path="demo.py",
    )


def _callable(
    *,
    name: str,
    path: str = "demo.py",
    lines: IntMetric | None = None,
    params: IntMetric | None = None,
    branches: IntMetric | None = None,
    nesting: IntMetric | None = None,
    signature: str | None = None,
) -> CallableComplexityEvidence:
    qualified = signature or f"{name}#0@1"
    return CallableComplexityEvidence(
        evidence_id=f"ev:callable:{name}",
        language="python",
        path=path,
        name=name,
        qualified_signature=qualified,
        callable_kind=ComplexityCallableKind.FUNCTION,
        classification=SourceClassification.SOURCE,
        span=SourceSpan(path=path, line_start=1, line_end=10),
        physical_line_count=lines or IntMetric.available(1),
        parameter_count=params or IntMetric.available(0),
        branch_point_count=branches or IntMetric.available(0),
        max_nesting_depth=nesting or IntMetric.available(0),
        provenance=_provenance(),
    )


def _type(
    *,
    name: str,
    path: str = "demo.py",
    lines: IntMetric | None = None,
) -> TypeComplexityEvidence:
    return TypeComplexityEvidence(
        evidence_id=f"ev:type:{name}",
        language="python",
        path=path,
        name=name,
        qualified_name=name,
        type_kind=ComplexityTypeKind.CLASS,
        classification=SourceClassification.SOURCE,
        span=SourceSpan(path=path, line_start=1, line_end=20),
        physical_line_count=lines or IntMetric.available(10),
        callable_count=IntMetric.available(1),
        provenance=_provenance(),
    )


def _evidence(
    *,
    callables: tuple[CallableComplexityEvidence, ...] = (),
    types: tuple[TypeComplexityEvidence, ...] = (),
) -> AggregatedComplexityEvidence:
    return AggregatedComplexityEvidence(
        repository_id="repo:demo",
        callables=callables,
        types=types,
        contributing_provider_ids=("language.python.complexity",),
    )


def _context(evidence: AggregatedComplexityEvidence | None) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo:demo"),
        languages=LanguageInventoryView(languages=("python",)),
        complexity_evidence=evidence,
        policy=RuleExecutionPolicy(),
        provenance={"source": "test"},
    )


def test_pack_metadata_and_registration() -> None:
    pack = TechnicalDebtRulePack()
    assert pack.pack_id == PACK_ID
    assert "php" in pack.supported_languages
    assert set(pack.included_rule_ids) == set(COMPLEXITY_RULE_IDS)
    registry = RuleRegistry()
    register_technical_debt_pack(registry)
    listed = {
        str(item.metadata.rule_id)
        for item in registry.list_rules(category=RuleCategory.TECHNICAL_DEBT)
    }
    assert listed == set(COMPLEXITY_RULE_IDS)
    service = create_rule_analysis_service(include_architecture_pack=False)
    debt_ids = {
        str(item.metadata.rule_id)
        for item in service.list_rules(category=RuleCategory.TECHNICAL_DEBT)
    }
    assert debt_ids == set(COMPLEXITY_RULE_IDS)


def test_large_callable_positive_negative_boundary() -> None:
    rule = LargeCallableRule(max_physical_lines=50)
    positive = _context(
        _evidence(callables=(_callable(name="big", lines=IntMetric.available(51)),))
    )
    boundary = _context(
        _evidence(callables=(_callable(name="edge", lines=IntMetric.available(50)),))
    )
    negative = _context(
        _evidence(callables=(_callable(name="small", lines=IntMetric.available(10)),))
    )
    assert rule.evaluate(positive).status is RuleResultStatus.MATCHED
    assert rule.evaluate(boundary).status is RuleResultStatus.NOT_MATCHED
    assert rule.evaluate(negative).status is RuleResultStatus.NOT_MATCHED


def test_excessive_branching_and_nesting_and_parameters() -> None:
    branching = ExcessiveBranchingRule(max_branch_points=10)
    nesting = DeepNestingRule(max_nesting_depth=4)
    params = ExcessiveParametersRule(max_parameters=5)

    over = _context(
        _evidence(
            callables=(
                _callable(
                    name="busy",
                    signature="busy#6@1",
                    branches=IntMetric.available(11),
                    nesting=IntMetric.available(5),
                    params=IntMetric.available(6),
                ),
            )
        )
    )
    under = _context(
        _evidence(
            callables=(
                _callable(
                    name="calm",
                    signature="calm#1@1",
                    branches=IntMetric.available(2),
                    nesting=IntMetric.available(1),
                    params=IntMetric.available(1),
                ),
            )
        )
    )
    assert branching.evaluate(over).status is RuleResultStatus.MATCHED
    assert nesting.evaluate(over).status is RuleResultStatus.MATCHED
    assert params.evaluate(over).status is RuleResultStatus.MATCHED
    assert branching.evaluate(under).status is RuleResultStatus.NOT_MATCHED
    assert nesting.evaluate(under).status is RuleResultStatus.NOT_MATCHED
    assert params.evaluate(under).status is RuleResultStatus.NOT_MATCHED


def test_oversized_type_positive_and_boundary() -> None:
    rule = OversizedTypeRule(max_physical_lines=300)
    positive = _context(
        _evidence(types=(_type(name="Huge", lines=IntMetric.available(301)),))
    )
    boundary = _context(
        _evidence(types=(_type(name="Exact", lines=IntMetric.available(300)),))
    )
    assert rule.evaluate(positive).status is RuleResultStatus.MATCHED
    assert rule.evaluate(boundary).status is RuleResultStatus.NOT_MATCHED


def test_unsupported_metrics_never_match() -> None:
    rule = LargeCallableRule(max_physical_lines=1)
    evidence = _evidence(
        callables=(
            _callable(name="unknown", lines=IntMetric.unsupported()),
            _callable(name="missing", lines=IntMetric.unavailable(), signature="missing#0@2"),
        )
    )
    result = rule.evaluate(_context(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_missing_complexity_evidence_not_applicable() -> None:
    rule = LargeCallableRule()
    result = rule.evaluate(_context(None))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_deterministic_ordering_and_finding_ids() -> None:
    rules = technical_debt_rules(
        large_callable_max_lines=5,
        excessive_branching_max_branch_points=1,
        deep_nesting_max_depth=1,
        excessive_parameters_max_count=1,
        oversized_type_max_lines=5,
    )
    evidence = _evidence(
        callables=(
            _callable(
                name="b",
                path="b.py",
                signature="b#3@1",
                lines=IntMetric.available(20),
                branches=IntMetric.available(5),
                nesting=IntMetric.available(3),
                params=IntMetric.available(3),
            ),
            _callable(
                name="a",
                path="a.py",
                signature="a#3@1",
                lines=IntMetric.available(20),
                branches=IntMetric.available(5),
                nesting=IntMetric.available(3),
                params=IntMetric.available(3),
            ),
        ),
        types=(
            _type(name="Z", path="z.py", lines=IntMetric.available(50)),
            _type(name="A", path="a.py", lines=IntMetric.available(50)),
        ),
    )
    context = _context(evidence)
    first_matches = []
    second_matches = []
    for rule in rules:
        first = rule.evaluate(context)
        second = rule.evaluate(context)
        assert first.status is RuleResultStatus.MATCHED
        assert second == first
        first_matches.extend(first.matches)
        second_matches.extend(second.matches)
    assert [item.summary for item in first_matches] == [
        item.summary for item in second_matches
    ]
    mapper = RuleFindingMapper()
    category_by_rule = {rule_id: RuleCategory.TECHNICAL_DEBT for rule_id in COMPLEXITY_RULE_IDS}
    findings_one = mapper.map_matches(tuple(first_matches), category_by_rule=category_by_rule)
    findings_two = mapper.map_matches(tuple(second_matches), category_by_rule=category_by_rule)
    assert [item.id for item in findings_one] == [item.id for item in findings_two]
    assert all(item.category is FindingCategory.TECHNICAL_DEBT for item in findings_one)
    assert all(item.metadata.get("pack_id") == PACK_ID for item in findings_one)
    assert all(
        item.metadata.get("confidence") == RuleConfidence.HIGH.value
        for item in findings_one
    )
    assert all(item.metadata.get("remediation") for item in findings_one)


def test_facade_execution_with_registered_pack() -> None:
    registry = RuleRegistry()
    register_technical_debt_pack(registry)
    facade = RuleExecutionFacade(shared_registry=registry)
    evidence = _evidence(
        callables=(_callable(name="big", lines=IntMetric.available(100), signature="big#0@1"),)
    )
    result = facade.execute_shared(
        _context(evidence),
        include_rule_ids=frozenset({RULE_LARGE_CALLABLE}),
    )
    assert any(str(item.rule_id) == RULE_LARGE_CALLABLE for item in result.matches)


def test_complexity_threshold_settings(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules.technical_debt.complexity.large_callable]
        max_physical_lines = 12

        [rules.technical_debt.complexity.excessive_branching]
        max_branch_points = 3

        [rules.technical_debt.complexity.deep_nesting]
        max_nesting_depth = 2

        [rules.technical_debt.complexity.excessive_parameters]
        max_parameters = 2

        [rules.technical_debt.complexity.oversized_type]
        max_physical_lines = 40
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    complexity = settings.rules.technical_debt.complexity
    assert complexity.large_callable.max_physical_lines == 12
    assert complexity.excessive_branching.max_branch_points == 3
    assert complexity.deep_nesting.max_nesting_depth == 2
    assert complexity.excessive_parameters.max_parameters == 2
    assert complexity.oversized_type.max_physical_lines == 40
    assert settings.rules.technical_debt.enabled is False
    assert technical_debt_pack_enabled(settings) is False


def test_invalid_threshold_rejected(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [rules.technical_debt.complexity.large_callable]
        max_physical_lines = 0
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="max_physical_lines"):
        load_settings(config)


def test_rule_ids_stable() -> None:
    assert RULE_LARGE_CALLABLE == "technical_debt.large-callable"
    assert RULE_EXCESSIVE_BRANCHING == "technical_debt.excessive-branching"
    assert RULE_DEEP_NESTING == "technical_debt.deep-nesting"
    assert RULE_EXCESSIVE_PARAMETERS == "technical_debt.excessive-parameters"
    assert RULE_OVERSIZED_TYPE == "technical_debt.oversized-type"


def test_php_language_large_callable_finding() -> None:
    callable_item = CallableComplexityEvidence(
        evidence_id="ev:callable:php-big",
        language="php",
        path="src/App/Big.php",
        name="handle",
        qualified_signature="Controller.handle#1@1",
        callable_kind=ComplexityCallableKind.METHOD,
        owner_qualified_name="Controller",
        classification=SourceClassification.SOURCE,
        span=SourceSpan(path="src/App/Big.php", line_start=1, line_end=80),
        physical_line_count=IntMetric.available(80),
        parameter_count=IntMetric.available(1),
        branch_point_count=IntMetric.available(2),
        max_nesting_depth=IntMetric.available(1),
        provenance=EvidenceProvenance(
            provider_id="language.php.complexity",
            provider_version="1.0.0",
            source_analyzer="test",
            extraction_method="fixture",
            origin=EvidenceOrigin.SOURCE_PARSE,
            source_path="src/App/Big.php",
        ),
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo:php"),
        languages=LanguageInventoryView(languages=("php",)),
        complexity_evidence=AggregatedComplexityEvidence(
            repository_id="repo:php",
            callables=(callable_item,),
            contributing_provider_ids=("language.php.complexity",),
        ),
        policy=RuleExecutionPolicy(),
    )
    result = LargeCallableRule(max_physical_lines=50).evaluate(context)
    assert result.status is RuleResultStatus.MATCHED
    assert any("handle" in item.summary for item in result.matches)
