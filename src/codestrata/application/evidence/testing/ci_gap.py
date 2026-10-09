"""M21 declared test/coverage invocation gaps from M03 CI observations."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.inventory.ci import observe_ci
from codestrata.application.evidence.inventory.models import (
    CiDocumentObservation,
    CiInvocationObservation,
    SupportKind,
)
from codestrata.application.evidence.repository_testing.build_and_frameworks import (
    collect_build_and_framework_facts,
)
from codestrata.application.evidence.repository_testing.coverage_config import (
    collect_coverage_facts,
)
from codestrata.application.evidence.repository_testing.discovery import (
    discover_ci_paths,
    discover_coverage_paths,
)
from codestrata.application.evidence.testing.capability import CI_GAP_FORMULA_VERSION
from codestrata.application.evidence.testing.models import (
    CiGapMetric,
    CiGapRecord,
    CoverageScope,
    DeclaredCapability,
    GapStatus,
    InvocationWitness,
    MetricStatusName,
)
from codestrata.application.evidence.testing.paths import normalize_relative_path
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    TestFrameworkFamily,
)

_TEST_FRAMEWORKS = frozenset(
    {
        TestFrameworkFamily.PYTEST,
        TestFrameworkFamily.UNITTEST,
        TestFrameworkFamily.JUNIT,
        TestFrameworkFamily.JUNIT_JUPITER,
        TestFrameworkFamily.TESTNG,
        TestFrameworkFamily.JEST,
        TestFrameworkFamily.VITEST,
        TestFrameworkFamily.MOCHA,
        TestFrameworkFamily.PLAYWRIGHT,
        TestFrameworkFamily.CYPRESS,
        TestFrameworkFamily.SUREFIRE,
        TestFrameworkFamily.FAILSAFE,
        TestFrameworkFamily.XUNIT,
        TestFrameworkFamily.NUNIT,
        TestFrameworkFamily.MSTEST,
        TestFrameworkFamily.PHPUNIT,
    }
)
_COVERAGE_FRAMEWORKS = frozenset(
    {
        TestFrameworkFamily.COVERAGE_PY,
        TestFrameworkFamily.JACOCO,
        TestFrameworkFamily.NYC,
        TestFrameworkFamily.ISTANBUL,
        TestFrameworkFamily.COVERLET,
    }
)
_NPM_SCRIPT = re.compile(
    r'"test"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_SCRIPT_CMD = re.compile(
    r"(?:^|[\\/\s])(?:\.?/?[\w./-]+\.(?:sh|bash|ps1|bat)\b|\bmake\b)",
    re.IGNORECASE,
)
_SCRIPT_BODY = re.compile(
    r"\b(?:pytest|mvn\s+test|gradlew\s+test|npm\s+test|yarn\s+test|vitest|jest)\b",
    re.IGNORECASE,
)
_COVERAGE_BODY = re.compile(
    r"\b(?:--cov|coverage\b|nyc\b|jacoco|c8\b)\b",
    re.IGNORECASE,
)


def _witness(item: CiInvocationObservation) -> InvocationWitness:
    return InvocationWitness(
        path=item.path,
        line=item.line,
        job=item.job,
        literal_command=item.literal_command,
        condition=item.condition,
        tool_category=item.tool_category,
        parser_rule=item.parser_rule,
        unresolved=item.unresolved,
        unresolved_reason=item.unresolved_reason,
    )


def _declared_capabilities(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[DeclaredCapability, ...]:
    texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
    paths = [normalize_relative_path(path) for path in relative_paths]
    coverage_paths = tuple(path for path, _kind in discover_coverage_paths(paths))
    frameworks, _builds = collect_build_and_framework_facts(file_texts=texts)
    coverage_facts = collect_coverage_facts(
        (*coverage_paths, *paths),
        file_texts=texts,
    )
    declared: dict[str, DeclaredCapability] = {}
    for item in frameworks:
        if item.framework in _TEST_FRAMEWORKS:
            kind = "test"
        elif item.framework in _COVERAGE_FRAMEWORKS:
            kind = "coverage"
        else:
            continue
        key = f"{kind}:{item.framework.value}:{item.path}"
        declared[key] = DeclaredCapability(
            capability_id=key,
            kind=kind,
            tool=item.framework.value,
            path=item.path,
            detail=item.detail or item.basis.value,
        )
    for coverage in coverage_facts:
        if coverage.fact_type is CoverageFactType.COVERAGE_REPORT_REFERENCE:
            # A report file is not 0% and is not a declared capability gap.
            continue
        tool = coverage.tool.value if coverage.tool is not None else "coverage"
        key = f"coverage:{tool}:{coverage.path}"
        declared[key] = DeclaredCapability(
            capability_id=key,
            kind="coverage",
            tool=tool,
            path=coverage.path,
            detail=coverage.detail or coverage.fact_type.value,
        )
    for path, text in texts.items():
        name = PurePosixPath(path).name.lower()
        if name == "package.json":
            match = _NPM_SCRIPT.search(text)
            if match:
                key = f"test:npm-script:{path}"
                declared[key] = DeclaredCapability(
                    capability_id=key,
                    kind="test",
                    tool="npm-script",
                    path=path,
                    detail=match.group(1),
                )
    return tuple(sorted(declared.values(), key=lambda item: item.capability_id))


def _ci_complete(documents: Sequence[CiDocumentObservation]) -> bool:
    if not documents:
        return False
    return all(
        item.support is SupportKind.STRUCTURAL and item.parse_status in {"ok", "OK"}
        for item in documents
    ) and all(item.provider == "github-actions" for item in documents)


def _inspect_delegated(
    command: str,
    file_texts: Mapping[str, str],
) -> tuple[bool, bool]:
    """Return (resolved_test, resolved_coverage) if a script body was inspected."""

    tokens = command.strip().split()
    if not tokens:
        return False, False
    script: str | None = None
    if tokens[0] in {"./scripts/ci.sh", "scripts/ci.sh"} or tokens[0].endswith(".sh"):
        script = tokens[0].lstrip("./")
    elif len(tokens) >= 2 and tokens[0] == "bash":
        script = tokens[1].lstrip("./")
    if script is None:
        return False, False
    normalized = normalize_relative_path(script)
    body = file_texts.get(normalized)
    if body is None:
        return False, False
    return bool(_SCRIPT_BODY.search(body)), bool(_COVERAGE_BODY.search(body))


def collect_ci_gap_metric(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    notes: list[str],
) -> CiGapMetric:
    texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
    paths = [normalize_relative_path(path) for path in relative_paths]
    declared = _declared_capabilities(relative_paths=paths, file_texts=texts)
    documents = observe_ci(paths, texts)
    ci_paths = discover_ci_paths(paths)
    invocations = tuple(item for document in documents for item in document.invocations)
    witnesses = tuple(_witness(item) for item in invocations)

    if not declared:
        return CiGapMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            proven_absent=0,
            full_scope_status=CoverageScope.NOT_APPLICABLE,
            reason="no_declared_test_or_coverage_capability",
            formula_version=CI_GAP_FORMULA_VERSION,
            coverage_percent=None,
            declared=(),
            ci_documents=len(documents),
        )
    if not documents and not ci_paths:
        notes.append("no_ci_applicability")
        return CiGapMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            proven_absent=0,
            invoked=0,
            full_scope_status=CoverageScope.NOT_APPLICABLE,
            reason="no_ci_applicability",
            formula_version=CI_GAP_FORMULA_VERSION,
            coverage_percent=None,
            declared=declared,
            ci_documents=0,
        )

    complete = _ci_complete(documents)
    if not complete:
        notes.append("external_workflow_or_partial_ci")

    test_invoked = False
    coverage_invoked = False
    test_conditional_only = False
    coverage_conditional_only = False
    delegated_unresolved = False
    conditional_unresolved = False

    test_hits = 0
    coverage_hits = 0
    test_conditional_hits = 0
    coverage_conditional_hits = 0

    for item in invocations:
        resolved_test, resolved_coverage = (False, False)
        looks_delegated = bool(
            item.unresolved_reason == "delegated_script_body_not_inspected"
            or (item.literal_command and _SCRIPT_CMD.search(item.literal_command))
        )
        if looks_delegated and item.literal_command:
            resolved_test, resolved_coverage = _inspect_delegated(
                item.literal_command, texts
            )
            if not resolved_test and not resolved_coverage:
                delegated_unresolved = True
        category = item.tool_category
        if resolved_test:
            category = "test"
        if resolved_coverage:
            category = "coverage"
        if category == "test":
            test_hits += 1
            if item.condition:
                test_conditional_hits += 1
            else:
                test_invoked = True
        elif category == "coverage":
            coverage_hits += 1
            if item.condition:
                coverage_conditional_hits += 1
            else:
                coverage_invoked = True
        if item.condition and item.unresolved:
            conditional_unresolved = True

    if test_hits and not test_invoked:
        test_conditional_only = True
    if coverage_hits and not coverage_invoked:
        coverage_conditional_only = True

    gaps: list[CiGapRecord] = []
    for capability in declared:
        invoked = test_invoked if capability.kind == "test" else coverage_invoked
        conditional_only = (
            test_conditional_only if capability.kind == "test" else coverage_conditional_only
        )
        related = tuple(
            witness
            for witness in witnesses
            if witness.tool_category == capability.kind
            or (witness.literal_command and capability.tool in (witness.literal_command or ""))
        )
        if invoked:
            status = GapStatus.INVOKED
            reason = "declared_and_invoked"
        elif not complete or delegated_unresolved:
            status = GapStatus.UNKNOWN
            reason = (
                "delegated_script_body_not_inspected"
                if delegated_unresolved
                else "external_workflow_not_inspected"
            )
        elif conditional_only or conditional_unresolved:
            status = GapStatus.UNKNOWN
            reason = "conditional_job_uncertainty"
        else:
            status = GapStatus.PROVEN_ABSENT
            reason = "declared_without_static_invocation"
        gaps.append(
            CiGapRecord(
                gap_id=f"gap:{capability.capability_id}",
                capability_id=capability.capability_id,
                kind=capability.kind,
                tool=capability.tool,
                status=status,
                reason=reason,
                checked_scope=(
                    "github-actions.structural" if complete else "partial_or_unsupported_ci"
                ),
                invocations=related,
            )
        )

    proven = sum(1 for item in gaps if item.status is GapStatus.PROVEN_ABSENT)
    unknown = sum(1 for item in gaps if item.status is GapStatus.UNKNOWN)
    invoked_count = sum(1 for item in gaps if item.status is GapStatus.INVOKED)
    if proven and unknown == 0 and complete:
        metric_status = MetricStatusName.VALUE
        scope = CoverageScope.COMPLETE
        reason = "proven_absent_invocation"
    elif unknown:
        metric_status = MetricStatusName.UNKNOWN
        scope = CoverageScope.UNKNOWN
        reason = next(
            (item.reason for item in gaps if item.status is GapStatus.UNKNOWN),
            "ci_scope_unknown",
        )
        notes.append(reason)
    elif proven:
        metric_status = MetricStatusName.UNKNOWN
        scope = CoverageScope.PARTIAL
        reason = "partial_ci_cannot_prove_all_gaps"
    else:
        metric_status = MetricStatusName.VALUE
        scope = CoverageScope.COMPLETE
        reason = "declared_and_invoked"

    gaps.sort(key=lambda item: item.gap_id)
    return CiGapMetric(
        status=metric_status,
        proven_absent=proven,
        unknown=unknown,
        invoked=invoked_count,
        full_scope_status=scope,
        reason=reason,
        formula_version=CI_GAP_FORMULA_VERSION,
        coverage_percent=None,
        declared=declared,
        gaps=tuple(gaps),
        ci_documents=len(documents),
    )


__all__ = ["collect_ci_gap_metric"]
