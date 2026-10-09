"""Map bounded operator results onto contract PASS/FAIL/UNKNOWN/ERROR."""

from __future__ import annotations

from codestrata.domain.contracts.enums import CoverageState, MetricStatus, ResultStatus
from codestrata.domain.rules.operators.models import OperatorResult, Truth


def interpret_operator_result(result: OperatorResult) -> ResultStatus:
    """FAIL is a evidenced violation; ERROR is processing/budget failure.

    YAML conditions encode the violating predicate. TRUE therefore FAIL,
    FALSE therefore PASS. A cutoff never proves absence.
    """

    if result.error:
        return ResultStatus.ERROR
    if result.metric is not None and result.truth is None:
        if result.metric.status is MetricStatus.ERROR:
            return ResultStatus.ERROR
        if result.metric.status is MetricStatus.NOT_APPLICABLE:
            return ResultStatus.NOT_APPLICABLE
        if result.metric.status is MetricStatus.UNKNOWN:
            return ResultStatus.UNKNOWN
        return ResultStatus.UNKNOWN
    if result.cutoff and result.truth is not Truth.TRUE:
        return ResultStatus.UNKNOWN
    if result.truth is Truth.TRUE:
        return ResultStatus.FAIL
    if result.truth is Truth.FALSE:
        return ResultStatus.PASS
    return ResultStatus.UNKNOWN


def coverage_for_scope(
    *,
    enabled: bool,
    suppressed: bool,
    status: ResultStatus | None,
) -> CoverageState:
    if not enabled:
        return CoverageState.DISABLED
    if suppressed:
        return CoverageState.SUPPRESSED
    if status is ResultStatus.ERROR:
        return CoverageState.ERROR
    if status is ResultStatus.NOT_APPLICABLE:
        return CoverageState.NOT_APPLICABLE
    if status is ResultStatus.UNKNOWN:
        return CoverageState.UNKNOWN
    return CoverageState.COMPLETE
