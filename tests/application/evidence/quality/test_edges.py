"""Additional E08.1 edge, partial and unsupported fixtures."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from codestrata.application.evidence.quality.consumer import (
    ConsumerContractError,
    consume_envelope,
)
from codestrata.application.evidence.quality.envelope import (
    QUALITY_ENVELOPE_SCHEMA,
    EnvelopeError,
    QualityEnvelope,
    QualityEnvelopeBody,
    parse_envelope_payload,
)
from codestrata.application.evidence.quality.maps import QualityBudgets, language_for_path
from codestrata.application.evidence.quality.models import (
    FileRole,
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
)
from codestrata.application.evidence.quality.projections import dumps_quality_json
from codestrata.application.evidence.quality.roles import (
    file_role,
    is_ignored,
    is_supported_source_path,
)
from codestrata.application.evidence.quality.service import QualityEvidenceService
from codestrata.application.rules.security.yaml_catalog import YamlCatalogError
from codestrata.application.rules.technical_debt.yaml_catalog import (
    CATALOG_DIR,
    bundled_quality_rule,
    parse_quality_rule_document,
    quality_catalog_digests,
)
from codestrata.application.rules.technical_debt.yaml_quality import (
    CloneIndicatorRule,
    ComplexityRule,
    NestingRule,
    quality_evidence,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus


def _collect(
    paths: tuple[str, ...],
    texts: dict[str, str],
    *,
    budgets: QualityBudgets | None = None,
) -> tuple[QualityEvidence, QualityEnvelope]:
    return QualityEvidenceService(budgets=budgets).collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest=quality_catalog_digests()["pack"],
    )


def test_javascript_class_method_arrow_and_nested_function() -> None:
    source = "\n".join(
        (
            "class Box {",
            "  method(x) {",
            "    if (x) { return x; }",
            "    return 0;",
            "  }",
            "}",
            "const arrow = (value) => {",
            "  if (value) { return 1; }",
            "  return 0;",
            "};",
            "function outer() {",
            "  function inner() { return 1; }",
            "  return inner();",
            "}",
            "",
        )
    )
    evidence, envelope = _collect(("src/box.js",), {"src/box.js": source})
    names = {item.name for item in evidence.functions}
    assert "method" in names
    assert any(item.name.startswith("<arrow>") for item in evidence.functions)
    assert "outer" in names
    assert "inner" in names
    outer = next(item for item in evidence.functions if item.name == "outer")
    inner = next(item for item in evidence.functions if item.name == "inner")
    assert outer.cyclomatic == 1
    assert inner.cyclomatic == 1
    consume_envelope(envelope.model_dump(mode="json"))


def test_typescript_is_supported_and_php_is_unknown_not_zero() -> None:
    ts = "function typed(x: number): number { if (x) { return x; } return 0; }\n"
    php = "<?php function f() { if ($x) { return 1; } }\n"
    evidence, _ = _collect(
        ("src/a.ts", "src/b.php"),
        {"src/a.ts": ts, "src/b.php": php},
    )
    assert any(item.language == "typescript" for item in evidence.functions)
    php_file = next(item for item in evidence.files if item.path.endswith(".php"))
    assert php_file.parse_status is MetricStatusName.UNKNOWN
    assert php_file.unknown_reason == "unsupported_language_map"
    assert not any(item.path.endswith(".php") for item in evidence.functions)


def test_java_nested_type_and_comment_nloc() -> None:
    source = "\n".join(
        (
            "class Outer {",
            "  // comment only",
            "  class Inner {",
            "    void run() {",
            "      int x = 1;",
            "    }",
            "  }",
            "}",
            "",
        )
    )
    evidence, _ = _collect(("src/Outer.java",), {"src/Outer.java": source})
    assert evidence.functions
    assert any("Inner" in item.qualified_name for item in evidence.functions)
    assert evidence.files[0].nloc is not None
    assert evidence.files[0].nloc < evidence.files[0].physical_lines


def test_file_over_budget_and_token_cutoff_are_partial() -> None:
    source = "def ok():\n    return 1\n"
    over, _ = _collect(
        ("pkg/big.py",),
        {"pkg/big.py": source * 100},
        budgets=QualityBudgets(max_file_bytes=20, max_files=2000, max_tokens=500_000),
    )
    assert over.files[0].unknown_reason == "file_over_budget"
    cut, envelope = _collect(
        ("pkg/a.py",),
        {"pkg/a.py": "def ok():\n    return 1\n"},
        budgets=QualityBudgets(max_file_bytes=1_048_576, max_files=2000, max_tokens=1),
    )
    assert cut.clone.cutoff is True
    consume_envelope(envelope.model_dump(mode="json"))


def test_vendor_path_excluded_from_clones() -> None:
    block = "\n".join(f"    n_{index} = {index}" for index in range(60))
    copied = f"def copied():\n{block}\n    return n_0\n"
    evidence, _ = _collect(
        ("pkg/a.py", "node_modules/lib/b.py"),
        {"pkg/a.py": copied, "node_modules/lib/b.py": copied},
    )
    assert any("vendor_excluded" in item for item in evidence.limitations)
    assert all("node_modules" not in item.path for item in evidence.clone.merged_spans)


def test_consumer_rejects_health_score_and_corrupt_envelope() -> None:
    _, envelope = _collect(("pkg/mod.py",), {"pkg/mod.py": "def ok():\n    return 1\n"})
    dumped = envelope.model_dump(mode="json")
    dumped["health_score"] = 100
    with pytest.raises(ConsumerContractError):
        consume_envelope(dumped)
    with pytest.raises(ConsumerContractError):
        consume_envelope("not-an-object")
    with pytest.raises(EnvelopeError):
        parse_envelope_payload({"schema_name": "other", "schema_version": "1"})
    tampered = envelope.model_dump(mode="json")
    tampered["body_digest"] = "0" * 64
    with pytest.raises((EnvelopeError, ConsumerContractError)):
        consume_envelope(tampered)


def test_yaml_rule_not_applicable_without_evidence() -> None:
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
    )
    assert quality_evidence(context) is None
    assert ComplexityRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE
    assert NestingRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE
    assert CloneIndicatorRule().evaluate(context).status is RuleResultStatus.NOT_APPLICABLE


def test_loader_rejects_wrong_kind_and_unknown_fields() -> None:
    document = {
        "api_version": "codestrata.io/rules/v1",
        "kind": "NotRule",
        "metadata": {
            "id": "quality.complexity",
            "version": "1.0.0",
            "title": "x",
            "category": "quality",
            "owner": "codestrata",
            "measurement": "M16",
            "tags": ["quality"],
        },
        "applies_to": {"languages": ["python"]},
        "select": {"source": "quality"},
        "condition": {"operator": "quality.complexity"},
        "emit": {"finding": {"default_severity": "medium", "message": {"template": "x"}}},
        "evidence": {"include": ["span"]},
        "parameters": {},
    }
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(document, path=Path("quality.complexity.yaml"))


def test_language_for_path_and_empty_text() -> None:
    assert language_for_path("a.java") == "java"
    assert language_for_path("a.py") == "python"
    assert language_for_path("a.js") == "javascript"
    assert language_for_path("a.tsx") == "typescript"
    assert language_for_path("a.php") == "php"
    empty, _ = _collect(("pkg/empty.py",), {"pkg/empty.py": ""})
    assert empty.files[0].physical_lines == 0


def test_javascript_unbalanced_function_is_unknown() -> None:
    evidence, _ = _collect(
        ("src/bad.js",),
        {"src/bad.js": "function broken() { if (true) {\n"},
    )
    unknown = [item for item in evidence.functions if item.status is FunctionStatus.UNKNOWN]
    assert unknown or evidence.files[0].parse_status is MetricStatusName.UNKNOWN


def test_language_maps_and_roles() -> None:
    assert language_for_path("README") is None
    assert language_for_path("a.cs") == "csharp"
    assert is_supported_source_path("a.py")
    assert not is_supported_source_path("a.txt")
    assert is_ignored(".codestrata/cache.py")
    assert file_role("node_modules/lib/b.py") is FileRole.VENDOR
    assert file_role("third_party/lib/b.py") is FileRole.VENDOR
    assert file_role("generated/copy.py") is FileRole.GENERATED


def test_python_declared_constructs_and_nested_class() -> None:
    source = "\n".join(
        (
            "class Outer:",
            "    class Inner:",
            "        async def walk(self, items):",
            "            async for item in items:",
            "                while item:",
            "                    try:",
            "                        if item and item or False:",
            "                            return [x for x in items if x]",
            "                    except ValueError:",
            "                        return 0",
            "            match item:",
            "                case 1:",
            "                    return 1",
            "                case _:",
            "                    return 0",
            "",
            "if True:",
            "    def hidden():",
            "        return 1",
            "",
        )
    )
    evidence, _ = _collect(("pkg/rich.py",), {"pkg/rich.py": source})
    walk = next(item for item in evidence.functions if item.name == "walk")
    constructs = {item.syntax for item in walk.branches}
    assert "async_for" in constructs
    assert "while" in constructs
    assert "except" in constructs
    assert "if" in constructs
    assert "boolop_and" in constructs or "boolop_or" in constructs
    assert "match_case_non_wildcard" in constructs
    assert "comprehension_if" in constructs
    assert any("Inner" in item.qualified_name for item in evidence.functions)


def test_javascript_generator_arrow_comments_and_class_nested() -> None:
    source = "\n".join(
        (
            "function* gen() { yield 1; }",
            "const expr = (x) => x && 1;",
            "const tmpl = (x) => { return `hi ${x}`; };",
            "function uses(a, b) {",
            "  if (a === b) { return a !== b; }",
            "  /* block",
            "     comment */",
            "  return a?.b ?? 0;",
            "}",
            "class Box {",
            "  method() {",
            "    function inner() { return 1; }",
            "    const nested = () => { return 2; };",
            "    if (true) return inner();",
            "    return 0;",
            "  }",
            "}",
            "",
        )
    )
    evidence, envelope = _collect(("src/rich.js",), {"src/rich.js": source})
    names = {item.name for item in evidence.functions}
    assert "gen" in names
    assert "uses" in names
    assert "method" in names
    assert "inner" in names
    assert any(item.name.startswith("<arrow>") for item in evidence.functions)
    consume_envelope(envelope.model_dump(mode="json"))


def test_java_braceless_if_and_lambda() -> None:
    source = "\n".join(
        (
            "class Sample {",
            "  void compact(int x) {",
            "    if (x > 0) return;",
            "    Runnable task = () -> { if (x > 1) { return; } };",
            "  }",
            "}",
            "",
        )
    )
    evidence, _ = _collect(("src/Sample.java",), {"src/Sample.java": source})
    compact = next(item for item in evidence.functions if item.name == "compact")
    assert compact.cyclomatic is not None and compact.cyclomatic >= 2


def test_backslash_text_lookup_and_php_unsupported_tokenization() -> None:
    evidence, _ = _collect(
        ("pkg/mod.py", "src/app.php"),
        {"pkg\\mod.py": "def ok():\n    return 1\n", "src/app.php": "<?php function f() {}\n"},
    )
    assert evidence.files
    php_limited = any(
        "unsupported_tokenization:src/app.php" in item for item in evidence.limitations
    )
    php_recorded = any(item.path.endswith(".php") for item in evidence.files)
    assert php_limited or php_recorded


def test_yaml_loader_rejects_invalid_documents() -> None:
    base = deepcopy(bundled_quality_rule("quality.complexity")["document"])
    path = CATALOG_DIR / "quality.complexity.yaml"
    wrong_api = deepcopy(base)
    wrong_api["api_version"] = "other"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(wrong_api, path=path)
    no_meta = deepcopy(base)
    no_meta["metadata"] = "x"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(no_meta, path=path)
    bad_id = deepcopy(base)
    bad_id["metadata"] = dict(base["metadata"])
    bad_id["metadata"]["id"] = "quality.maintainability_index"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(bad_id, path=path)
    no_cond = deepcopy(base)
    no_cond["condition"] = "x"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(no_cond, path=path)
    no_emit = deepcopy(base)
    no_emit["emit"] = {}
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(no_emit, path=path)
    bad_sev = deepcopy(base)
    bad_sev["emit"] = deepcopy(base["emit"])
    bad_sev["emit"]["finding"] = dict(base["emit"]["finding"])
    bad_sev["emit"]["finding"]["default_severity"] = "not-a-severity"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(bad_sev, path=path)
    no_msg = deepcopy(base)
    no_msg["emit"] = deepcopy(base["emit"])
    no_msg["emit"]["finding"] = dict(base["emit"]["finding"])
    no_msg["emit"]["finding"]["message"] = {}
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(no_msg, path=path)
    bad_params = deepcopy(base)
    bad_params["parameters"] = "x"
    with pytest.raises(YamlCatalogError):
        parse_quality_rule_document(bad_params, path=path)
    no_langs = deepcopy(base)
    no_langs["applies_to"] = "x"
    parsed = parse_quality_rule_document(no_langs, path=path)
    assert parsed["languages"] == ()
    empty_langs = deepcopy(base)
    empty_langs["applies_to"] = {"languages": "python"}
    assert parse_quality_rule_document(empty_langs, path=path)["languages"] == ()
    metadata = ComplexityRule().metadata
    assert str(metadata.rule_id) == "quality.complexity"
    assert QualityEnvelopeBody.as_tuple(None) == ()
    assert QualityEnvelopeBody.as_tuple([1]) == (1,)
    with pytest.raises(EnvelopeError):
        QualityEnvelopeBody.as_tuple("bad")
    with pytest.raises(EnvelopeError, match="version"):
        parse_envelope_payload({"schema_name": QUALITY_ENVELOPE_SCHEMA, "schema_version": "x"})
    with pytest.raises(EnvelopeError, match="major"):
        parse_envelope_payload({"schema_name": QUALITY_ENVELOPE_SCHEMA, "schema_version": "9.0.0"})
    _, envelope = _collect(("pkg/mod.py",), {"pkg/mod.py": "def ok():\n    return 1\n"})
    dumped_json = dumps_quality_json(envelope)
    assert envelope.body_digest in dumped_json


def test_clone_token_cutoff_unknown_is_not_a_zero() -> None:
    evidence, _ = _collect(
        ("pkg/a.py",),
        {"pkg/a.py": "def ok():\n    return 1\n"},
        budgets=QualityBudgets(max_file_bytes=1_048_576, max_files=2000, max_tokens=1),
    )
    assert evidence.clone.cutoff is True
    assert evidence.clone.status is MetricStatusName.UNKNOWN
    assert evidence.clone.serialized is None
    assert (
        CloneIndicatorRule()
        .evaluate(
            RuleExecutionContext(
                repository=RepositoryFactView(repository_id="fixture"),
                languages=LanguageInventoryView(languages=("python",)),
                assessment_graph=evidence,
            )
        )
        .status
        is RuleResultStatus.NOT_APPLICABLE
    )
