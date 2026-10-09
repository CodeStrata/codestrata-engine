"""M17 fixtures: maximum nesting depth under declared construct maps."""

from __future__ import annotations

from codestrata.application.evidence.quality.consumer import consume_envelope
from codestrata.application.evidence.quality.envelope import QualityEnvelope
from codestrata.application.evidence.quality.maps import NESTING_FORMULA_VERSION
from codestrata.application.evidence.quality.models import FunctionStatus, QualityEvidence
from codestrata.application.evidence.quality.service import QualityEvidenceService
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.application.rules.technical_debt.yaml_quality import NestingRule
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity


def _run(paths: tuple[str, ...], texts: dict[str, str]) -> tuple[QualityEvidence, QualityEnvelope]:
    return QualityEvidenceService().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest=quality_catalog_digests()["quality.nesting"],
    )


def _ctx(evidence: QualityEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("java", "python", "javascript")),
        assessment_graph=evidence,
    )


def _nested_java(depth: int) -> str:
    lines = ["class Sample {", "  void nested(int x) {"]
    for index in range(depth):
        lines.append("    " * (index + 1) + f"if (x > {index}) {{")
    lines.append("    " * (depth + 1) + "return;")
    for index in range(depth, 0, -1):
        lines.append("    " * index + "}")
    lines.extend(["  }", "}", ""])
    return "\n".join(lines)


def test_depth_four_is_not_a_finding_depth_five_is_medium() -> None:
    depth4, _ = _run(("src/D4.java",), {"src/D4.java": _nested_java(4)})
    assert depth4.functions[0].max_nesting_depth == 4
    assert NestingRule().evaluate(_ctx(depth4)).status is RuleResultStatus.NOT_MATCHED

    depth5, envelope = _run(("src/D5.java",), {"src/D5.java": _nested_java(5)})
    function = depth5.functions[0]
    assert function.max_nesting_depth == 5
    assert function.nesting_version == NESTING_FORMULA_VERSION
    assert function.nesting_witness
    matched = NestingRule().evaluate(_ctx(depth5))
    assert matched.status is RuleResultStatus.MATCHED
    assert matched.matches[0].severity is RuleSeverity.MEDIUM
    consume_envelope(envelope.model_dump(mode="json"))


def test_python_nested_lambda_does_not_inflate_enclosing_nesting() -> None:
    source = "\n".join(
        (
            "def outer(items):",
            "    mapped = map(lambda value: value if value else 0, items)",
            "    return list(mapped)",
            "",
        )
    )
    evidence, _ = _run(("pkg/mod.py",), {"pkg/mod.py": source})
    outer = next(item for item in evidence.functions if item.name == "outer")
    lambdas = [item for item in evidence.functions if item.name.startswith("<lambda>")]
    assert outer.max_nesting_depth == 0
    assert lambdas
    nesting = lambdas[0].max_nesting_depth
    cyclomatic = lambdas[0].cyclomatic
    assert nesting is not None and nesting >= 0
    assert cyclomatic is not None and cyclomatic >= 2


def test_malformed_block_invalidates_negative_claim() -> None:
    evidence, envelope = _run(
        ("src/Broken.java",),
        {"src/Broken.java": "class Sample { void broken() { if (true) { \n"},
    )
    m17 = next(
        item for item in envelope.body.coverage if item.capability_id.endswith("m17.nesting")
    )
    assert m17.full_scope_status in {"unknown", "partial"}
    result = NestingRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE or (
        evidence.functions
        and all(
            item.status is not FunctionStatus.MEASURED or (item.max_nesting_depth or 0) <= 4
            for item in evidence.functions
        )
    )
    consume_envelope(envelope.model_dump(mode="json"))


def test_absent_functions_are_not_applicable() -> None:
    evidence, envelope = _run(
        ("pkg/empty.py",),
        {"pkg/empty.py": "VALUE = 1\n"},
    )
    assert evidence.functions == ()
    m17 = next(
        item for item in envelope.body.coverage if item.capability_id.endswith("m17.nesting")
    )
    assert m17.full_scope_status == "not_applicable"
    assert NestingRule().evaluate(_ctx(evidence)).status is RuleResultStatus.NOT_APPLICABLE


def test_javascript_for_of_is_a_nesting_construct() -> None:
    source = "\n".join(
        (
            "function walk(items) {",
            "  for (const item of items) {",
            "    if (item) {",
            "      return item;",
            "    }",
            "  }",
            "}",
            "",
        )
    )
    evidence, _ = _run(("src/walk.js",), {"src/walk.js": source})
    function = evidence.functions[0]
    assert function.status is FunctionStatus.MEASURED
    assert function.max_nesting_depth == 2
    constructs = [item.syntax for item in function.branches]
    assert "for" in constructs
    assert "if" in constructs
