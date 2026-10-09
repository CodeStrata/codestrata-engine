"""M19 fixtures: static test inventory and association (not runtime coverage)."""

from __future__ import annotations

from codestrata.application.evidence.testing.consumer import consume_envelope
from codestrata.application.evidence.testing.envelope import TestingEnvelope
from codestrata.application.evidence.testing.models import (
    AssociationConfidence,
    AssociationMethod,
    CoverageScope,
    MetricStatusName,
    TestingEvidence,
)
from codestrata.application.evidence.testing.service import TestingEvidenceService
from codestrata.application.rules.testing.yaml_catalog import (
    testing_catalog_digests as catalog_digests,
)
from codestrata.application.rules.testing.yaml_testing import TestAssociationRule
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity


def _run(paths: tuple[str, ...], texts: dict[str, str]) -> tuple[TestingEvidence, TestingEnvelope]:
    return TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest=catalog_digests()["quality.test_association"],
    )


def _ctx(evidence: TestingEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python", "java", "javascript")),
        assessment_graph=evidence,
    )


def test_direct_reference_is_high_confidence_not_runtime_coverage() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "tests/test_alpha.py": (
            "from pkg.alpha import work\n\ndef test_work():\n    assert work() == 1\n"
        ),
    }
    evidence, envelope = _run(("pkg/alpha.py", "tests/test_alpha.py"), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.association.runtime_coverage is None
    assert evidence.association.status is MetricStatusName.VALUE
    assert evidence.association.associated == 1
    assert evidence.association.eligible == 1
    assert evidence.association.serialized == "1.000000"
    record = evidence.association.associations[0]
    assert record.method is AssociationMethod.IMPORT_REFERENCE
    assert record.confidence is AssociationConfidence.HIGH
    assert any(item.framework == "pytest" for item in evidence.association.framework_counts)
    result = TestAssociationRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED
    html = __import__(
        "codestrata.application.evidence.testing.projections",
        fromlist=["project_testing_html"],
    ).project_testing_html(envelope)
    assert "not measured runtime coverage" in html
    assert "runtime_coverage: none" in html


def test_convention_only_is_medium_confidence() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "tests/test_alpha.py": "def test_work():\n    assert True\n",
    }
    evidence, _ = _run(("pkg/alpha.py", "tests/test_alpha.py"), texts)
    record = evidence.association.associations[0]
    assert record.method is AssociationMethod.NAMING_CONVENTION
    assert record.confidence is AssociationConfidence.MEDIUM
    assert evidence.association.associated == 1


def test_no_tests_is_zero_association_not_runtime_coverage() -> None:
    texts = {"pkg/alpha.py": "def work():\n    return 1\n"}
    evidence, envelope = _run(("pkg/alpha.py",), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.association.associated == 0
    assert evidence.association.eligible == 1
    assert evidence.association.serialized == "0.000000"
    assert evidence.association.unassociated == ("pkg/alpha.py",)
    result = TestAssociationRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW
    assert "not measured runtime test coverage" in result.matches[0].summary


def test_generated_tests_unknown_association_scope() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "generated/test_alpha.py": (
            "from pkg.alpha import work\n\ndef test_work():\n    assert work() == 1\n"
        ),
    }
    evidence, _ = _run(("pkg/alpha.py", "generated/test_alpha.py"), texts)
    assert evidence.association.status is MetricStatusName.UNKNOWN
    assert evidence.association.full_scope_status is CoverageScope.UNKNOWN
    assert evidence.association.generated_tests >= 1
    generated = any(
        item.method is AssociationMethod.GENERATED for item in evidence.association.associations
    )
    assert generated
    result = TestAssociationRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_ambiguous_association_is_not_a_unique_link() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "other/alpha.py": "def work():\n    return 2\n",
        "tests/test_alpha.py": "def test_work():\n    assert True\n",
    }
    evidence, _ = _run(("pkg/alpha.py", "other/alpha.py", "tests/test_alpha.py"), texts)
    methods = {item.method for item in evidence.association.associations}
    assert AssociationMethod.AMBIGUOUS in methods
    assert evidence.association.associated == 0
    assert evidence.association.eligible == 2


def test_java_direct_import_and_javascript_convention() -> None:
    texts = {
        "pkg/Alpha.java": "package pkg;\nclass Alpha { int n() { return 1; } }\n",
        "src/test/java/pkg/AlphaTest.java": (
            "package pkg;\nimport pkg.Alpha;\nclass AlphaTest {\n"
            "  @Test void n() { }\n}\n"
        ),
        "src/util.js": "export function n() { return 1; }\n",
        "src/util.test.js": "test('n', () => { expect(1).toBe(1); });\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    methods = {item.production_path: item.method for item in evidence.association.associations}
    assert methods.get("pkg/Alpha.java") is AssociationMethod.IMPORT_REFERENCE
    assert methods.get("src/util.js") is AssociationMethod.NAMING_CONVENTION


def test_unsupported_framework_unknown_scope() -> None:
    texts = {
        "pkg/alpha.py": "def work():\n    return 1\n",
        "tests/sample_test.go": "package tests\nfunc TestSample(t *testing.T) {}\n",
    }
    evidence, _ = _run(("pkg/alpha.py", "tests/sample_test.go"), texts)
    assert "go" in evidence.association.unsupported_frameworks
    assert evidence.association.full_scope_status is CoverageScope.UNKNOWN
    result = TestAssociationRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE
