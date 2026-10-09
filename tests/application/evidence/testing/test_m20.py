"""M20 fixtures: skipped/disabled tests with conditional vs dynamic distinction."""

from __future__ import annotations

from codestrata.application.evidence.testing.consumer import consume_envelope
from codestrata.application.evidence.testing.envelope import TestingEnvelope
from codestrata.application.evidence.testing.models import (
    MetricStatusName,
    SkipKind,
    TestingEvidence,
)
from codestrata.application.evidence.testing.service import TestingEvidenceService
from codestrata.application.rules.testing.yaml_catalog import (
    testing_catalog_digests as catalog_digests,
)
from codestrata.application.rules.testing.yaml_testing import DisabledTestsRule
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
        catalog_digest=catalog_digests()["testing.disabled"],
    )


def _ctx(evidence: TestingEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python", "java", "javascript")),
        assessment_graph=evidence,
    )


def test_explicit_disabled_with_static_reason() -> None:
    source = "\n".join(
        (
            "import pytest",
            "",
            "@pytest.mark.skip(reason='flaky network')",
            "def test_remote():",
            "    assert True",
            "",
        )
    )
    evidence, envelope = _run(("tests/test_skip.py",), {"tests/test_skip.py": source})
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.skipped.status is MetricStatusName.VALUE
    assert evidence.skipped.explicit_disabled == 1
    record = next(
        item for item in evidence.skipped.records if item.kind is SkipKind.EXPLICIT_DISABLED
    )
    assert record.reason == "flaky network"
    assert record.annotation.endswith("skip")
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW
    assert result.matches[0].evidence[0].line_start == record.span.line_start


def test_enabled_test_is_not_disabled() -> None:
    source = "def test_ok():\n    assert True\n"
    evidence, _ = _run(("tests/test_ok.py",), {"tests/test_ok.py": source})
    assert evidence.skipped.explicit_disabled == 0
    assert evidence.skipped.enabled >= 1
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_conditional_skipif_is_not_unconditional_disabled() -> None:
    source = "\n".join(
        (
            "import sys",
            "import pytest",
            "",
            "@pytest.mark.skipif(sys.platform == 'win32', reason='windows')",
            "def test_posix():",
            "    assert True",
            "",
        )
    )
    evidence, _ = _run(("tests/test_cond.py",), {"tests/test_cond.py": source})
    assert evidence.skipped.explicit_disabled == 0
    assert evidence.skipped.conditional == 1
    record = next(item for item in evidence.skipped.records if item.kind is SkipKind.CONDITIONAL)
    assert record.static_condition is not None
    assert "sys.platform" in record.static_condition
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_dynamic_skip_condition_is_unknown_eligibility() -> None:
    source = "\n".join(
        (
            "import pytest",
            "",
            "def maybe():",
            "    return True",
            "",
            "@pytest.mark.skipif(maybe(), reason='dynamic')",
            "def test_maybe():",
            "    assert True",
            "",
        )
    )
    evidence, _ = _run(("tests/test_dyn.py",), {"tests/test_dyn.py": source})
    assert evidence.skipped.explicit_disabled == 0
    assert evidence.skipped.unknown_eligibility == 1
    record = next(
        item for item in evidence.skipped.records if item.kind is SkipKind.UNKNOWN_ELIGIBILITY
    )
    assert record.static_condition is None
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_unsupported_decorator_is_not_disabled() -> None:
    source = "\n".join(
        (
            "def flaky(fn):",
            "    return fn",
            "",
            "@flaky",
            "def test_marked():",
            "    assert True",
            "",
        )
    )
    evidence, _ = _run(("tests/test_flaky.py",), {"tests/test_flaky.py": source})
    assert evidence.skipped.explicit_disabled == 0
    assert evidence.skipped.unsupported_decorator == 1
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_test_deletion_is_not_a_skip() -> None:
    present = {
        "tests/test_keep.py": "def test_keep():\n    assert True\n",
        "tests/test_gone.py": (
            "import pytest\n\n@pytest.mark.skip\ndef test_gone():\n    assert False\n"
        ),
    }
    with_skip, _ = _run(tuple(present), present)
    assert with_skip.skipped.explicit_disabled == 1
    deleted = {"tests/test_keep.py": present["tests/test_keep.py"]}
    after, _ = _run(("tests/test_keep.py",), deleted)
    assert after.skipped.explicit_disabled == 0
    assert after.skipped.enabled >= 1


def test_java_disabled_and_js_skip() -> None:
    texts = {
        "src/test/java/pkg/AlphaTest.java": (
            "class AlphaTest {\n  @Disabled(\"until fix\")\n  @Test void gone() {}\n"
            "  @Test void ok() {}\n}\n"
        ),
        "src/alpha.test.js": "test.skip('offline', () => {});\ntest('ok', () => {});\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    assert evidence.skipped.explicit_disabled >= 2
    result = DisabledTestsRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
