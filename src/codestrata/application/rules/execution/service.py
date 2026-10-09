"""Launch catalog orchestration: YAML only, trusted extractors/operators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codestrata.application.rules.execution.executor import execute_launch_plan
from codestrata.application.rules.execution.planner import (
    CatalogEntry,
    LaunchExecutionPlan,
    plan_launch_catalog,
)
from codestrata.application.rules.execution.process_guard import IsolatedOutcome
from codestrata.application.rules.execution.projections import (
    dumps_launch_json,
    project_launch_html,
    project_launch_json,
    project_launch_sarif,
)
from codestrata.application.rules.execution.purpose import admit_execution_purpose
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.rules.execution_models import LaunchExecutionBody
from codestrata.domain.rules.operators.models import OperatorContext


class LaunchCatalogService:
    """Planner/executor for the YAML launch catalog.

    SharedRule.evaluate() is not used. Trusted Python extractors populate
    :class:`OperatorContext`; operators remain the E03.2 set.
    """

    def plan(
        self,
        entries: tuple[CatalogEntry, ...] | list[CatalogEntry],
        *,
        purpose: ExecutionPurpose,
        budgets: BudgetLimits | None = None,
    ) -> LaunchExecutionPlan:
        return plan_launch_catalog(entries, purpose=purpose, budgets=budgets)

    def execute(
        self,
        entries: tuple[CatalogEntry, ...] | list[CatalogEntry],
        context: OperatorContext,
        *,
        purpose: ExecutionPurpose,
        package_purpose: ExecutionPurpose | None = None,
        budgets: BudgetLimits | None = None,
        isolate: bool = True,
        cancel_requested: Callable[[], bool] | None = None,
        evidence_paths: dict[str, str] | None = None,
        isolate_fn: Callable[..., IsolatedOutcome] | None = None,
    ) -> LaunchExecutionBody:
        package = package_purpose or purpose
        admit_execution_purpose(package_purpose=package, requested_purpose=purpose)
        plan = self.plan(entries, purpose=purpose, budgets=budgets)
        return execute_launch_plan(
            plan,
            context,
            package_purpose=package,
            requested_purpose=purpose,
            budgets=budgets,
            isolate=isolate,
            cancel_requested=cancel_requested,
            evidence_paths=evidence_paths,
            isolate_fn=isolate_fn,
        )

    def project_json(self, body: LaunchExecutionBody) -> dict[str, Any]:
        return project_launch_json(body)

    def project_json_text(self, body: LaunchExecutionBody) -> str:
        return dumps_launch_json(body)

    def project_html(self, body: LaunchExecutionBody) -> str:
        return project_launch_html(body)

    def project_sarif(self, body: LaunchExecutionBody) -> dict[str, Any]:
        return project_launch_sarif(body)
