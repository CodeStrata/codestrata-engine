"""Bundled testing YAML catalog, projections, consumer and edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.evidence.testing.consumer import (
    FORBIDDEN_RUNTIME_KEYS,
    consume_envelope,
)
from codestrata.application.evidence.testing.envelope import (
    TESTING_ENVELOPE_SCHEMA,
    EnvelopeError,
    parse_envelope_payload,
)
from codestrata.application.evidence.testing.projections import (
    project_testing_html,
    project_testing_json,
    project_testing_sarif,
)
from codestrata.application.evidence.testing.service import TestingBudgets, TestingEvidenceService
from codestrata.application.rules.security.yaml_catalog import YamlCatalogError, load_yaml_document
from codestrata.application.rules.technical_debt.yaml_catalog import bundled_quality_rule
from codestrata.application.rules.testing.yaml_catalog import (
    TESTING_RULE_IDS,
    bundled_testing_rule,
    load_testing_pack,
    load_testing_rules,
    parse_testing_rule_document,
)
from codestrata.application.rules.testing.yaml_catalog import (
    testing_catalog_digests as catalog_digests,
)
from codestrata.application.rules.testing.yaml_testing import (
    CiGapRule,
    DisabledTestsRule,
    TestAssociationRule,
)
from codestrata.application.rules.testing.yaml_testing import (
    testing_evidence as load_testing_evidence,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity


def test_bundled_catalog_covers_testing_rules() -> None:
    rules = load_testing_rules()
    pack = load_testing_pack()
    assert tuple(rules) == TESTING_RULE_IDS
    assert set(pack["document"]["rules"]) == set(TESTING_RULE_IDS)
    assert bundled_testing_rule("testing.disabled")["default_severity"] is RuleSeverity.LOW
    assert bundled_testing_rule("testing.ci_gap")["default_severity"] is RuleSeverity.MEDIUM
    assert bundled_testing_rule("testing.test-001")["default_severity"] is RuleSeverity.LOW
    assert bundled_testing_rule("testing.test-005")["default_severity"] is RuleSeverity.MEDIUM
    assert bundled_quality_rule("quality.test_association")["default_severity"] is RuleSeverity.LOW
    digests = catalog_digests()
    assert "testing.disabled" in digests
    assert "quality.test_association" in digests
    for digest in digests.values():
        assert len(digest) == 64


def test_loader_rejects_aliases_and_unknown_operator() -> None:
    with pytest.raises(YamlCatalogError, match="aliases"):
        load_yaml_document("x: &a 1\ny: *a\n", max_bytes=1024, label="alias.yaml")
    document = bundled_testing_rule("testing.disabled")["document"].copy()
    document["condition"] = {"operator": "testing.runtime_coverage"}
    with pytest.raises(YamlCatalogError, match="allowlisted"):
        parse_testing_rule_document(document, path=Path("testing.disabled.yaml"))


def test_projections_share_one_canonical_digest() -> None:
    evidence, envelope = TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("pkg/mod.py", "tests/test_mod.py"),
        file_texts={
            "pkg/mod.py": "def ok():\n    return 1\n",
            "tests/test_mod.py": "from pkg.mod import ok\n\ndef test_ok():\n    assert ok() == 1\n",
        },
        catalog_digest=catalog_digests()["pack"],
    )
    dumped = envelope.model_dump(mode="json")
    consume_envelope(dumped)
    json_proj = project_testing_json(envelope)
    html = project_testing_html(envelope)
    sarif = project_testing_sarif(envelope)
    assert json_proj["body_digest"] == envelope.body_digest
    assert envelope.body_digest in html
    assert sarif["runs"][0]["properties"]["body_digest"] == envelope.body_digest
    assert json_proj["health_verdict"] == "none"
    assert json_proj["runtime_coverage"] is None
    assert json_proj["coverage_percent"] is None
    for key in FORBIDDEN_RUNTIME_KEYS:
        assert key not in json_proj
    assert evidence.association.associated == 1


def test_deterministic_repeat() -> None:
    texts = {
        "pkg/mod.py": "def ok():\n    return 1\n",
        "tests/test_mod.py": "def test_ok():\n    assert True\n",
    }
    first, envelope_a = TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=tuple(texts),
        file_texts=texts,
        catalog_digest="abc",
    )
    second, envelope_b = TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=tuple(texts),
        file_texts=texts,
        catalog_digest="abc",
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert envelope_a.body_digest == envelope_b.body_digest


def test_file_over_budget_is_partial_not_zero() -> None:
    huge = "def test_ok():\n    assert True\n" + ("x = 1\n" * 100)
    evidence, _ = TestingEvidenceService(TestingBudgets(max_file_bytes=20)).collect(
        repository_id="fixture",
        relative_paths=("tests/test_ok.py", "pkg/mod.py"),
        file_texts={"tests/test_ok.py": huge, "pkg/mod.py": "def ok():\n    return 1\n"},
        catalog_digest="abc",
    )
    assert any("file_over_budget" in item for item in evidence.limitations)


def test_corrupt_envelope_rejected() -> None:
    with pytest.raises(EnvelopeError):
        parse_envelope_payload({"schema_name": "nope"})
    _, envelope = TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("pkg/mod.py",),
        file_texts={"pkg/mod.py": "def ok():\n    return 1\n"},
        catalog_digest="abc",
    )
    payload = envelope.model_dump(mode="json")
    payload["body_digest"] = "0" * 64
    with pytest.raises(EnvelopeError, match="body_digest"):
        parse_envelope_payload(payload)
    assert envelope.schema_name == TESTING_ENVELOPE_SCHEMA


def test_rules_unavailable_without_evidence() -> None:
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
    )
    assert load_testing_evidence(context) is None
    assert TestAssociationRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE
    assert DisabledTestsRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE
    assert CiGapRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE
