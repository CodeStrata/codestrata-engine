"""Additional negative, partial and unsupported fixtures for E08.2 coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.evidence.testing.consumer import (
    ConsumerContractError,
    consume_envelope,
)
from codestrata.application.evidence.testing.envelope import (
    EnvelopeError,
    TestingEnvelopeBody,
    digest_body,
    parse_envelope_payload,
)
from codestrata.application.evidence.testing.models import (
    AssociationMethod,
    GapStatus,
    MetricStatusName,
    SkipKind,
)
from codestrata.application.evidence.testing.paths import (
    convention_stems,
    eligible_production,
    is_generated_path,
    is_test_like,
    normalize_relative_path,
    resolve_relative_specifier,
    stem_without_suffix,
    unsupported_language_for_path,
)
from codestrata.application.evidence.testing.projections import (
    dumps_testing_json,
    project_testing_sarif,
)
from codestrata.application.evidence.testing.service import TestingEvidenceService
from codestrata.application.rules.security.yaml_catalog import YamlCatalogError
from codestrata.application.rules.testing.yaml_catalog import (
    bundled_testing_rule,
    parse_testing_rule_document,
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


def _run(paths: tuple[str, ...], texts: dict[str, str]):
    return TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest="abc",
    )


def _ctx(evidence, *, slot: str = "assessment_graph") -> RuleExecutionContext:
    kwargs: dict[str, object] = {
        "repository": RepositoryFactView(repository_id="fixture"),
        "languages": LanguageInventoryView(languages=("python", "java", "javascript")),
        slot: evidence,
    }
    return RuleExecutionContext(**kwargs)


def test_python_prefix_import_and_relative_js_reference() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "tests/test_alpha.py": (
            "from pkg import alpha\n\ndef test_work():\n    assert alpha.work() == 1\n"
        ),
        "src/util.js": "export function n() { return 1; }\n",
        "src/util.test.js": (
            "import { n } from './util';\ntest('n', () => { expect(n()).toBe(1); });\n"
        ),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    methods = {item.production_path: item.method for item in evidence.association.associations}
    assert methods.get("pkg/alpha.py") is AssociationMethod.IMPORT_REFERENCE
    assert methods.get("src/util.js") is AssociationMethod.IMPORT_REFERENCE
    dumped = dumps_testing_json(envelope)
    assert "static_test_association_not_runtime_coverage" in dumped


def test_java_suffix_import_and_typescript_spec_convention() -> None:
    texts = {
        "src/main/java/com/demo/Alpha.java": (
            "package com.demo;\nclass Alpha { int n() { return 1; } }\n"
        ),
        "src/test/java/com/demo/AlphaTest.java": (
            "import Alpha;\nclass AlphaTest {\n  @ParameterizedTest\n"
            "  public void n() {}\n}\n"
        ),
        "src/util.ts": "export function n() { return 1; }\n",
        "src/util.spec.ts": "test('n', () => { expect(1).toBe(1); });\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    methods = {item.production_path: item.method for item in evidence.association.associations}
    assert methods.get("src/main/java/com/demo/Alpha.java") is AssociationMethod.IMPORT_REFERENCE
    assert methods.get("src/util.ts") is AssociationMethod.NAMING_CONVENTION
    assert any(item.framework == "junit_jupiter" for item in evidence.tests)


def test_python_syntax_error_is_not_a_zero_runtime_coverage() -> None:
    texts = {
        "./pkg/alpha.py": "def work():\n    return 1\n",
        "tests/test_alpha.py": "def test_work(\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    assert evidence.association.runtime_coverage is None
    assert evidence.association.eligible == 1
    assert evidence.association.associated == 1
    assert evidence.association.associations[0].method is AssociationMethod.NAMING_CONVENTION


def test_unittest_class_importfrom_and_python_test_suffix() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "tests/alpha_test.py": (
            "import unittest\nfrom pkg.alpha import work\n\n"
            "class TestAlpha(unittest.TestCase):\n"
            "    def test_work(self):\n"
            "        self.assertEqual(work(), 1)\n"
        ),
    }
    evidence, _ = _run(tuple(texts), texts)
    assert any(item.framework == "unittest" for item in evidence.tests)
    assert evidence.association.associated == 1


def test_vendor_php_and_generated_are_not_eligible_production() -> None:
    texts = {
        "vendor/pkg/alpha.py": "def work():\n    return 1\n",
        "pkg/legacy.php": "<?php function n() { return 1; }\n",
        "tests/test_alpha.py": "def test_work():\n    assert True\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    assert "vendor/pkg/alpha.py" not in (evidence.association.unassociated or ())
    assert evidence.association.eligible == 0
    result = TestAssociationRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_playwright_hint_and_js_require_without_suffix() -> None:
    texts = {
        "src/util.js": "export function n() { return 1; }\n",
        "src/util.test.js": (
            "const { test } = require('@playwright/test');\n"
            "const util = require('./util');\n"
            "test('n', () => {});\n"
        ),
    }
    evidence, _ = _run(tuple(texts), texts)
    assert any(item.framework == "playwright" for item in evidence.tests)
    assert evidence.association.associations[0].method is AssociationMethod.IMPORT_REFERENCE


def test_unittest_skip_body_skip_and_java_ignore() -> None:
    texts = {
        "tests/test_unit.py": (
            "import unittest\n\n"
            "class TestGone(unittest.TestCase):\n"
            "    @unittest.skip('offline')\n"
            "    def test_gone(self):\n"
            "        assert False\n"
            "\n"
            "def test_body():\n"
            "    pytest.skip('literal')\n"
            "\n"
            "def test_if():\n"
            "    if sys.platform == 'win32':\n"
            "        pytest.skip('windows')\n"
            "\n"
            "def test_dyn_if():\n"
            "    if maybe():\n"
            "        pytest.skip('dyn')\n"
            "\n"
            "@pytest.mark.skipif(not True, reason='bool')\n"
            "def test_bool():\n"
            "    assert True\n"
            "\n"
            "@slow\n"
            "def test_slow():\n"
            "    assert True\n"
        ),
        "src/test/java/pkg/IgnoreTest.java": (
            "class IgnoreTest {\n  @Ignore(\"old\")\n  @Test void gone() {}\n"
            "  @DisabledIf(\"true\")\n  @Test void cond() {}\n"
            "  @Flaky\n  @Test void flaky() {}\n}\n"
        ),
        "src/skip.spec.js": (
            "it.skipIf(process.env.CI, 'ci');\n"
            "xit('old', () => {});\n"
            "describe.skip('suite', () => {});\n"
            "test('ok', () => {});\n"
        ),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.skipped.explicit_disabled >= 3
    assert evidence.skipped.conditional >= 2
    assert evidence.skipped.unknown_eligibility >= 1
    assert evidence.skipped.unsupported_decorator >= 1
    kinds = {item.kind for item in evidence.skipped.records}
    assert SkipKind.EXPLICIT_DISABLED in kinds
    assert SkipKind.CONDITIONAL in kinds
    sarif = project_testing_sarif(envelope)
    assert any(item["ruleId"] == "testing.disabled" for item in sarif["runs"][0]["results"])


def test_ten_explicit_skips_are_medium() -> None:
    lines = ["import pytest", ""]
    for index in range(10):
        lines.extend(
            (f"@pytest.mark.skip('n{index}')", f"def test_{index}():", "    assert True", "")
        )
    source = "\n".join(lines)
    evidence, _ = _run(("tests/test_many.py",), {"tests/test_many.py": source})
    assert evidence.skipped.explicit_disabled == 10
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.MEDIUM


def test_skip_syntax_error_is_unknown_not_disabled() -> None:
    texts = {"tests/test_bad.py": "def test_ok(\n"}
    evidence, _ = _run(tuple(texts), texts)
    assert evidence.skipped.explicit_disabled == 0
    assert evidence.skipped.status in {MetricStatusName.VALUE, MetricStatusName.UNKNOWN}


def test_package_json_and_coverage_invocation() -> None:
    texts = {
        "package.json": '{"scripts":{"test":"jest"}}\n',
        "pyproject.toml": (
            "[project]\nname='demo'\ndependencies=['pytest','coverage']\n"
            "[tool.coverage.run]\nsource=['pkg']\n"
        ),
        ".github/workflows/ci.yml": (
            "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "      - run: npm test\n      - run: pytest --cov=pkg\n"
        ),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.ci_gap.coverage_percent is None
    assert evidence.ci_gap.proven_absent == 0
    assert any(item.tool == "npm-script" for item in evidence.ci_gap.declared)
    sarif = project_testing_sarif(envelope)
    assert all(item["ruleId"] != "testing.ci_gap" for item in sarif["runs"][0]["results"])


def test_bash_delegated_script_and_no_declared_capability() -> None:
    invoked = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        "scripts/ci.sh": "#!/bin/sh\npytest\n",
        ".github/workflows/ci.yml": (
            "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "      - run: bash scripts/ci.sh\n"
        ),
    }
    evidence, _ = _run(tuple(invoked), invoked)
    assert any(item.status is GapStatus.INVOKED for item in evidence.ci_gap.gaps) or (
        evidence.ci_gap.proven_absent == 0
    )
    empty, _ = _run(("pkg/mod.py",), {"pkg/mod.py": "def n():\n    return 1\n"})
    assert empty.ci_gap.reason == "no_declared_test_or_coverage_capability"
    assert empty.ci_gap.status is MetricStatusName.NOT_APPLICABLE


def test_gitlab_ci_is_unknown_not_medium() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        ".gitlab-ci.yml": "test:\n  script: pytest\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    result = CiGapRule().evaluate(_ctx(evidence))
    assert result.status is not RuleResultStatus.MATCHED
    assert evidence.ci_gap.status in {MetricStatusName.UNKNOWN, MetricStatusName.NOT_APPLICABLE}


def test_proven_absent_emits_sarif_warning() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        ".github/workflows/ci.yml": (
            "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n      - run: echo hello\n"
        ),
    }
    evidence, envelope = _run(tuple(texts), texts)
    assert evidence.ci_gap.proven_absent >= 1
    sarif = project_testing_sarif(envelope)
    assert any(item["ruleId"] == "testing.ci_gap" for item in sarif["runs"][0]["results"])
    metadata = CiGapRule().metadata
    assert str(metadata.rule_id) == "testing.ci_gap"
    applicability = CiGapRule().evaluate_applicability(_ctx(evidence))
    assert applicability.is_applicable


def test_evidence_slots_and_consumer_errors() -> None:
    texts = {"pkg/mod.py": "def n():\n    return 1\n"}
    evidence, envelope = _run(tuple(texts), texts)
    assert load_testing_evidence(_ctx(evidence, slot="enterprise_context")) is evidence
    assert load_testing_evidence(_ctx(evidence, slot="repository_testing_evidence")) is evidence
    assert TestAssociationRule().evaluate_applicability(_ctx(evidence)).is_applicable
    with pytest.raises(ConsumerContractError):
        consume_envelope({"schema_name": "nope"})
    with pytest.raises(ConsumerContractError):
        consume_envelope([])
    payload = envelope.model_dump(mode="json")
    payload["body"]["live_lookup"] = True
    payload["body_digest"] = digest_body(envelope.body.model_copy(update={"live_lookup": True}))
    with pytest.raises(EnvelopeError, match="live-lookup"):
        parse_envelope_payload(payload)
    with pytest.raises(EnvelopeError, match="must be an object"):
        parse_envelope_payload("nope")
    with pytest.raises(EnvelopeError, match="unsupported envelope version"):
        parse_envelope_payload(
            {**envelope.model_dump(mode="json"), "schema_version": "not-a-number"}
        )
    with pytest.raises(EnvelopeError, match="major version"):
        parse_envelope_payload({**envelope.model_dump(mode="json"), "schema_version": "2"})
    assert TestingEnvelopeBody.as_tuple(None) == ()
    with pytest.raises(EnvelopeError):
        TestingEnvelopeBody.as_tuple(1)


def test_path_helpers_and_catalog_parse_errors() -> None:
    assert normalize_relative_path("./pkg/alpha.py") == "pkg/alpha.py"
    assert is_generated_path("gen/test_alpha.py")
    assert unsupported_language_for_path("tests/sample_test.go") == "go"
    assert unsupported_language_for_path("spec.feature") == "cucumber"
    assert unsupported_language_for_path("pkg/alpha.py") is None
    assert is_test_like("src/alpha.spec.js")
    assert not eligible_production("node_modules/pkg/mod.py")
    assert "alpha" in convention_stems("tests/test_alpha.py", "python")
    assert "Alpha" in convention_stems("src/test/java/pkg/AlphaIT.java", "java")
    assert stem_without_suffix("notes.md") == "notes"
    assert resolve_relative_specifier("src/nested/util.test.js", "../lib") == "src/lib"
    document = bundled_testing_rule("testing.disabled")["document"].copy()
    with pytest.raises(YamlCatalogError, match="unknown fields"):
        parse_testing_rule_document({**document, "extra": 1}, path=Path("testing.disabled.yaml"))
    with pytest.raises(YamlCatalogError, match="api_version"):
        parse_testing_rule_document({**document, "api_version": "nope"}, path=Path("x.yaml"))
    with pytest.raises(YamlCatalogError, match="kind"):
        parse_testing_rule_document({**document, "kind": "Pack"}, path=Path("x.yaml"))
    with pytest.raises(YamlCatalogError, match="metadata"):
        parse_testing_rule_document({**document, "metadata": []}, path=Path("x.yaml"))
    broken = {**document, "metadata": {**document["metadata"], "id": "testing.nope"}}
    with pytest.raises(YamlCatalogError, match="not a testing rule"):
        parse_testing_rule_document(broken, path=Path("x.yaml"))
    with pytest.raises(YamlCatalogError, match="condition"):
        parse_testing_rule_document({**document, "condition": "x"}, path=Path("x.yaml"))
    finding = {**document["emit"]["finding"], "default_severity": "nope"}
    with pytest.raises(YamlCatalogError, match="default_severity"):
        parse_testing_rule_document(
            {**document, "emit": {**document["emit"], "finding": finding}},
            path=Path("x.yaml"),
        )
    finding = {**document["emit"]["finding"], "message": {"template": ""}}
    with pytest.raises(YamlCatalogError, match="template"):
        parse_testing_rule_document(
            {**document, "emit": {**document["emit"], "finding": finding}},
            path=Path("x.yaml"),
        )
    with pytest.raises(YamlCatalogError, match="parameters"):
        parse_testing_rule_document({**document, "parameters": []}, path=Path("x.yaml"))
    with pytest.raises(YamlCatalogError, match="unknown bundled rule"):
        bundled_testing_rule("testing.nope")
    association = TestAssociationRule()
    assert association.metadata.category.value
    assert "not measured runtime test coverage" in association._remediation
