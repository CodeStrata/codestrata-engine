"""M16 fixtures: size and function complexity with frozen language maps."""

from __future__ import annotations

from codestrata.application.evidence.quality.consumer import consume_envelope
from codestrata.application.evidence.quality.envelope import QualityEnvelope
from codestrata.application.evidence.quality.maps import CYCLOMATIC_FORMULA_VERSION
from codestrata.application.evidence.quality.models import (
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
)
from codestrata.application.evidence.quality.service import QualityEvidenceService
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.application.rules.technical_debt.yaml_quality import ComplexityRule
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
        catalog_digest=quality_catalog_digests()["quality.complexity"],
    )


def _ctx(evidence: QualityEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("java", "python", "javascript")),
        assessment_graph=evidence,
    )


def test_java_straight_line_is_cyclomatic_one() -> None:
    source = "\n".join(
        (
            "class Sample {",
            "  void straight() {",
            "    int value = 1;",
            "    return;",
            "  }",
            "}",
            "",
        )
    )
    evidence, envelope = _run(("src/Sample.java",), {"src/Sample.java": source})
    function = evidence.functions[0]
    assert function.status is FunctionStatus.MEASURED
    assert function.cyclomatic == 1
    assert function.branch_count == 0
    assert function.cyclomatic_version == CYCLOMATIC_FORMULA_VERSION
    consume_envelope(envelope.model_dump(mode="json"))
    result = ComplexityRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_java_if_loop_case_boolean_mapping() -> None:
    source = "\n".join(
        (
            "class Sample {",
            "  int mapped(int x, boolean a, boolean b) {",
            "    if (a && b) {",
            "      return 1;",
            "    }",
            "    for (int i = 0; i < x; i++) {",
            "      x = x + 1;",
            "    }",
            "    while (x > 0) {",
            "      x = x - 1;",
            "    }",
            "    do {",
            "      x = x + 1;",
            "    } while (x < 2);",
            "    try {",
            "      x = x / 1;",
            "    } catch (Exception error) {",
            "      return 0;",
            "    }",
            "    switch (x) {",
            "      case 1:",
            "        return 1;",
            "      case 2:",
            "        return 2;",
            "      default:",
            "        return a ? 3 : 4;",
            "    }",
            "  }",
            "}",
            "",
        )
    )
    evidence, _ = _run(("src/Sample.java",), {"src/Sample.java": source})
    function = evidence.functions[0]
    constructs = [item.syntax for item in function.branches]
    assert "if" in constructs
    assert "for" in constructs
    assert "while" in constructs
    assert "do_while" in constructs
    assert "catch" in constructs
    assert constructs.count("switch_case_non_default") == 2
    assert "ternary" in constructs
    assert "logical_and" in constructs
    assert "default" not in constructs
    assert "else" not in constructs
    assert function.cyclomatic == 1 + len(function.branches)


def test_python_nested_functions_are_excluded_from_enclosing() -> None:
    source = "\n".join(
        (
            "def outer():",
            "    value = 1",
            "    def inner():",
            "        if value:",
            "            return 2",
            "        return 3",
            "    return inner()",
            "",
        )
    )
    evidence, _ = _run(("pkg/mod.py",), {"pkg/mod.py": source})
    by_name = {item.name: item for item in evidence.functions}
    assert by_name["outer"].cyclomatic == 1
    assert by_name["inner"].cyclomatic == 2
    assert "if" in [item.syntax for item in by_name["inner"].branches]


def test_javascript_boolean_and_ternary() -> None:
    source = "\n".join(
        (
            "function mapped(a, b, x) {",
            "  if (a || b) {",
            "    return a ? 1 : 2;",
            "  }",
            "  return 0;",
            "}",
            "",
        )
    )
    evidence, _ = _run(("src/mapped.js",), {"src/mapped.js": source})
    function = evidence.functions[0]
    constructs = [item.syntax for item in function.branches]
    assert constructs.count("if") == 1
    assert constructs.count("logical_or") == 1
    assert constructs.count("ternary") == 1
    assert function.cyclomatic == 4


def test_malformed_syntax_is_unknown_not_zero() -> None:
    evidence, envelope = _run(
        ("pkg/bad.py",),
        {"pkg/bad.py": "def broken(\n"},
    )
    assert evidence.functions == ()
    assert evidence.files[0].parse_status is MetricStatusName.UNKNOWN
    m16 = next(
        item
        for item in envelope.body.coverage
        if item.capability_id.endswith("m16.size_complexity")
    )
    assert m16.full_scope_status == "unknown"
    assert m16.coverage_ratio is None
    result = ComplexityRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED
    consume_envelope(envelope.model_dump(mode="json"))


def test_complexity_threshold_boundary() -> None:
    lines = ["class Sample {", "  int many(int x) {"]
    for index in range(15):
        lines.append(f"    if (x == {index}) {{ return {index}; }}")
    lines.extend(["    return 0;", "  }", "}", ""])
    source = "\n".join(lines)
    evidence, _ = _run(("src/Sample.java",), {"src/Sample.java": source})
    function = evidence.functions[0]
    assert function.cyclomatic == 16
    matched = ComplexityRule().evaluate(_ctx(evidence))
    assert matched.status is RuleResultStatus.MATCHED
    assert matched.matches[0].severity is RuleSeverity.MEDIUM

    lines15 = ["class Sample {", "  int edge(int x) {"]
    for index in range(14):
        lines15.append(f"    if (x == {index}) {{ return {index}; }}")
    lines15.extend(["    return 0;", "  }", "}", ""])
    edge, _ = _run(("src/Edge.java",), {"src/Edge.java": "\n".join(lines15)})
    assert edge.functions[0].cyclomatic == 15
    assert ComplexityRule().evaluate(_ctx(edge)).status is RuleResultStatus.NOT_MATCHED


def test_size_threshold_is_low_and_gt_80() -> None:
    body = "\n".join(f"    int v{index} = {index};" for index in range(81))
    source = f"class Sample {{\n  void large() {{\n{body}\n  }}\n}}\n"
    evidence, _ = _run(("src/Large.java",), {"src/Large.java": source})
    function = evidence.functions[0]
    assert function.nloc is not None and function.nloc > 80
    matched = ComplexityRule().evaluate(_ctx(evidence))
    assert matched.status is RuleResultStatus.MATCHED
    assert any(item.severity is RuleSeverity.LOW for item in matched.matches)


def test_no_maintainability_index_in_canonical_body() -> None:
    evidence, envelope = _run(
        ("pkg/mod.py",),
        {"pkg/mod.py": "def ok():\n    return 1\n"},
    )
    dumped = envelope.model_dump(mode="json")
    assert dumped["body"]["maintainability_index"] is None
    assert dumped["body"]["health_verdict"] == "none"
    consume_envelope(dumped)
    assert evidence.distribution.measured == 1
