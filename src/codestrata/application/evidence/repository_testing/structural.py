"""Bounded structural inspection of candidate test files."""

from __future__ import annotations

from codestrata.application.evidence.repository_testing.discovery import (
    classification_for_path,
    language_hint_for_path,
    normalize_relative_path,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    EvidenceConfirmationLevel,
    TestFrameworkFamily,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_file_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import StructuralTestFactEvidence

_MAX_LINE_HINTS = 20

# (token, count_key, framework_hint | None)
_TOKEN_SPECS: tuple[tuple[str, str, TestFrameworkFamily | None, frozenset[str] | None], ...] = (
    # language_hint set None => apply to any language
    # Python
    ("def test_", "python_def_test", TestFrameworkFamily.PYTEST, frozenset({"python"})),
    ("class Test", "python_class_test", TestFrameworkFamily.UNITTEST, frozenset({"python"})),
    (
        "unittest.TestCase",
        "unittest_testcase",
        TestFrameworkFamily.UNITTEST,
        frozenset({"python"}),
    ),
    ("@pytest.fixture", "pytest_fixture", TestFrameworkFamily.PYTEST, frozenset({"python"})),
    ("@pytest.mark.", "pytest_mark", TestFrameworkFamily.PYTEST, frozenset({"python"})),
    ("pytest.skip", "pytest_skip", TestFrameworkFamily.PYTEST, frozenset({"python"})),
    # Java / JVM
    (
        "@ParameterizedTest",
        "java_parameterized_test",
        TestFrameworkFamily.JUNIT_JUPITER,
        frozenset({"java", "kotlin", "groovy"}),
    ),
    (
        "@SpringBootTest",
        "java_spring_boot_test",
        TestFrameworkFamily.JUNIT,
        frozenset({"java", "kotlin", "groovy"}),
    ),
    (
        "@Disabled",
        "java_disabled",
        TestFrameworkFamily.JUNIT_JUPITER,
        frozenset({"java", "kotlin", "groovy"}),
    ),
    ("@Ignore", "java_ignore", TestFrameworkFamily.JUNIT, frozenset({"java", "kotlin", "groovy"})),
    ("@Test", "java_test", TestFrameworkFamily.JUNIT, frozenset({"java", "kotlin", "groovy"})),
    ("org.junit", "org_junit", TestFrameworkFamily.JUNIT, frozenset({"java", "kotlin", "groovy"})),
    (
        "org.testng",
        "org_testng",
        TestFrameworkFamily.TESTNG,
        frozenset({"java", "kotlin", "groovy"}),
    ),
    # JS/TS
    (
        "@playwright/test",
        "playwright_import",
        TestFrameworkFamily.PLAYWRIGHT,
        frozenset({"javascript", "typescript"}),
    ),
    (
        "describe.skip",
        "js_describe_skip",
        TestFrameworkFamily.JEST,
        frozenset({"javascript", "typescript"}),
    ),
    (
        "test.skip",
        "js_test_skip",
        TestFrameworkFamily.JEST,
        frozenset({"javascript", "typescript"}),
    ),
    (
        "test.only",
        "js_test_only",
        TestFrameworkFamily.JEST,
        frozenset({"javascript", "typescript"}),
    ),
    (
        "describe(",
        "js_describe",
        TestFrameworkFamily.JEST,
        frozenset({"javascript", "typescript"}),
    ),
    ("test(", "js_test", TestFrameworkFamily.JEST, frozenset({"javascript", "typescript"})),
    ("it(", "js_it", TestFrameworkFamily.MOCHA, frozenset({"javascript", "typescript"})),
    ("cy.", "cypress_cy", TestFrameworkFamily.CYPRESS, frozenset({"javascript", "typescript"})),
    # .NET
    ("[Fact]", "dotnet_fact", TestFrameworkFamily.XUNIT, frozenset({"csharp"})),
    ("[Theory]", "dotnet_theory", TestFrameworkFamily.XUNIT, frozenset({"csharp"})),
    ("[TestMethod]", "dotnet_test_method", TestFrameworkFamily.MSTEST, frozenset({"csharp"})),
    ("[Test]", "dotnet_test", TestFrameworkFamily.NUNIT, frozenset({"csharp"})),
    ("[Ignore]", "dotnet_ignore", TestFrameworkFamily.NUNIT, frozenset({"csharp"})),
    # Go
    # PHP
    (
        "PHPUnit\\Framework\\TestCase",
        "phpunit_testcase",
        TestFrameworkFamily.PHPUNIT,
        frozenset({"php"}),
    ),
    (
        "extends TestCase",
        "php_extends_testcase",
        TestFrameworkFamily.PHPUNIT,
        frozenset({"php"}),
    ),
    (
        "@group",
        "phpunit_group",
        TestFrameworkFamily.PHPUNIT,
        frozenset({"php"}),
    ),
    (
        "markTestSkipped",
        "phpunit_skip",
        TestFrameworkFamily.PHPUNIT,
        frozenset({"php"}),
    ),
    ("func Test", "go_func_test", None, frozenset({"go"})),
    ("t.Skip(", "go_t_skip", None, frozenset({"go"})),
)

_MARKER_COUNT_KEYS = {
    "pytest_skip",
    "java_disabled",
    "java_ignore",
    "js_describe_skip",
    "js_test_skip",
    "js_test_only",
    "dotnet_ignore",
    "go_t_skip",
    "phpunit_skip",
}


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_structural_collector",
        extraction_method="structural_token_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def inspect_structural_facts(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str = "",
) -> StructuralTestFactEvidence | None:
    """Return structural facts for a candidate test file, or None if empty path."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return None

    structural_counts: dict[str, int] = {}
    marker_counts: dict[str, int] = {}
    framework_hints: list[TestFrameworkFamily] = []
    line_hints: list[int] = []
    seen_lines: set[int] = set()

    language_hint = language_hint_for_path(normalized)
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        matched_on_line = False
        for token, count_key, framework, languages in _TOKEN_SPECS:
            if languages is not None:
                if language_hint is None or language_hint not in languages:
                    continue
            if token not in line:
                continue
            structural_counts[count_key] = structural_counts.get(count_key, 0) + 1
            if count_key in _MARKER_COUNT_KEYS:
                marker_counts[count_key] = marker_counts.get(count_key, 0) + 1
            if framework is not None and framework not in framework_hints:
                framework_hints.append(framework)
            matched_on_line = True
        if matched_on_line and line_no not in seen_lines and len(line_hints) < _MAX_LINE_HINTS:
            seen_lines.add(line_no)
            line_hints.append(line_no)

    confirmation = (
        EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        if structural_counts
        else EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    )

    metadata: dict[str, str] = {}
    language = language_hint_for_path(normalized)
    if language:
        metadata["language_hint"] = language

    return StructuralTestFactEvidence(
        evidence_id=make_file_evidence_id(path=normalized, role="structural"),
        path=normalized,
        confirmation_level=confirmation,
        framework_hints=tuple(framework_hints),
        marker_counts=marker_counts,
        structural_counts=structural_counts,
        line_hints=tuple(line_hints),
        classification=classification_for_path(normalized),
        provenance=_provenance(
            normalized, configuration_fingerprint=configuration_fingerprint
        ),
        metadata=metadata,
    )
