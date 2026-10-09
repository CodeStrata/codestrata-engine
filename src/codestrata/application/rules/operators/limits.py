"""Load E03.2 operator limits from the E01.1 launch ratification."""

from __future__ import annotations

from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.rules.operators.models import OperatorLimits


def operator_limits_from_ratification() -> OperatorLimits:
    budgets = load_launch_ratification().budgets
    return OperatorLimits(
        graph_max_depth=budgets.graph_max_depth,
        graph_max_visited_nodes=budgets.graph_max_visited_nodes,
        graph_max_visited_edges=budgets.graph_max_visited_edges,
        regex_max_steps=budgets.regex_max_steps,
        regex_timeout_milliseconds=budgets.regex_match_timeout_milliseconds,
    )
