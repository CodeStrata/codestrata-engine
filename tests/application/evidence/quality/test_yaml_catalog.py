"""Bundled quality YAML catalog, projections and consumer contract (E08.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.evidence.quality.consumer import (
    FORBIDDEN_HEALTH_KEYS,
    consume_envelope,
)
from codestrata.application.evidence.quality.projections import (
    project_quality_html,
    project_quality_json,
    project_quality_sarif,
)
from codestrata.application.evidence.quality.service import QualityEvidenceService
from codestrata.application.rules.security.yaml_catalog import YamlCatalogError, load_yaml_document
from codestrata.application.rules.technical_debt.yaml_catalog import (
    BUNDLED_RULE_IDS,
    QUALITY_RULE_IDS,
    bundled_quality_rule,
    load_quality_pack,
    load_quality_rules,
    parse_quality_rule_document,
    quality_catalog_digests,
)
from codestrata.domain.rules.enums import RuleSeverity


def test_bundled_catalog_covers_quality_rules() -> None:
    rules = load_quality_rules()
    pack = load_quality_pack()
    assert tuple(rules) == BUNDLED_RULE_IDS
    assert set(pack["document"]["rules"]) == set(BUNDLED_RULE_IDS)
    assert set(QUALITY_RULE_IDS) <= set(BUNDLED_RULE_IDS)
    complexity = bundled_quality_rule("quality.complexity")
    assert complexity["default_severity"] is RuleSeverity.MEDIUM
    assert bundled_quality_rule("quality.nesting")["default_severity"] is RuleSeverity.MEDIUM
    assert bundled_quality_rule("quality.clone_indicator")["default_severity"] is RuleSeverity.LOW
    assert bundled_quality_rule("quality.test_association")["default_severity"] is RuleSeverity.LOW
    assert bundled_quality_rule("maintainability.hotspot")["default_severity"] is (
        RuleSeverity.INFORMATIONAL
    )
    assert bundled_quality_rule("maintainability.dependency_age")["default_severity"] is (
        RuleSeverity.LOW
    )
    digests = quality_catalog_digests()
    assert set(digests) == {"pack", *BUNDLED_RULE_IDS}
    for digest in digests.values():
        assert len(digest) == 64


def test_loader_rejects_aliases_and_unknown_operator() -> None:
    with pytest.raises(YamlCatalogError, match="aliases"):
        load_yaml_document("x: &a 1\ny: *a\n", max_bytes=1024, label="alias.yaml")
    document = bundled_quality_rule("quality.complexity")["document"].copy()
    document["condition"] = {"operator": "quality.maintainability_index"}
    with pytest.raises(YamlCatalogError, match="allowlisted"):
        parse_quality_rule_document(document, path=Path("quality.complexity.yaml"))


def test_projections_share_one_canonical_digest() -> None:
    evidence, envelope = QualityEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("pkg/mod.py",),
        file_texts={"pkg/mod.py": "def ok():\n    return 1\n"},
        catalog_digest=quality_catalog_digests()["pack"],
    )
    dumped = envelope.model_dump(mode="json")
    consume_envelope(dumped)
    json_proj = project_quality_json(envelope)
    html = project_quality_html(envelope)
    sarif = project_quality_sarif(envelope)
    assert json_proj["body_digest"] == envelope.body_digest
    assert envelope.body_digest in html
    assert sarif["runs"][0]["properties"]["body_digest"] == envelope.body_digest
    assert json_proj["health_verdict"] == "none"
    assert json_proj["maintainability_index"] is None
    assert "maintainability_index: none" in html
    for key in FORBIDDEN_HEALTH_KEYS:
        assert key not in json_proj
    assert evidence.distribution.measured == 1


def test_deterministic_repeat() -> None:
    texts = {"src/Sample.java": "class Sample {\n  void a() { int x = 1; }\n}\n"}
    first, envelope_a = QualityEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("src/Sample.java",),
        file_texts=texts,
        catalog_digest="abc",
    )
    second, envelope_b = QualityEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("src/Sample.java",),
        file_texts=texts,
        catalog_digest="abc",
    )
    third, envelope_c = QualityEvidenceService().collect(
        repository_id="fixture",
        relative_paths=("src/Sample.java",),
        file_texts=texts,
        catalog_digest="abc",
    )
    assert envelope_a.body_digest == envelope_b.body_digest == envelope_c.body_digest
    assert first.functions == second.functions == third.functions
