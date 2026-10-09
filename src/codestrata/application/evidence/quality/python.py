"""Python function extraction via stdlib AST (python.cyclomatic.v1)."""

from __future__ import annotations

import ast

from codestrata.application.evidence.quality.loc import nloc_in_span
from codestrata.application.evidence.quality.maps import (
    BRANCH_MAPS,
    CYCLOMATIC_BASE,
    CYCLOMATIC_FORMULA_VERSION,
    NESTING_FORMULA_VERSION,
    SIZE_FORMULA_VERSION,
)
from codestrata.application.evidence.quality.models import (
    BranchWitness,
    FileRole,
    FunctionRecord,
    FunctionStatus,
    SourceSpan,
)

_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
    ast.Match,
)


def extract_python_functions(
    *,
    path: str,
    text: str,
    role: FileRole,
) -> tuple[tuple[FunctionRecord, ...], bool]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return (), True
    records: list[FunctionRecord] = []
    _visit_body(tree.body, path=path, text=text, role=role, owner="", records=records)
    ordered = tuple(sorted(records, key=lambda item: (item.span.line_start, item.qualified_name)))
    return ordered, False


def _visit_body(
    body: list[ast.stmt],
    *,
    path: str,
    text: str,
    role: FileRole,
    owner: str,
    records: list[FunctionRecord],
) -> None:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _take_function(node, path=path, text=text, role=role, owner=owner, records=records)
        elif isinstance(node, ast.ClassDef):
            qualified = f"{owner}.{node.name}" if owner else node.name
            _visit_body(
                node.body,
                path=path,
                text=text,
                role=role,
                owner=qualified,
                records=records,
            )
        else:
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    break


def _take_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    *,
    path: str,
    text: str,
    role: FileRole,
    owner: str,
    records: list[FunctionRecord],
) -> None:
    line_start = int(getattr(node, "lineno", 1) or 1)
    line_end = int(getattr(node, "end_lineno", line_start) or line_start)
    if isinstance(node, ast.Lambda):
        name = f"<lambda>@{line_start}"
    else:
        name = node.name
    qualified = f"{owner}.{name}" if owner else name
    branches, nesting, witnesses = _metrics(node)
    records.append(
        FunctionRecord(
            function_id=f"python:{path}:{qualified}@{line_start}",
            language="python",
            path=path,
            name=name,
            qualified_name=qualified,
            span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
            role=role,
            status=FunctionStatus.MEASURED,
            cyclomatic=CYCLOMATIC_BASE + len(branches),
            branch_count=len(branches),
            nloc=nloc_in_span(text, language="python", line_start=line_start, line_end=line_end),
            max_nesting_depth=nesting,
            cyclomatic_version=CYCLOMATIC_FORMULA_VERSION,
            nesting_version=NESTING_FORMULA_VERSION,
            size_version=SIZE_FORMULA_VERSION,
            branch_map_language=BRANCH_MAPS["python"].language,
            branches=tuple(branches),
            nesting_witness=tuple(witnesses),
        )
    )
    for child in _direct_nested_functions(node):
        _take_function(
            child,
            path=path,
            text=text,
            role=role,
            owner=qualified,
            records=records,
        )


def _direct_nested_functions(
    node: ast.AST,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda]:
    found: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda] = []

    def walk(current: ast.AST) -> None:
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                found.append(child)
                continue
            if isinstance(child, ast.ClassDef):
                continue
            walk(child)

    walk(node)
    return found


def _metrics(node: ast.AST) -> tuple[list[BranchWitness], int, list[BranchWitness]]:
    branches: list[BranchWitness] = []

    def walk_branches(current: ast.AST) -> None:
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            line = int(getattr(child, "lineno", getattr(node, "lineno", 1)) or 1)
            if isinstance(child, ast.If):
                branches.append(BranchWitness(syntax="if", line=line))
            elif isinstance(child, ast.For):
                branches.append(BranchWitness(syntax="for", line=line))
            elif isinstance(child, ast.AsyncFor):
                branches.append(BranchWitness(syntax="async_for", line=line))
            elif isinstance(child, ast.While):
                branches.append(BranchWitness(syntax="while", line=line))
            elif isinstance(child, ast.IfExp):
                branches.append(BranchWitness(syntax="ifexp", line=line))
            elif isinstance(child, ast.ExceptHandler):
                branches.append(BranchWitness(syntax="except", line=line))
            elif isinstance(child, ast.BoolOp):
                syntax = "boolop_and" if isinstance(child.op, ast.And) else "boolop_or"
                for _ in range(max(len(child.values) - 1, 0)):
                    branches.append(BranchWitness(syntax=syntax, line=line))
            elif isinstance(child, ast.match_case):
                pattern = child.pattern
                wildcard = isinstance(pattern, ast.MatchAs) and pattern.name is None
                if not wildcard:
                    branches.append(BranchWitness(syntax="match_case_non_wildcard", line=line))
            elif isinstance(child, ast.comprehension):
                for if_node in child.ifs:
                    if_line = int(getattr(if_node, "lineno", line) or line)
                    branches.append(BranchWitness(syntax="comprehension_if", line=if_line))
            walk_branches(child)

    walk_branches(node)

    def walk_nesting(current: ast.AST, depth: int) -> tuple[int, list[BranchWitness]]:
        deepest = depth
        witnesses: list[BranchWitness] = []
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, _NESTING_NODES):
                line = int(getattr(child, "lineno", getattr(node, "lineno", 1)) or 1)
                syntax = type(child).__name__.lower()
                inner_depth, inner_w = walk_nesting(child, depth + 1)
                witnesses.append(BranchWitness(syntax=syntax, line=line))
                witnesses.extend(inner_w)
                deepest = max(deepest, inner_depth)
            else:
                inner_depth, inner_w = walk_nesting(child, depth)
                witnesses.extend(inner_w)
                deepest = max(deepest, inner_depth)
        return deepest, witnesses

    if isinstance(node, ast.Lambda):
        lambda_depth, lambda_witness = walk_nesting(node, 0)
        return branches, lambda_depth, lambda_witness

    deepest = 0
    witnesses: list[BranchWitness] = []
    for stmt in list(getattr(node, "body", []) or []):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(stmt, _NESTING_NODES):
            line = int(getattr(stmt, "lineno", 1) or 1)
            inner_depth, inner_w = walk_nesting(stmt, 1)
            witnesses.append(BranchWitness(syntax=type(stmt).__name__.lower(), line=line))
            witnesses.extend(inner_w)
            deepest = max(deepest, inner_depth)
        else:
            inner_depth, inner_w = walk_nesting(stmt, 0)
            witnesses.extend(inner_w)
            deepest = max(deepest, inner_depth)
    return branches, deepest, witnesses


__all__ = ["extract_python_functions"]
