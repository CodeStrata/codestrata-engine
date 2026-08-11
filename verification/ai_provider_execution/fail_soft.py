"""Characterizes the executor's fail-soft contract (CR-3): never raises for an expected failure.

Complements ``executor.py``'s functional checks with a structural check that
``executor.py`` (the production module) only ever catches ``Exception``
(never a bare ``except:`` and never ``BaseException``), so
``KeyboardInterrupt``/``SystemExit``/``GeneratorExit`` are guaranteed to
propagate by Python's own exception hierarchy, not merely by this suite's
current test coverage.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.ai_provider_execution.models import CheckResult


def _executor_source_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "ai"
        / "provider_contracts"
        / "executor.py"
    )


def check_executor_never_uses_a_bare_except_or_catches_base_exception() -> CheckResult:
    source = _executor_source_path().read_text(encoding="utf-8")
    tree = ast.parse(source, filename="executor.py")
    offending: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            offending.append("bare except:")
            continue
        type_name = ast.unparse(node.type)
        if type_name in {"BaseException"}:
            offending.append(type_name)
    ok = not offending
    return CheckResult(
        name="executor_never_uses_a_bare_except_or_catches_base_exception",
        category="fail_soft",
        ok=ok,
        detail=f"offending_handlers={offending}" if offending else "only 'except Exception' found",
    )


def check_executor_catches_exactly_exception_type() -> CheckResult:
    source = _executor_source_path().read_text(encoding="utf-8")
    tree = ast.parse(source, filename="executor.py")
    handler_types: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            handler_types.append(ast.unparse(node.type))
    ok = handler_types == ["Exception"]
    return CheckResult(
        name="executor_catches_exactly_the_exception_type_and_nothing_broader",
        category="fail_soft",
        ok=ok,
        detail=f"handler_types={handler_types}",
    )


def check_executor_module_never_calls_sys_exit_or_os_kill() -> CheckResult:
    source = _executor_source_path().read_text(encoding="utf-8")
    ok = "sys.exit" not in source and "os.kill" not in source and "os._exit" not in source
    return CheckResult(
        name="executor_module_never_calls_sys_exit_or_os_kill",
        category="fail_soft",
        ok=ok,
        detail="'sys.exit'/'os.kill'/'os._exit' tokens absent from executor.py",
    )


def build_fail_soft_exception_hierarchy_matrix() -> dict[str, bool]:
    """Document, from Python's own hierarchy, which exceptions the executor catches."""

    return {
        "BaseException_is_caught_by_except_Exception": issubclass(BaseException, Exception),
        "Exception_is_caught_by_except_Exception": issubclass(Exception, Exception),
        "GeneratorExit_is_caught_by_except_Exception": issubclass(GeneratorExit, Exception),
        "KeyboardInterrupt_is_caught_by_except_Exception": issubclass(KeyboardInterrupt, Exception),
        "SystemExit_is_caught_by_except_Exception": issubclass(SystemExit, Exception),
    }


def check_keyboard_interrupt_system_exit_and_generator_exit_are_not_exception_subclasses() -> (
    CheckResult
):
    matrix = build_fail_soft_exception_hierarchy_matrix()
    ok = (
        matrix["Exception_is_caught_by_except_Exception"] is True
        and matrix["GeneratorExit_is_caught_by_except_Exception"] is False
        and matrix["KeyboardInterrupt_is_caught_by_except_Exception"] is False
        and matrix["SystemExit_is_caught_by_except_Exception"] is False
    )
    return CheckResult(
        name="keyboard_interrupt_system_exit_and_generator_exit_are_not_exception_subclasses",
        category="fail_soft",
        ok=ok,
        detail=f"matrix={matrix}",
    )


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_executor_never_uses_a_bare_except_or_catches_base_exception(),
        check_executor_catches_exactly_exception_type(),
        check_executor_module_never_calls_sys_exit_or_os_kill(),
        check_keyboard_interrupt_system_exit_and_generator_exit_are_not_exception_subclasses(),
    ]
    matrix = {"exception_hierarchy": build_fail_soft_exception_hierarchy_matrix()}
    return checks, matrix


__all__ = [
    "build_fail_soft_exception_hierarchy_matrix",
    "check_executor_catches_exactly_exception_type",
    "check_executor_module_never_calls_sys_exit_or_os_kill",
    "check_executor_never_uses_a_bare_except_or_catches_base_exception",
    "check_keyboard_interrupt_system_exit_and_generator_exit_are_not_exception_subclasses",
    "run_fail_soft_checks",
]
