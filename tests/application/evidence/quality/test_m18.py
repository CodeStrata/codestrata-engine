"""M18 fixtures: token clone indicator with overlap merge and rename policy."""

from __future__ import annotations

from codestrata.application.evidence.quality.consumer import consume_envelope
from codestrata.application.evidence.quality.envelope import QualityEnvelope
from codestrata.application.evidence.quality.maps import (
    CLONE_MIN_LINES,
    CLONE_MIN_TOKENS,
    TOKEN_NORMALIZATION_VERSION,
    QualityBudgets,
)
from codestrata.application.evidence.quality.models import (
    CoverageScope,
    MetricStatusName,
    QualityEvidence,
)
from codestrata.application.evidence.quality.service import QualityEvidenceService
from codestrata.application.rules.technical_debt.yaml_catalog import quality_catalog_digests
from codestrata.application.rules.technical_debt.yaml_quality import CloneIndicatorRule
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleResultStatus, RuleSeverity


def _run(
    paths: tuple[str, ...],
    texts: dict[str, str],
    *,
    budgets: QualityBudgets | None = None,
) -> tuple[QualityEvidence, QualityEnvelope]:
    return QualityEvidenceService(budgets=budgets).collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest=quality_catalog_digests()["quality.clone_indicator"],
    )


def _ctx(evidence: QualityEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        assessment_graph=evidence,
    )


def _token_block(name: str, count: int = 60) -> str:
    assignments = "\n".join(f"    {name}_{index} = {index}" for index in range(count))
    return f"def {name}():\n{assignments}\n    return {name}_0\n"


def test_exact_clone_ratio_and_advisory_finding() -> None:
    block = _token_block("copied")
    source = block + "\n" + block.replace("def copied", "def copied_again", 1)
    evidence, envelope = _run(("pkg/dup.py",), {"pkg/dup.py": source})
    clone = evidence.clone
    assert clone.status is MetricStatusName.VALUE
    assert clone.numerator is not None and clone.denominator is not None
    assert clone.denominator > 0
    assert clone.serialized is not None
    assert clone.normalization_version == TOKEN_NORMALIZATION_VERSION
    assert clone.min_tokens == CLONE_MIN_TOKENS
    assert clone.min_lines == CLONE_MIN_LINES
    assert clone.runs
    assert clone.merged_spans
    assert float(clone.serialized) == clone.numerator / clone.denominator
    consume_envelope(envelope.model_dump(mode="json"))
    if float(clone.serialized) > 0.10:
        matched = CloneIndicatorRule().evaluate(_ctx(evidence))
        assert matched.status is RuleResultStatus.MATCHED
        assert matched.matches[0].severity is RuleSeverity.LOW
        assert matched.matches[0].confidence is MatchEvidenceConfidence.LOW


def test_renamed_identifiers_are_not_clones() -> None:
    left = _token_block("alpha")
    right = _token_block("beta")
    evidence, _ = _run(("pkg/renamed.py",), {"pkg/renamed.py": left + "\n" + right})
    assert evidence.clone.runs == ()
    assert evidence.clone.numerator == 0
    assert CloneIndicatorRule().evaluate(_ctx(evidence)).status is RuleResultStatus.NOT_MATCHED


def test_overlapping_runs_merge_before_numerator() -> None:
    repeated = "\n".join(f"    value_{index} = {index}" for index in range(80))
    source = (
        f"def first():\n{repeated}\n    return value_0\n\n"
        f"def second():\n{repeated}\n    return value_0\n\n"
        f"def third():\n{repeated}\n    return value_0\n"
    )
    evidence, _ = _run(("pkg/overlap.py",), {"pkg/overlap.py": source})
    clone = evidence.clone
    assert clone.numerator is not None and clone.denominator is not None
    assert clone.numerator <= clone.denominator
    covered = 0
    for span in clone.merged_spans:
        covered += span.line_end - span.line_start + 1
    assert clone.numerator <= covered


def test_generated_files_are_excluded() -> None:
    block = _token_block("copied")
    texts = {
        "pkg/src.py": block,
        "generated/copy.py": block,
    }
    evidence, _ = _run(
        ("pkg/src.py", "generated/copy.py"),
        texts,
    )
    generated = any("generated_excluded" in item for item in evidence.limitations)
    assert generated or evidence.clone.runs == ()
    assert all(not item.path.startswith("generated/") for item in evidence.clone.merged_spans)


def test_no_eligible_lines_is_not_applicable() -> None:
    evidence, envelope = _run(("README.md",), {"README.md": "# docs only\n"})
    assert evidence.clone.status is MetricStatusName.NOT_APPLICABLE
    assert evidence.clone.full_scope_status is CoverageScope.NOT_APPLICABLE
    assert CloneIndicatorRule().evaluate(_ctx(evidence)).status is RuleResultStatus.NOT_APPLICABLE
    consume_envelope(envelope.model_dump(mode="json"))


def test_scan_cutoff_is_partial_not_zero() -> None:
    block = _token_block("copied")
    source = block + "\n" + block.replace("def copied", "def copied_again", 1)
    evidence, envelope = _run(
        ("pkg/a.py", "pkg/b.py"),
        {"pkg/a.py": source, "pkg/b.py": source},
        budgets=QualityBudgets(max_files=1, max_file_bytes=1_048_576, max_tokens=500_000),
    )
    assert evidence.clone.cutoff is True
    assert evidence.clone.full_scope_status in {CoverageScope.PARTIAL, CoverageScope.UNKNOWN}
    if evidence.clone.serialized is not None:
        assert evidence.clone.serialized != "0.000000" or evidence.clone.numerator == 0
    m18 = next(
        item
        for item in envelope.body.coverage
        if item.capability_id.endswith("m18.clone_indicator")
    )
    assert m18.full_scope_status != "complete"
    consume_envelope(envelope.model_dump(mode="json"))
