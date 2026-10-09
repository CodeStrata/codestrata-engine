"""Launch catalog planner/executor, budgets, cancellation and projections."""

from __future__ import annotations

from codestrata.application.rules.execution.budgets import (
    execution_budgets,
    memory_rss_for_workload,
    operator_limits_from_budgets,
    wall_seconds_for_workload,
)
from codestrata.application.rules.execution.executor import execute_launch_plan
from codestrata.application.rules.execution.planner import (
    CatalogCompileError,
    CatalogEntry,
    LaunchExecutionPlan,
    PlannedRule,
    compile_catalog_entry,
    plan_launch_catalog,
)
from codestrata.application.rules.execution.process_guard import (
    IsolatedOutcome,
    run_hang_until_killed,
    run_isolated_evaluation,
)
from codestrata.application.rules.execution.projections import (
    dumps_launch_json,
    project_launch_html,
    project_launch_json,
    project_launch_sarif,
)
from codestrata.application.rules.execution.purpose import (
    PurposeAdmissionError,
    admit_execution_purpose,
)
from codestrata.application.rules.execution.service import LaunchCatalogService

__all__ = [
    "CatalogCompileError",
    "CatalogEntry",
    "IsolatedOutcome",
    "LaunchCatalogService",
    "LaunchExecutionPlan",
    "PlannedRule",
    "PurposeAdmissionError",
    "admit_execution_purpose",
    "compile_catalog_entry",
    "dumps_launch_json",
    "execute_launch_plan",
    "execution_budgets",
    "memory_rss_for_workload",
    "operator_limits_from_budgets",
    "plan_launch_catalog",
    "project_launch_html",
    "project_launch_json",
    "project_launch_sarif",
    "run_hang_until_killed",
    "run_isolated_evaluation",
    "wall_seconds_for_workload",
]
