"""Bundled maintainability YAML catalog, projections, consumer and retained rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.evidence.maintainability.consumer import (
    FORBIDDEN_SCORE_KEYS,
    consume_envelope,
)
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    CoverageScope,
    FileChurnRecord,
    HistoryWindow,
)
from codestrata.application.evidence.maintainability.projections import (
    project_maintainability_html,
    project_maintainability_json,
    project_maintainability_sarif,
)
from codestrata.application.evidence.maintainability.service import MaintainabilityEvidenceService
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    FileRole,
    FunctionRecord,
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
    SourceSpan,
)
from codestrata.application.evidence.quality.models import (
    CoverageScope as QualityCoverage,
)
from codestrata.application.rules.security.yaml_catalog import YamlCatalogError, load_yaml_document
from codestrata.application.rules.technical_debt.pack import technical_debt_rules
from codestrata.application.rules.technical_debt.yaml_catalog import (
    BUNDLED_RULE_IDS,
    MAINTAINABILITY_RULE_IDS,
    RETAINED_DEBT_RULE_IDS,
    bundled_quality_rule,
    load_quality_pack,
    load_quality_rules,
    parse_quality_rule_document,
    quality_catalog_digests,
)
from codestrata.application.rules.technical_debt.yaml_debt import (
    YamlDeepNestingRule,
    YamlExcessiveBranchingRule,
    YamlExcessiveParametersRule,
    YamlLargeCallableRule,
    YamlOversizedTypeRule,
)
from codestrata.application.rules.technical_debt.yaml_maintainability import (
    DependencyAgeRule,
    HotspotRule,
)
from codestrata.application.rules.testing.pack import testing_rules as load_hygiene_rules
from codestrata.application.rules.testing.yaml_catalog import (
    TESTING_RULE_IDS,
    bundled_testing_rule,
    load_testing_pack,
)
from codestrata.application.rules.testing.yaml_retained import (
    YamlCoverageWithoutCiRule,
    YamlDeclaredWithoutObservationRule,
    YamlDisabledOrSkippedRule,
    YamlUnconfirmedCandidatesRule,
)
from codestrata.domain.rules.enums import RuleSeverity
from codestrata.domain.technical_debt.ids import (
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_EXCESSIVE_PARAMETERS,
    RULE_LARGE_CALLABLE,
    RULE_OVERSIZED_TYPE,
)
from codestrata.domain.testing.ids import (
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)


def _quality() -> QualityEvidence:
    return QualityEvidence(
        repository_id="fixture",
        functions=(
            FunctionRecord(
                function_id="pkg/a.py:run",
                language="python",
                path="pkg/a.py",
                name="run",
                qualified_name="run",
                span=SourceSpan(path="pkg/a.py", line_start=1, line_end=4),
                role=FileRole.SOURCE,
                status=FunctionStatus.MEASURED,
                cyclomatic=5,
                branch_count=4,
                nloc=4,
                max_nesting_depth=1,
                cyclomatic_version="cyclomatic.v1",
                nesting_version="nesting.v1",
                size_version="nloc.v1",
                branch_map_language="python",
            ),
        ),
        clone=CloneMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            full_scope_status=QualityCoverage.NOT_APPLICABLE,
            reason="unused",
            normalization_version="token.normalize.v1",
            formula_version="clone.v1",
            min_tokens=50,
            min_lines=5,
        ),
    )


def test_bundled_catalog_covers_maintainability_and_retained_debt() -> None:
    rules = load_quality_rules()
    pack = load_quality_pack()
    assert set(MAINTAINABILITY_RULE_IDS) <= set(BUNDLED_RULE_IDS)
    assert set(RETAINED_DEBT_RULE_IDS) <= set(rules)
    assert set(pack["document"]["rules"]) == set(BUNDLED_RULE_IDS)
    assert bundled_quality_rule("maintainability.hotspot")["default_severity"] is (
        RuleSeverity.INFORMATIONAL
    )
    assert bundled_quality_rule("technical_debt.large-callable")["default_severity"] is (
        RuleSeverity.MEDIUM
    )
    testing = load_testing_pack()
    assert set(testing["document"]["rules"]) == set(TESTING_RULE_IDS)
    assert testing["deferred_rule_ids"] == ("testing.test-004",)
    assert bundled_testing_rule("testing.test-001")["rule_id"] == RULE_DISABLED_OR_SKIPPED
    digests = quality_catalog_digests()
    assert "maintainability.hotspot" in digests
    for digest in digests.values():
        assert len(digest) == 64


def test_loader_rejects_opaque_score_operator() -> None:
    with pytest.raises(YamlCatalogError, match="aliases"):
        load_yaml_document("x: &a 1\ny: *a\n", max_bytes=1024, label="alias.yaml")
    document = bundled_quality_rule("maintainability.hotspot")["document"].copy()
    document["condition"] = {"operator": "maintainability.health_score"}
    with pytest.raises(YamlCatalogError, match="allowlisted"):
        parse_quality_rule_document(document, path=Path("maintainability.hotspot.yaml"))


def test_projections_share_one_canonical_digest() -> None:
    evidence, envelope = MaintainabilityEvidenceService().collect(
        repository_id="fixture",
        quality=_quality(),
        components=(ComponentSpec(component_id="pkg", file_paths=("pkg/a.py",)),),
        history=HistoryWindow(
            profile_id="m24.history.profile.v1",
            window="180d_then_latest_1000",
            head_sha="abc",
            coverage=CoverageScope.COMPLETE,
            coverage_reason="complete",
            file_churn=(FileChurnRecord(path="pkg/a.py", changed_lines=2),),
        ),
        catalog_digest=quality_catalog_digests()["pack"],
    )
    dumped = envelope.model_dump(mode="json")
    consume_envelope(dumped)
    json_proj = project_maintainability_json(envelope)
    html = project_maintainability_html(envelope)
    sarif = project_maintainability_sarif(envelope)
    assert json_proj["body_digest"] == envelope.body_digest
    assert envelope.body_digest in html
    assert sarif["runs"][0]["properties"]["body_digest"] == envelope.body_digest
    assert json_proj["opaque_score"] is None
    assert json_proj["cost_to_fix"] is None
    assert "does not compute another priority" in html
    for key in FORBIDDEN_SCORE_KEYS:
        assert key not in json_proj
    assert evidence.complete_hotspots


def test_retained_yaml_rules_keep_stable_ids() -> None:
    assert str(YamlLargeCallableRule().metadata.rule_id) == RULE_LARGE_CALLABLE
    assert str(YamlExcessiveBranchingRule().metadata.rule_id) == RULE_EXCESSIVE_BRANCHING
    assert str(YamlDeepNestingRule().metadata.rule_id) == RULE_DEEP_NESTING
    assert str(YamlExcessiveParametersRule().metadata.rule_id) == RULE_EXCESSIVE_PARAMETERS
    assert str(YamlOversizedTypeRule().metadata.rule_id) == RULE_OVERSIZED_TYPE
    assert str(YamlDisabledOrSkippedRule().metadata.rule_id) == RULE_DISABLED_OR_SKIPPED
    assert str(YamlUnconfirmedCandidatesRule().metadata.rule_id) == RULE_UNCONFIRMED_CANDIDATES
    assert (
        str(YamlDeclaredWithoutObservationRule().metadata.rule_id)
        == RULE_DECLARED_WITHOUT_OBSERVATION
    )
    assert str(YamlCoverageWithoutCiRule().metadata.rule_id) == RULE_COVERAGE_WITHOUT_CI_INVOCATION
    assert HotspotRule().metadata.default_severity is RuleSeverity.INFORMATIONAL
    assert DependencyAgeRule().metadata.default_severity is RuleSeverity.LOW
    debt = technical_debt_rules()
    assert all(
        type(rule).__name__.startswith("Yaml") for rule in debt
    )
    assert [str(rule.metadata.rule_id) for rule in debt] == list(RETAINED_DEBT_RULE_IDS)
    hygiene = load_hygiene_rules()
    assert all(type(rule).__name__.startswith("Yaml") for rule in hygiene)
    assert [str(rule.metadata.rule_id) for rule in hygiene] == [
        RULE_DISABLED_OR_SKIPPED,
        RULE_UNCONFIRMED_CANDIDATES,
        RULE_DECLARED_WITHOUT_OBSERVATION,
        RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    ]
