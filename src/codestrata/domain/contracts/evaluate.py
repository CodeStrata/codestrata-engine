"""Map E01.1 formula fixtures to independent computations."""

from __future__ import annotations

from decimal import Decimal

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.formulas import (
    m06_external_edge_ratio,
    m09_centrality,
    m12_resolution_coverage,
    m22_hotspot_value,
    m22_rank_order,
    m23_staleness_days,
    m25_ownership,
    m26_jaccard,
    m29_concern_class,
    m29_high_centrality,
    m29_high_churn,
    m30_classify,
)
from codestrata.domain.contracts.models import MetricComputation


def evaluate_formula_fixture(fixture_id: str) -> MetricComputation:
    if fixture_id == "M06-external-ratio-mixed":
        return m06_external_edge_ratio(
            (
                ("f1", "f2", "A", "A"),
                ("f1", "f3", "A", "B"),
                ("f2", "f3", "A", "B"),
            )
        )
    if fixture_id == "M06-duplicate-edges":
        return m06_external_edge_ratio(
            (
                ("f1", "f3", "A", "B"),
                ("f1", "f3", "A", "B"),
                ("f1", "f2", "A", "A"),
            )
        )
    if fixture_id == "M06-zero-edges":
        return m06_external_edge_ratio(())
    if fixture_id == "M09-diamond":
        return m09_centrality("c", ("a", "b", "c", "d"), ("a", "b"))
    if fixture_id == "M09-singleton":
        return m09_centrality("a", ("a",), ())
    if fixture_id == "M09-self-loop":
        return m09_centrality("a", ("a", "b"), ("a",))
    if fixture_id == "M12-partial":
        return m12_resolution_coverage(("d1", "d2", "d3", "d4"), ("d1", "d2", "d3"))
    if fixture_id == "M12-none-resolved":
        return m12_resolution_coverage(("d1", "d2", "d3", "d4"), ())
    if fixture_id == "M12-zero-eligible":
        return m12_resolution_coverage((), ())
    if fixture_id == "M12-unknown-denom":
        return m12_resolution_coverage(None, ("d1",))
    if fixture_id == "M22-tie-break":
        ranked, partial = m22_rank_order(
            (
                ("beta", m22_hotspot_value(10, 3), True),
                ("alpha", m22_hotspot_value(10, 3), True),
                ("gamma", m22_hotspot_value(10, 2), True),
                ("omega", m22_hotspot_value(99, 99), False),
            )
        )
        return MetricComputation(
            status=MetricStatus.VALUE,
            extra={"ranked": list(ranked), "partial": list(partial)},
        )
    if fixture_id == "M25-two-contributors":
        return m25_ownership({"alice": 70, "bob": 30})
    if fixture_id == "M25-zero":
        return m25_ownership({"alice": 0, "bob": 0})
    if fixture_id == "M26-jaccard":
        return m26_jaccard(3, 5)
    if fixture_id == "M23-staleness":
        return m23_staleness_days(1_700_000_000, 1_700_000_000 - 800 * 86400)
    if fixture_id == "M23-missing":
        return m23_staleness_days(1_700_000_000, None)
    if fixture_id == "M29-churn-only":
        high_churn = m29_high_churn(150, 100)
        high_centrality = m29_high_centrality(Decimal("0.20"), Decimal("0.25"))
        return MetricComputation(
            status=MetricStatus.VALUE,
            extra={
                "class": m29_concern_class(high_churn=high_churn, high_centrality=high_centrality)
            },
        )
    if fixture_id == "M30-empty-drivers":
        movement = m30_classify(
            driver_set_empty=True,
            comparable=True,
            required_unknown=False,
            favorable=0,
            unfavorable=0,
        )
        return MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            extra={"movement": movement.value},
        )
    if fixture_id == "M30-improved":
        movement = m30_classify(
            driver_set_empty=False,
            comparable=True,
            required_unknown=False,
            favorable=1,
            unfavorable=0,
        )
        return MetricComputation(
            status=MetricStatus.VALUE,
            extra={"movement": movement.value},
        )
    if fixture_id == "M30-mixed":
        movement = m30_classify(
            driver_set_empty=False,
            comparable=True,
            required_unknown=False,
            favorable=1,
            unfavorable=1,
        )
        return MetricComputation(
            status=MetricStatus.VALUE,
            extra={"movement": movement.value},
        )
    if fixture_id == "M30-insufficient":
        movement = m30_classify(
            driver_set_empty=False,
            comparable=True,
            required_unknown=True,
            favorable=2,
            unfavorable=0,
        )
        return MetricComputation(
            status=MetricStatus.UNKNOWN,
            extra={"movement": movement.value},
        )
    if fixture_id == "M33-budget-failure":
        return MetricComputation(
            status=MetricStatus.ERROR,
            reason="hard_deadline_exceeded",
        )
    raise KeyError(fixture_id)
