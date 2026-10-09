"""M20 skipped/disabled tests. Conditional and dynamic skips stay distinct."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.quality.maps import language_for_path
from codestrata.application.evidence.testing.capability import SKIP_FORMULA_VERSION
from codestrata.application.evidence.testing.models import (
    CoverageScope,
    MetricStatusName,
    SkipKind,
    SkipMetric,
    SkipRecord,
    SourceSpan,
    TestDeclaration,
)
from codestrata.application.evidence.testing.paths import is_test_like, normalize_relative_path

_UNSUPPORTED_DECORATORS = (
    "@flaky",
    "@quarantine",
    "@slow",
    "@Flaky",
    "@Quarantine",
)
_JAVA_DISABLED = re.compile(r"@(Disabled|Ignore)\b(?:\s*\(\s*\"([^\"]*)\"\s*\))?")
_JAVA_CONDITIONAL = re.compile(
    r"@(DisabledIf|EnabledIf|EnabledOnOs|DisabledOnOs|EnabledIfEnvironmentVariable)\b"
)
_JS_EXPLICIT = re.compile(
    r"\b(?:test\.skip|it\.skip|describe\.skip|xdescribe|xit)\s*\("
)
_JS_CONDITIONAL = re.compile(r"\b(?:test\.skipIf|it\.skipIf|describe\.skipIf)\s*\(")


def _decorator_chain(node: ast.AST) -> str:
    current: ast.AST = node
    if isinstance(current, ast.Call):
        current = current.func
    parts: list[str] = []
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_static_condition(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant | ast.Name | ast.Attribute):
        return not isinstance(node, ast.Call)
    if isinstance(node, ast.UnaryOp):
        return _is_static_condition(node.operand)
    if isinstance(node, ast.BoolOp):
        return all(_is_static_condition(item) for item in node.values)
    if isinstance(node, ast.Compare):
        return _is_static_condition(node.left) and all(
            _is_static_condition(item) for item in node.comparators
        )
    return False


def _skip_from_decorators(
    *,
    path: str,
    name: str,
    test_id: str,
    decorators: Sequence[ast.AST],
    span: SourceSpan,
) -> SkipRecord | None:
    for decorator in decorators:
        chain = _decorator_chain(decorator)
        call = decorator if isinstance(decorator, ast.Call) else None
        if chain.endswith("mark.skip") or chain in {"skip", "unittest.skip"}:
            reason = None
            if call is not None:
                if call.keywords:
                    reason = _literal_string(call.keywords[0].value)
                elif call.args:
                    reason = _literal_string(call.args[0])
            return SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=SkipKind.EXPLICIT_DISABLED,
                annotation=chain,
                span=span,
                reason=reason,
                formula_version=SKIP_FORMULA_VERSION,
            )
        if chain.endswith("mark.skipif") or chain in {"skipIf", "skipUnless", "unittest.skipIf"}:
            condition_node = call.args[0] if call is not None and call.args else None
            condition_text = ast.unparse(condition_node) if condition_node is not None else None
            reason = None
            if call is not None:
                if len(call.args) > 1:
                    reason = _literal_string(call.args[1])
                for keyword in call.keywords:
                    if keyword.arg == "reason":
                        reason = _literal_string(keyword.value)
            dynamic = condition_node is None or not _is_static_condition(condition_node)
            return SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=(
                    SkipKind.UNKNOWN_ELIGIBILITY if dynamic else SkipKind.CONDITIONAL
                ),
                annotation=chain,
                span=span,
                reason=reason,
                static_condition=None if dynamic else condition_text,
                formula_version=SKIP_FORMULA_VERSION,
            )
        rendered = chain.lower()
        last = rendered.split(".")[-1]
        if any(token.strip("@").lower() == last for token in ("flaky", "quarantine", "slow")):
            return SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=SkipKind.UNSUPPORTED_DECORATOR,
                annotation=chain,
                span=span,
                formula_version=SKIP_FORMULA_VERSION,
            )
    return None


def _python_body_skip(
    *,
    path: str,
    name: str,
    test_id: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    span: SourceSpan,
) -> SkipRecord | None:
    for statement in node.body:
        if isinstance(statement, ast.If):
            skip_call = _pytest_skip_call(statement.body)
            if skip_call is None:
                continue
            condition_text = ast.unparse(statement.test)
            dynamic = not _is_static_condition(statement.test)
            reason = _skip_reason_from_call(skip_call)
            return SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=(
                    SkipKind.UNKNOWN_ELIGIBILITY if dynamic else SkipKind.CONDITIONAL
                ),
                annotation="pytest.skip",
                span=span,
                reason=reason,
                static_condition=None if dynamic else condition_text,
                formula_version=SKIP_FORMULA_VERSION,
            )
        call = statement.value if isinstance(statement, ast.Expr) else None
        if isinstance(call, ast.Call) and _is_pytest_skip(call):
            reason = _skip_reason_from_call(call)
            kind = (
                SkipKind.UNKNOWN_ELIGIBILITY
                if call.args and _literal_string(call.args[0]) is None and not call.keywords
                else SkipKind.EXPLICIT_DISABLED
            )
            if (
                call.args
                and not _is_static_condition(call.args[0])
                and _literal_string(call.args[0]) is None
            ):
                kind = SkipKind.UNKNOWN_ELIGIBILITY
            return SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=kind,
                annotation="pytest.skip",
                span=span,
                reason=reason if kind is SkipKind.EXPLICIT_DISABLED else reason,
                static_condition=None,
                formula_version=SKIP_FORMULA_VERSION,
            )
    return None


def _is_pytest_skip(call: ast.Call) -> bool:
    chain = _decorator_chain(call)
    return chain in {"pytest.skip", "skip"} or chain.endswith(".skip")


def _pytest_skip_call(body: Sequence[ast.stmt]) -> ast.Call | None:
    for statement in body:
        call = statement.value if isinstance(statement, ast.Expr) else None
        if isinstance(call, ast.Call) and _is_pytest_skip(call):
            return call
    return None


def _skip_reason_from_call(call: ast.Call) -> str | None:
    if call.args:
        return _literal_string(call.args[0])
    for keyword in call.keywords:
        if keyword.arg in {None, "reason"} or keyword.arg == "reason":
            return _literal_string(keyword.value)
    return None


def _python_records(path: str, text: str, tests: Sequence[TestDeclaration]) -> list[SkipRecord]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    by_name = {item.name.split(".")[-1]: item for item in tests if item.path == path}
    by_qualified = {item.name: item for item in tests if item.path == path}
    records: list[SkipRecord] = []

    def handle_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        class_decorators: Sequence[ast.AST] = (),
        qualified: str | None = None,
    ) -> None:
        name = qualified or node.name
        test = by_qualified.get(name) or by_name.get(node.name)
        if test is None and not node.name.startswith("test"):
            return
        test_id = test.test_id if test is not None else f"test:{path}:{name}:{node.lineno}"
        span = (
            test.span
            if test is not None
            else SourceSpan(
                path=path,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
            )
        )
        record = _skip_from_decorators(
            path=path,
            name=name,
            test_id=test_id,
            decorators=(*class_decorators, *node.decorator_list),
            span=span,
        )
        if record is None:
            record = _python_body_skip(
                path=path, name=name, test_id=test_id, node=node, span=span
            )
        if record is None and test is not None:
            record = SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=name,
                kind=SkipKind.ENABLED,
                annotation="",
                span=span,
                formula_version=SKIP_FORMULA_VERSION,
            )
        if record is not None:
            records.append(record)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            handle_function(node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    handle_function(
                        child,
                        class_decorators=node.decorator_list,
                        qualified=f"{node.name}.{child.name}",
                    )
    return records


def _java_records(path: str, text: str, tests: Sequence[TestDeclaration]) -> list[SkipRecord]:
    records: list[SkipRecord] = []
    lines = text.splitlines()
    tests_by_name = {item.name: item for item in tests if item.path == path}
    for item in tests:
        if item.path != path:
            continue
        window_start = max(item.span.line_start - 6, 1)
        window = "\n".join(lines[window_start - 1 : item.span.line_end])
        if any(token in window for token in _UNSUPPORTED_DECORATORS):
            records.append(
                SkipRecord(
                    skip_id=f"skip:{item.test_id}",
                    test_id=item.test_id,
                    path=path,
                    name=item.name,
                    kind=SkipKind.UNSUPPORTED_DECORATOR,
                    annotation="unsupported",
                    span=item.span,
                    formula_version=SKIP_FORMULA_VERSION,
                )
            )
            continue
        conditional = _JAVA_CONDITIONAL.search(window)
        disabled = _JAVA_DISABLED.search(window)
        if conditional:
            records.append(
                SkipRecord(
                    skip_id=f"skip:{item.test_id}",
                    test_id=item.test_id,
                    path=path,
                    name=item.name,
                    kind=SkipKind.CONDITIONAL,
                    annotation=conditional.group(0),
                    span=item.span,
                    static_condition=conditional.group(0),
                    formula_version=SKIP_FORMULA_VERSION,
                )
            )
        elif disabled:
            records.append(
                SkipRecord(
                    skip_id=f"skip:{item.test_id}",
                    test_id=item.test_id,
                    path=path,
                    name=item.name,
                    kind=SkipKind.EXPLICIT_DISABLED,
                    annotation=disabled.group(1),
                    span=item.span,
                    reason=disabled.group(2),
                    formula_version=SKIP_FORMULA_VERSION,
                )
            )
        else:
            records.append(
                SkipRecord(
                    skip_id=f"skip:{item.test_id}",
                    test_id=item.test_id,
                    path=path,
                    name=item.name,
                    kind=SkipKind.ENABLED,
                    annotation="",
                    span=item.span,
                    formula_version=SKIP_FORMULA_VERSION,
                )
            )
    _ = tests_by_name
    return records


def _js_kind(line: str) -> tuple[SkipKind, str, str | None]:
    if _JS_CONDITIONAL.search(line):
        return SkipKind.CONDITIONAL, "skipIf", line.strip()
    if _JS_EXPLICIT.search(line) or line.strip().startswith("xit(") or "xdescribe(" in line:
        return SkipKind.EXPLICIT_DISABLED, "skip", None
    if any(token in line for token in _UNSUPPORTED_DECORATORS):
        return SkipKind.UNSUPPORTED_DECORATOR, "unsupported", None
    return SkipKind.ENABLED, "", None


def _js_records(path: str, text: str, tests: Sequence[TestDeclaration]) -> list[SkipRecord]:
    records: list[SkipRecord] = []
    seen: set[int] = set()
    for item in tests:
        if item.path != path:
            continue
        lines = text.splitlines()
        line = lines[item.span.line_start - 1] if item.span.line_start <= len(lines) else ""
        kind, annotation, condition = _js_kind(line)
        seen.add(item.span.line_start)
        records.append(
            SkipRecord(
                skip_id=f"skip:{item.test_id}",
                test_id=item.test_id,
                path=path,
                name=item.name,
                kind=kind,
                annotation=annotation,
                span=item.span,
                static_condition=condition,
                formula_version=SKIP_FORMULA_VERSION,
            )
        )
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line_no in seen:
            continue
        kind, annotation, condition = _js_kind(line)
        if kind is SkipKind.ENABLED:
            continue
        test_id = f"test:{path}:js:{line_no}"
        records.append(
            SkipRecord(
                skip_id=f"skip:{test_id}",
                test_id=test_id,
                path=path,
                name=line.strip()[:80],
                kind=kind,
                annotation=annotation,
                span=SourceSpan(path=path, line_start=line_no, line_end=line_no),
                static_condition=condition,
                formula_version=SKIP_FORMULA_VERSION,
            )
        )
    return records


def collect_skip_metric(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    tests: Sequence[TestDeclaration],
    notes: list[str],
    max_file_bytes: int,
) -> SkipMetric:
    records: list[SkipRecord] = []
    unknown_files = 0
    inspected = 0
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not is_test_like(path):
            continue
        text = file_texts.get(path, file_texts.get(raw))
        if text is None:
            continue
        if len(text.encode("utf-8")) > max_file_bytes:
            notes.append(f"file_over_budget:{path}")
            unknown_files += 1
            continue
        language = language_for_path(path)
        file_tests = [item for item in tests if item.path == path]
        inspected += 1
        if language == "python":
            records.extend(_python_records(path, text, file_tests))
        elif language == "java":
            records.extend(_java_records(path, text, file_tests))
        elif language in {"javascript", "typescript"}:
            records.extend(_js_records(path, text, file_tests))
        else:
            unknown_files += 1
            notes.append(f"unsupported_skip_syntax:{path}")

    records.sort(key=lambda item: item.skip_id)
    explicit = sum(1 for item in records if item.kind is SkipKind.EXPLICIT_DISABLED)
    conditional = sum(1 for item in records if item.kind is SkipKind.CONDITIONAL)
    unknown = sum(1 for item in records if item.kind is SkipKind.UNKNOWN_ELIGIBILITY)
    enabled = sum(1 for item in records if item.kind is SkipKind.ENABLED)
    unsupported = sum(1 for item in records if item.kind is SkipKind.UNSUPPORTED_DECORATOR)

    if inspected == 0 and unknown_files == 0 and not tests:
        return SkipMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            explicit_disabled=0,
            full_scope_status=CoverageScope.NOT_APPLICABLE,
            reason="no_tests",
            formula_version=SKIP_FORMULA_VERSION,
        )
    if unknown_files:
        status = MetricStatusName.UNKNOWN
        scope = CoverageScope.PARTIAL if records else CoverageScope.UNKNOWN
        reason = "unsupported_or_unparsed_skip_syntax"
    else:
        status = MetricStatusName.VALUE
        scope = CoverageScope.COMPLETE
        reason = "explicit_disabled_distinct_from_conditional"

    return SkipMetric(
        status=status,
        explicit_disabled=explicit,
        conditional=conditional,
        unknown_eligibility=unknown,
        enabled=enabled,
        unsupported_decorator=unsupported,
        full_scope_status=scope,
        reason=reason,
        formula_version=SKIP_FORMULA_VERSION,
        records=tuple(records),
    )


__all__ = ["collect_skip_metric"]
