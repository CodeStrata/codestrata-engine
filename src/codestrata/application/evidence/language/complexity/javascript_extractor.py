"""JavaScript/TypeScript structural complexity extraction (brace-aware).

Measures ordinary functions, class methods, and assigned arrow functions.
This is not the TypeScript compiler or a framework extractor. Template
expressions, regex literals, and nested parentheses in parameter lists are
left unmeasured.
"""

from __future__ import annotations

import re
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
    JAVASCRIPT_COMPLEXITY_PROVIDER_ID,
    JAVASCRIPT_COMPLEXITY_PROVIDER_VERSION,
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

_TYPE_DECL = re.compile(r"\b(?P<kind>class|interface)\s+(?P<name>[A-Za-z_$][\w$]*)\b")
_FUNCTION_DECL = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s*\*?\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"\((?P<params>[^)]*)\)\s*\{",
    re.MULTILINE,
)
_METHOD_DECL = re.compile(
    r"(?:(?:public|private|protected|static|async|readonly|get|set)\s+)*"
    r"(?P<name>constructor|[A-Za-z_$][\w$]*)\s*\((?P<params>[^)]*)\)\s*\{",
    re.MULTILINE,
)
_ARROW_DECL = re.compile(
    r"(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?"
    r"(?:\((?P<params>[^)]*)\)|(?P<single>[A-Za-z_$][\w$]*))\s*=>",
    re.MULTILINE,
)
_BRANCH_WORD = re.compile(r"\b(?:if|for|while|case|catch)\b")
_BOOL_OP = re.compile(r"&&|\|\|")
_TERNARY = re.compile(r"(?<![?:])\?(?![.?:=])")
_KEYWORDS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "function",
        "return",
        "class",
        "interface",
        "else",
        "do",
        "try",
        "new",
        "typeof",
        "instanceof",
        "await",
        "yield",
        "import",
        "export",
        "from",
        "of",
        "in",
    }
)


@dataclass
class JavaScriptFileComplexityResult:
    file: FileComplexityEvidence
    types: list[TypeComplexityEvidence] = field(default_factory=list)
    callables: list[CallableComplexityEvidence] = field(default_factory=list)
    failed: bool = False
    diagnostic: str | None = None


def extract_javascript_file_complexity(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> JavaScriptFileComplexityResult:
    provenance = EvidenceProvenance(
        provider_id=JAVASCRIPT_COMPLEXITY_PROVIDER_ID,
        provider_version=JAVASCRIPT_COMPLEXITY_PROVIDER_VERSION,
        source_analyzer="language.javascript.complexity.structural",
        extraction_method="javascript_structural_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        transformation_chain=("javascript_structural_scan", "complexity_evidence"),
        configuration_fingerprint=configuration_fingerprint,
        notes=(
            "not_typescript_compiler",
            "template_expressions_unmeasured",
            "regex_literals_unmeasured",
        ),
    )
    classification = classification_for_path(path)
    lines = physical_line_count(text)
    file_evidence = FileComplexityEvidence(
        evidence_id=make_file_complexity_id(
            provider_id=JAVASCRIPT_COMPLEXITY_PROVIDER_ID,
            language="javascript",
            path=path,
        ),
        language="javascript",
        path=path,
        classification=classification,
        physical_line_count=IntMetric.available(lines),
        type_count=IntMetric.unavailable(),
        callable_count=IntMetric.unavailable(),
        provenance=provenance,
    )
    scrubbed = _scrub_comments_and_strings(text)
    line_starts = _line_start_indexes(text)
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    try:
        for match in _TYPE_DECL.finditer(scrubbed):
            body_open = scrubbed.find("{", match.end())
            if body_open < 0:
                continue
            body_close = _matching_brace(scrubbed, body_open)
            if body_close < 0:
                continue
            name = match.group("name")
            type_kind = (
                ComplexityTypeKind.INTERFACE
                if match.group("kind") == "interface"
                else ComplexityTypeKind.CLASS
            )
            line_start = _line_number(line_starts, match.start())
            line_end = _line_number(line_starts, body_close)
            body = scrubbed[body_open + 1 : body_close]
            type_callables = _methods_in_body(
                path=path,
                type_name=name,
                body=body,
                body_offset=body_open + 1,
                line_starts=line_starts,
                classification=classification,
                provenance=provenance,
            )
            callables.extend(type_callables)
            types.append(
                TypeComplexityEvidence(
                    evidence_id=make_type_complexity_id(
                        provider_id=JAVASCRIPT_COMPLEXITY_PROVIDER_ID,
                        language="javascript",
                        path=path,
                        qualified_name=name,
                    ),
                    language="javascript",
                    path=path,
                    name=name,
                    qualified_name=name,
                    type_kind=type_kind,
                    classification=classification,
                    span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
                    physical_line_count=IntMetric.available(line_end - line_start + 1),
                    callable_count=IntMetric.available(len(type_callables)),
                    provenance=provenance,
                )
            )
        for match in _FUNCTION_DECL.finditer(scrubbed):
            if _inside_type(types, line_starts, match.start()):
                continue
            item = _callable_from_brace(
                path=path,
                owner="",
                name=match.group("name"),
                params_text=match.group("params"),
                match_start=match.start(),
                body_open=match.end() - 1,
                scrubbed=scrubbed,
                line_starts=line_starts,
                classification=classification,
                provenance=provenance,
                callable_kind=ComplexityCallableKind.FUNCTION,
            )
            if item is not None:
                callables.append(item)
        for match in _ARROW_DECL.finditer(scrubbed):
            if _inside_type(types, line_starts, match.start()):
                continue
            params_text = match.group("params")
            if params_text is None:
                params_text = match.group("single") or ""
            item = _arrow_callable(
                path=path,
                name=match.group("name"),
                params_text=params_text,
                match_start=match.start(),
                arrow_end=match.end(),
                scrubbed=scrubbed,
                line_starts=line_starts,
                classification=classification,
                provenance=provenance,
            )
            if item is not None:
                callables.append(item)
    except Exception as error:  # noqa: BLE001
        return JavaScriptFileComplexityResult(
            file=file_evidence,
            failed=True,
            diagnostic=f"javascript_structural_error:{path}:{type(error).__name__}",
        )
    file_evidence = file_evidence.model_copy(
        update={
            "type_count": IntMetric.available(len(types)),
            "callable_count": IntMetric.available(len(callables)),
        }
    )
    return JavaScriptFileComplexityResult(file=file_evidence, types=types, callables=callables)


def _methods_in_body(
    *,
    path: str,
    type_name: str,
    body: str,
    body_offset: int,
    line_starts: list[int],
    classification: SourceClassification,
    provenance: EvidenceProvenance,
) -> list[CallableComplexityEvidence]:
    found: list[CallableComplexityEvidence] = []
    for match in _METHOD_DECL.finditer(body):
        name = match.group("name")
        if name in _KEYWORDS:
            continue
        kind = (
            ComplexityCallableKind.CONSTRUCTOR
            if name == "constructor"
            else ComplexityCallableKind.METHOD
        )
        item = _callable_from_brace(
            path=path,
            owner=type_name,
            name=name,
            params_text=match.group("params"),
            match_start=body_offset + match.start(),
            body_open=body_offset + match.end() - 1,
            scrubbed=body,
            line_starts=line_starts,
            classification=classification,
            provenance=provenance,
            callable_kind=kind,
            body_offset=body_offset,
        )
        if item is not None:
            found.append(item)
    return found


def _callable_from_brace(
    *,
    path: str,
    owner: str,
    name: str,
    params_text: str,
    match_start: int,
    body_open: int,
    scrubbed: str,
    line_starts: list[int],
    classification: SourceClassification,
    provenance: EvidenceProvenance,
    callable_kind: ComplexityCallableKind,
    body_offset: int = 0,
) -> CallableComplexityEvidence | None:
    local_open = body_open - body_offset
    if local_open < 0 or local_open >= len(scrubbed) or scrubbed[local_open] != "{":
        return None
    local_close = _matching_brace(scrubbed, local_open)
    if local_close < 0:
        return None
    absolute_close = body_offset + local_close
    method_body = scrubbed[local_open + 1 : local_close]
    return _evidence(
        path=path,
        owner=owner,
        name=name,
        params=_parameter_count(params_text),
        body=method_body,
        line_start=_line_number(line_starts, match_start),
        line_end=_line_number(line_starts, absolute_close),
        classification=classification,
        provenance=provenance,
        callable_kind=callable_kind,
    )


def _arrow_callable(
    *,
    path: str,
    name: str,
    params_text: str,
    match_start: int,
    arrow_end: int,
    scrubbed: str,
    line_starts: list[int],
    classification: SourceClassification,
    provenance: EvidenceProvenance,
) -> CallableComplexityEvidence | None:
    index = arrow_end
    while index < len(scrubbed) and scrubbed[index] in " \t\r\n":
        index += 1
    if index < len(scrubbed) and scrubbed[index] == "{":
        return _callable_from_brace(
            path=path,
            owner="",
            name=name,
            params_text=params_text,
            match_start=match_start,
            body_open=index,
            scrubbed=scrubbed,
            line_starts=line_starts,
            classification=classification,
            provenance=provenance,
            callable_kind=ComplexityCallableKind.FUNCTION,
        )
    line = _line_number(line_starts, match_start)
    return _evidence(
        path=path,
        owner="",
        name=name,
        params=_parameter_count(params_text),
        body="",
        line_start=line,
        line_end=line,
        classification=classification,
        provenance=provenance,
        callable_kind=ComplexityCallableKind.FUNCTION,
    )


def _evidence(
    *,
    path: str,
    owner: str,
    name: str,
    params: int,
    body: str,
    line_start: int,
    line_end: int,
    classification: SourceClassification,
    provenance: EvidenceProvenance,
    callable_kind: ComplexityCallableKind,
) -> CallableComplexityEvidence:
    owner_prefix = f"{owner}." if owner else ""
    signature = f"{owner_prefix}{name}#{params}@{line_start}"
    return CallableComplexityEvidence(
        evidence_id=make_callable_complexity_id(
            provider_id=JAVASCRIPT_COMPLEXITY_PROVIDER_ID,
            language="javascript",
            path=path,
            qualified_signature=signature,
        ),
        language="javascript",
        path=path,
        name=name,
        qualified_signature=signature,
        callable_kind=callable_kind,
        owner_qualified_name=owner or None,
        classification=classification,
        span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
        physical_line_count=IntMetric.available(line_end - line_start + 1),
        parameter_count=IntMetric.available(params),
        branch_point_count=IntMetric.available(_branch_point_count(body)),
        max_nesting_depth=IntMetric.available(_max_nesting_depth(body)),
        provenance=provenance,
    )


def _inside_type(
    types: list[TypeComplexityEvidence],
    line_starts: list[int],
    index: int,
) -> bool:
    line = _line_number(line_starts, index)
    return any(
        item.span.line_start
        and item.span.line_end
        and item.span.line_start <= line <= item.span.line_end
        for item in types
    )


def _parameter_count(params_text: str) -> int:
    compact = params_text.strip()
    if not compact:
        return 0
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in compact:
        if char in "<([":
            depth += 1
        elif char in ">)]":
            depth = max(depth - 1, 0)
        if char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return len(parts)


def _branch_point_count(body: str) -> int:
    return (
        len(_BRANCH_WORD.findall(body)) + len(_BOOL_OP.findall(body)) + len(_TERNARY.findall(body))
    )


def _max_nesting_depth(body: str) -> int:
    depth = 0
    deepest = 0
    for char in body:
        if char == "{":
            depth += 1
            deepest = max(deepest, depth)
        elif char == "}":
            depth = max(depth - 1, 0)
    return deepest


def _scrub_comments_and_strings(text: str) -> str:
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""
        if char == "/" and nxt == "/":
            while index < length and text[index] != "\n":
                out.append(" ")
                index += 1
            continue
        if char == "/" and nxt == "*":
            out.extend([" ", " "])
            index += 2
            while index < length - 1 and not (text[index] == "*" and text[index + 1] == "/"):
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            if index < length - 1:
                out.extend([" ", " "])
                index += 2
            continue
        if char in {'"', "'", "`"}:
            quote = char
            out.append(" ")
            index += 1
            while index < length:
                current = text[index]
                if current == "\\" and index + 1 < length:
                    out.extend([" ", " "])
                    index += 2
                    continue
                if current == quote:
                    out.append(" ")
                    index += 1
                    break
                out.append("\n" if current == "\n" else " ")
                index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _matching_brace(text: str, open_index: int) -> int:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
        return -1
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _line_start_indexes(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n" and index + 1 < len(text):
            starts.append(index + 1)
    return starts


def _line_number(line_starts: list[int], index: int) -> int:
    low = 0
    high = len(line_starts) - 1
    while low <= high:
        mid = (low + high) // 2
        if line_starts[mid] <= index:
            low = mid + 1
        else:
            high = mid - 1
    return high + 1
