"""Python complexity extraction via the standard-library ``ast`` module."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from codestrata.application.evidence.language.complexity.paths import (
    classification_for_path,
    physical_line_count,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.complexity.enums import (
    ComplexityCallableKind,
    ComplexityTypeKind,
)
from codestrata.domain.evidence.language.complexity.identifiers import (
    PYTHON_COMPLEXITY_PROVIDER_ID,
    PYTHON_COMPLEXITY_PROVIDER_VERSION,
    make_callable_complexity_id,
    make_file_complexity_id,
    make_type_complexity_id,
)
from codestrata.domain.evidence.language.complexity.models import (
    CallableComplexityEvidence,
    FileComplexityEvidence,
    IntMetric,
    SourceSpan,
    TypeComplexityEvidence,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance

_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,
    ast.ExceptHandler,
    ast.Assert,
    ast.comprehension,
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
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Match,
)


@dataclass
class PythonFileComplexityResult:
    file: FileComplexityEvidence
    types: list[TypeComplexityEvidence] = field(default_factory=list)
    callables: list[CallableComplexityEvidence] = field(default_factory=list)
    failed: bool = False
    diagnostic: str | None = None


def extract_python_file_complexity(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> PythonFileComplexityResult:
    provenance = _provenance(path=path, configuration_fingerprint=configuration_fingerprint)
    classification = classification_for_path(path)
    lines = physical_line_count(text)
    file_evidence = FileComplexityEvidence(
        evidence_id=make_file_complexity_id(
            provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
            language="python",
            path=path,
        ),
        language="python",
        path=path,
        classification=classification,
        physical_line_count=IntMetric.available(lines),
        type_count=IntMetric.unavailable(),
        callable_count=IntMetric.unavailable(),
        provenance=provenance,
    )
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as error:
        return PythonFileComplexityResult(
            file=file_evidence,
            failed=True,
            diagnostic=f"python_syntax_error:{path}:{error.msg}",
        )

    module_name = _module_name_from_path(path)
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            callables.append(
                _callable_from_function(
                    node=node,
                    path=path,
                    classification=classification,
                    provenance=provenance,
                    owner_qualified_name=None,
                    callable_kind=ComplexityCallableKind.FUNCTION,
                )
            )
        elif isinstance(node, ast.ClassDef):
            class_types, class_callables = _collect_class_tree(
                node=node,
                path=path,
                classification=classification,
                provenance=provenance,
                parent_qualified=module_name,
            )
            types.extend(class_types)
            callables.extend(class_callables)

    module_span = (
        SourceSpan(path=path, line_start=1, line_end=lines)
        if lines > 0
        else SourceSpan(path=path)
    )
    types.insert(
        0,
        TypeComplexityEvidence(
            evidence_id=make_type_complexity_id(
                provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
                language="python",
                path=path,
                qualified_name=module_name,
            ),
            language="python",
            path=path,
            name=module_name.rsplit(".", 1)[-1],
            qualified_name=module_name,
            type_kind=ComplexityTypeKind.MODULE,
            classification=classification,
            span=module_span,
            physical_line_count=IntMetric.available(lines),
            callable_count=IntMetric.available(len(callables)),
            provenance=provenance,
        ),
    )
    file_evidence = file_evidence.model_copy(
        update={
            "type_count": IntMetric.available(len(types)),
            "callable_count": IntMetric.available(len(callables)),
        }
    )
    return PythonFileComplexityResult(
        file=file_evidence,
        types=types,
        callables=callables,
    )


def _provenance(*, path: str, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
        provider_version=PYTHON_COMPLEXITY_PROVIDER_VERSION,
        source_analyzer="language.python.complexity.ast",
        extraction_method="python_ast",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        transformation_chain=("python_ast", "complexity_evidence"),
        configuration_fingerprint=configuration_fingerprint,
    )


def _module_name_from_path(path: str) -> str:
    parts = [part for part in path.replace("\\", "/").split("/") if part not in {".", ".."}]
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return "__module__"
    stem = parts[-1]
    if stem.endswith(".py"):
        stem = stem[: -len(".py")]
    prefix = parts[:-1]
    if stem == "__init__":
        return ".".join(prefix) if prefix else "__init__"
    return ".".join([*prefix, stem]) if prefix else stem


def _collect_class_tree(
    *,
    node: ast.ClassDef,
    path: str,
    classification: SourceClassification,
    provenance: EvidenceProvenance,
    parent_qualified: str,
) -> tuple[list[TypeComplexityEvidence], list[CallableComplexityEvidence]]:
    qualified = f"{parent_qualified}.{node.name}" if parent_qualified else node.name
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    direct_callable_count = 0

    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = (
                ComplexityCallableKind.CONSTRUCTOR
                if child.name == "__init__"
                else ComplexityCallableKind.METHOD
            )
            callables.append(
                _callable_from_function(
                    node=child,
                    path=path,
                    classification=classification,
                    provenance=provenance,
                    owner_qualified_name=qualified,
                    callable_kind=kind,
                )
            )
            direct_callable_count += 1
        elif isinstance(child, ast.ClassDef):
            nested_types, nested_callables = _collect_class_tree(
                node=child,
                path=path,
                classification=classification,
                provenance=provenance,
                parent_qualified=qualified,
            )
            types.extend(nested_types)
            callables.extend(nested_callables)

    line_start = getattr(node, "lineno", None)
    line_end = getattr(node, "end_lineno", None) or line_start
    physical = (
        IntMetric.available(line_end - line_start + 1)
        if line_start is not None and line_end is not None
        else IntMetric.unavailable()
    )
    types.insert(
        0,
        TypeComplexityEvidence(
            evidence_id=make_type_complexity_id(
                provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
                language="python",
                path=path,
                qualified_name=qualified,
            ),
            language="python",
            path=path,
            name=node.name,
            qualified_name=qualified,
            type_kind=ComplexityTypeKind.CLASS,
            classification=classification,
            span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
            physical_line_count=physical,
            callable_count=IntMetric.available(direct_callable_count),
            provenance=provenance,
        ),
    )
    return types, callables


def _callable_from_function(
    *,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
    classification: SourceClassification,
    provenance: EvidenceProvenance,
    owner_qualified_name: str | None,
    callable_kind: ComplexityCallableKind,
) -> CallableComplexityEvidence:
    params = _parameter_count(
        node,
        exclude_implicit_receiver=callable_kind
        in {ComplexityCallableKind.METHOD, ComplexityCallableKind.CONSTRUCTOR},
    )
    branches = _branch_point_count(node)
    nesting = _max_nesting_depth(node)
    line_start = getattr(node, "lineno", None)
    line_end = getattr(node, "end_lineno", None) or line_start
    physical = (
        IntMetric.available(line_end - line_start + 1)
        if line_start is not None and line_end is not None
        else IntMetric.unavailable()
    )
    signature = _qualified_signature(
        name=node.name,
        owner=owner_qualified_name,
        parameter_count=params,
        line_start=line_start,
    )
    return CallableComplexityEvidence(
        evidence_id=make_callable_complexity_id(
            provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
            language="python",
            path=path,
            qualified_signature=signature,
        ),
        language="python",
        path=path,
        name=node.name,
        qualified_signature=signature,
        callable_kind=callable_kind,
        owner_qualified_name=owner_qualified_name,
        classification=classification,
        span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
        physical_line_count=physical,
        parameter_count=IntMetric.available(params),
        branch_point_count=IntMetric.available(branches),
        max_nesting_depth=IntMetric.available(nesting),
        provenance=provenance,
    )


def _qualified_signature(
    *,
    name: str,
    owner: str | None,
    parameter_count: int,
    line_start: int | None,
) -> str:
    owner_part = f"{owner}." if owner else ""
    line_part = f"@{line_start}" if line_start is not None else ""
    return f"{owner_part}{name}#{parameter_count}{line_part}"


def _parameter_count(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    exclude_implicit_receiver: bool = False,
) -> int:
    """Count formal parameters.

    For methods/constructors, ``self`` / ``cls`` are excluded so thresholds
    measure declared API surface rather than the implicit receiver.
    """

    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    count = (
        len(positional)
        + len(args.kwonlyargs)
        + (1 if args.vararg is not None else 0)
        + (1 if args.kwarg is not None else 0)
    )
    if (
        exclude_implicit_receiver
        and positional
        and positional[0].arg in {"self", "cls"}
    ):
        count -= 1
    return count


def _branch_point_count(node: ast.AST) -> int:
    total = 0
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, _BRANCH_NODES):
            if isinstance(child, ast.comprehension):
                total += len(child.ifs)
                continue
            total += 1
        elif isinstance(child, ast.BoolOp):
            total += max(len(child.values) - 1, 0)
        elif isinstance(child, ast.match_case):
            total += 1
    return total


def _max_nesting_depth(node: ast.AST) -> int:
    """Maximum nesting of compound statements inside the callable body."""

    def walk(current: ast.AST, depth: int) -> int:
        deepest = depth
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                deepest = max(deepest, walk(child, depth + 1))
            elif isinstance(child, _NESTING_NODES):
                deepest = max(deepest, walk(child, depth + 1))
            else:
                deepest = max(deepest, walk(child, depth))
        return deepest

    deepest = 0
    for stmt in getattr(node, "body", []):
        if isinstance(stmt, _NESTING_NODES):
            deepest = max(deepest, walk(stmt, 1))
        else:
            deepest = max(deepest, walk(stmt, 0))
    return deepest
