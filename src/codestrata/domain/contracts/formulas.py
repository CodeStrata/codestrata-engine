"""Independent formula helpers for ratified E01.1 measurements.

These functions are the pre-analyzer expected-value implementations. Analyzer
stories must match these results; they must not become a second score.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal

from codestrata.domain.contracts.enums import MetricStatus, OutcomeMovement
from codestrata.domain.contracts.models import MetricComputation


def serialize_ratio(value: Decimal) -> str:
    """Normalized six-fractional-place decimal for derived ratios."""

    quantized = value.quantize(Decimal("0.000000"), rounding=ROUND_HALF_EVEN)
    return format(quantized, "f")


def ratio(
    numerator: int,
    denominator: int,
    *,
    empty_status: MetricStatus = MetricStatus.NOT_APPLICABLE,
) -> MetricComputation:
    """Publish numerator/denominator; empty denominator uses empty_status."""

    if denominator < 0 or numerator < 0:
        raise ValueError("counts must be nonnegative")
    if denominator == 0:
        return MetricComputation(
            status=empty_status,
            numerator=numerator,
            denominator=denominator,
            value=None,
            serialized=None,
        )
    value = Decimal(numerator) / Decimal(denominator)
    return MetricComputation(
        status=MetricStatus.VALUE,
        numerator=numerator,
        denominator=denominator,
        value=value,
        serialized=serialize_ratio(value),
    )


def unknown_denominator() -> MetricComputation:
    return MetricComputation(
        status=MetricStatus.UNKNOWN,
        numerator=None,
        denominator=None,
        value=None,
        serialized=None,
        reason="unknown_denominator",
    )


def m06_external_edge_ratio(
    edges: Sequence[tuple[str, str, str, str]],
) -> MetricComputation:
    """File import-edge view.

    Each item is (source_file, target_file, source_component, target_component).
    Duplicate (source_file, target_file) pairs are excluded. Unmapped endpoints
    are excluded from both numerator and denominator and counted separately by
    the caller.
    """

    distinct: dict[tuple[str, str], tuple[str, str]] = {}
    for source, target, src_comp, tgt_comp in edges:
        key = (source, target)
        if key not in distinct:
            distinct[key] = (src_comp, tgt_comp)
    eligible = [comps for comps in distinct.values() if comps[0] and comps[1]]
    if not eligible:
        return ratio(0, 0)
    external = sum(1 for src, tgt in eligible if src != tgt)
    return ratio(external, len(eligible))


def m09_centrality(
    node: str,
    universe: Sequence[str],
    incoming_neighbors: Sequence[str],
) -> MetricComputation:
    """centrality(v) = |{u in V: u != v and edge u->v}| / max(1, |V|-1)."""

    v = set(universe)
    if node not in v:
        return MetricComputation(
            status=MetricStatus.UNKNOWN,
            reason="node_outside_universe",
        )
    distinct = {u for u in incoming_neighbors if u in v and u != node}
    denom = max(1, len(v) - 1)
    return ratio(len(distinct), denom)


def m12_resolution_coverage(
    eligible_declaration_ids: Sequence[str] | None,
    fully_resolved_ids: Sequence[str],
) -> MetricComputation:
    """Resolved IDs / eligible IDs in the same scope; unknown denom is UNKNOWN."""

    if eligible_declaration_ids is None:
        return unknown_denominator()
    unique_eligible = list(dict.fromkeys(eligible_declaration_ids))
    if not unique_eligible:
        return ratio(0, 0)
    resolved = {item for item in fully_resolved_ids if item in unique_eligible}
    return ratio(len(resolved), len(unique_eligible))


def nearest_rank_percentile(values: Sequence[int], p: float) -> MetricComputation:
    """Percentile operator v1: rank = max(1, ceil(p*N)) on sorted N values."""

    if not values:
        return MetricComputation(status=MetricStatus.NOT_APPLICABLE, reason="empty_input")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be in [0, 1]")
    ordered = sorted(values)
    rank = max(1, math.ceil(p * len(ordered)))
    return MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(ordered[rank - 1]),
        serialized=str(ordered[rank - 1]),
        numerator=rank,
        denominator=len(ordered),
    )


def m22_hotspot_value(complexity_sum: int, changed_lines: int) -> int:
    if complexity_sum < 0 or changed_lines < 0:
        raise ValueError("hotspot contributors must be nonnegative")
    return complexity_sum * changed_lines


def m22_rank_order(
    records: Sequence[tuple[str, int, bool]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (complete_ranked_ids, partial_unknown_ids).

    records: (component_id, ranking_value, complete).
    Complete: descending value, then component_id ascending.
    Partial/UNKNOWN: subject ID ascending, never mixed into complete ranking.
    """

    complete = [(cid, value) for cid, value, ok in records if ok]
    partial = tuple(sorted(cid for cid, _value, ok in records if not ok))
    complete.sort(key=lambda item: (-item[1], item[0]))
    return tuple(cid for cid, _value in complete), partial


def m25_ownership(
    contributor_lines: Mapping[str, int],
) -> MetricComputation:
    """Largest contributor share and contributors-to-50% over attributable lines."""

    attributable = sum(max(0, n) for n in contributor_lines.values())
    if attributable == 0:
        return MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            denominator=0,
            reason="zero_attributable_churn",
        )
    ordered = sorted(
        contributor_lines.items(),
        key=lambda item: (-item[1], item[0]),
    )
    largest = ordered[0][1]
    share = ratio(largest, attributable)
    cumulative = 0
    needed = 0
    for _identity, lines in ordered:
        needed += 1
        cumulative += lines
        if cumulative * 2 >= attributable:
            break
    return share.model_copy(update={"extra": {"contributors_to_50_percent": needed}})


def m26_jaccard(cochanged: int, union: int) -> MetricComputation:
    if union == 0:
        return ratio(0, 0)
    return ratio(cochanged, union)


def m23_staleness_days(
    evaluation_time_unix: int | None,
    publication_time_unix: int | None,
) -> MetricComputation:
    if evaluation_time_unix is None or publication_time_unix is None:
        return MetricComputation(status=MetricStatus.UNKNOWN, reason="missing_timestamp")
    if publication_time_unix > evaluation_time_unix:
        return MetricComputation(status=MetricStatus.UNKNOWN, reason="future_or_invalid_timestamp")
    days = (evaluation_time_unix - publication_time_unix) // 86400
    return MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(days),
        serialized=str(days),
    )


def m29_high_churn(changed_lines: int, p90_changed_lines: int) -> bool:
    """High-churn iff changed lines are strictly above the window p90 among >0 churn."""

    return changed_lines > 0 and changed_lines > p90_changed_lines


def m29_high_centrality(centrality: Decimal, p90_centrality: Decimal) -> bool:
    """High-centrality iff centrality is strictly above universe p90."""

    return centrality > p90_centrality


def m29_concern_class(*, high_churn: bool, high_centrality: bool) -> str:
    if high_churn and high_centrality:
        return "high_churn_and_centrality"
    if high_churn:
        return "high_churn"
    if high_centrality:
        return "high_centrality"
    return "ordinary"


def m29_rank_key(
    subject_id: str,
    *,
    high_churn: bool,
    high_centrality: bool,
    changed_lines: int,
    centrality: Decimal,
) -> tuple[int, int, Decimal, str]:
    """Lexicographic ranking without a weighted composite score.

    Class order: both, churn-only, centrality-only, ordinary. Within class:
    more changed lines, then higher centrality, then stable subject ID.
    """

    class_rank = {
        "high_churn_and_centrality": 0,
        "high_churn": 1,
        "high_centrality": 2,
        "ordinary": 3,
    }[m29_concern_class(high_churn=high_churn, high_centrality=high_centrality)]
    return (class_rank, -changed_lines, -centrality, subject_id)


def m30_classify(
    *,
    driver_set_empty: bool,
    comparable: bool,
    required_unknown: bool,
    favorable: int,
    unfavorable: int,
) -> OutcomeMovement:
    if driver_set_empty:
        return OutcomeMovement.NOT_APPLICABLE
    if not comparable or required_unknown:
        return OutcomeMovement.INSUFFICIENT
    if unfavorable > 0 and favorable > 0:
        return OutcomeMovement.MIXED
    if unfavorable > 0:
        return OutcomeMovement.DETERIORATED
    if favorable > 0:
        return OutcomeMovement.IMPROVED
    return OutcomeMovement.STABLE
