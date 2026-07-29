"""Golden equivalence helpers for incremental-versus-full comparison."""

from __future__ import annotations

from codestrata.application.incremental.equivalence import (
    AssessmentEquivalenceResult,
    AssessmentSemanticComparator,
    CompleteAssessmentArtifacts,
    artifacts_from_assessment_result,
)


def compare_assessment_results(
    incremental_result: object,
    full_result: object,
    *,
    max_differences: int = 100,
) -> AssessmentEquivalenceResult:
    """Compare two AssessmentCommandResult-like objects semantically."""

    left = (
        incremental_result
        if isinstance(incremental_result, CompleteAssessmentArtifacts)
        else artifacts_from_assessment_result(incremental_result)
    )
    right = (
        full_result
        if isinstance(full_result, CompleteAssessmentArtifacts)
        else artifacts_from_assessment_result(full_result)
    )
    return AssessmentSemanticComparator(max_differences=max_differences).compare(
        left, right
    )


def assert_semantically_equivalent(
    incremental_result: object,
    full_result: object,
) -> AssessmentEquivalenceResult:
    result = compare_assessment_results(incremental_result, full_result)
    assert result.equivalent, result.differences
    return result
