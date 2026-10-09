"""E01.1 launch budgets for planner/executor enforcement."""

from __future__ import annotations

from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.rules.deadlines import budgets_require_process_cap
from codestrata.domain.rules.operators.models import OperatorLimits


def execution_budgets() -> BudgetLimits:
    budgets = load_launch_ratification().budgets
    budgets_require_process_cap(budgets)
    return budgets


def operator_limits_from_budgets(budgets: BudgetLimits | None = None) -> OperatorLimits:
    bound = budgets or execution_budgets()
    return OperatorLimits(
        graph_max_depth=bound.graph_max_depth,
        graph_max_visited_nodes=bound.graph_max_visited_nodes,
        graph_max_visited_edges=bound.graph_max_visited_edges,
        regex_max_steps=bound.regex_max_steps,
        regex_timeout_milliseconds=bound.regex_match_timeout_milliseconds,
    )


def wall_seconds_for_workload(budgets: BudgetLimits, *, eligible_files: int) -> int:
    if eligible_files <= 10_000:
        return budgets.wall_seconds_tier_10k
    return budgets.wall_seconds_tier_100k


def memory_rss_for_workload(budgets: BudgetLimits, *, eligible_files: int) -> int:
    if eligible_files <= 10_000:
        return budgets.max_memory_rss_bytes_tier_10k
    return budgets.max_memory_rss_bytes_tier_100k
