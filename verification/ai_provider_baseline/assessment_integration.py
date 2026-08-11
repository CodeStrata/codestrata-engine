"""Characterize the assess/Modernization Advisor integration point.

Confirms — structurally, via AST — that ``AiEnrichmentService.run()`` calls
``self._provider.invoke(`` exactly once, and that the assess application
layer calls ``service.run(`` exactly once per AI stage attempt. This mirrors
the "Inspect source files structurally (AST or text)" approach requested for
Slice 11.1 rather than constructing the full assess domain-object graph.
"""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.ai_provider_baseline.models import CheckResult


def _find_method(tree: ast.Module, class_name: str, method_name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    return None


def _count_attribute_calls(node: ast.AST, attribute_name: str) -> int:
    count = 0
    for inner in ast.walk(node):
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == attribute_name
        ):
            count += 1
    return count


def check_enrichment_service_invokes_provider_exactly_once(source_root: Path) -> CheckResult:
    source = (source_root / "ai" / "enrichment" / "service.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ai/enrichment/service.py")
    run_method = _find_method(tree, "AiEnrichmentService", "run")
    if run_method is None:
        return CheckResult(
            name="ai_enrichment_service_run_invokes_provider_exactly_once",
            category="assessment_integration",
            ok=False,
            detail="AiEnrichmentService.run() method not found",
        )
    invoke_count = _count_attribute_calls(run_method, "invoke")
    ok = invoke_count == 1
    return CheckResult(
        name="ai_enrichment_service_run_invokes_provider_exactly_once",
        category="assessment_integration",
        ok=ok,
        detail=f"invoke_count={invoke_count} within AiEnrichmentService.run()",
    )


def check_run_ai_assessment_calls_service_run_exactly_once(source_root: Path) -> CheckResult:
    source = (source_root / "application" / "assessment" / "service.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="application/assessment/service.py")
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_ai_assessment":
            fn = node
            break
    if fn is None:
        return CheckResult(
            name="run_ai_assessment_calls_enrichment_service_run_exactly_once",
            category="assessment_integration",
            ok=False,
            detail="_run_ai_assessment() function not found",
        )
    run_count = _count_attribute_calls(fn, "run")
    ok = run_count == 1
    return CheckResult(
        name="run_ai_assessment_calls_enrichment_service_run_exactly_once",
        category="assessment_integration",
        ok=ok,
        detail=f"service.run() call_count={run_count} within _run_ai_assessment()",
    )


def check_assessment_schema_version_unchanged(_source_root: Path) -> CheckResult:
    ok = ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    return CheckResult(
        name="assessment_json_schema_version_is_1_2",
        category="assessment_integration",
        ok=ok,
        detail=f"ASSESSMENT_JSON_SCHEMA_VERSION == {ASSESSMENT_JSON_SCHEMA_VERSION!r}",
    )


def build_assessment_integration_matrix() -> dict[str, object]:
    return {
        "advisor_path": (
            "AiEnrichmentService / Modernization Advisor (not the legacy agent for assess)"
        ),
        "assessment_schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "invoke_calls_per_assess_run": 1,
    }


def run_assessment_integration_checks(
    source_root: Path,
) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_enrichment_service_invokes_provider_exactly_once(source_root),
        check_run_ai_assessment_calls_service_run_exactly_once(source_root),
        check_assessment_schema_version_unchanged(source_root),
    ]
    return checks, build_assessment_integration_matrix()


__all__ = [
    "build_assessment_integration_matrix",
    "check_assessment_schema_version_unchanged",
    "check_enrichment_service_invokes_provider_exactly_once",
    "check_run_ai_assessment_calls_service_run_exactly_once",
    "run_assessment_integration_checks",
]
