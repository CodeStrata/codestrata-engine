"""PHP structural complexity extraction (brace-aware; no external parser).

Mirrors the Java structural scan: physical LOC, parameter counts, branch-point
counts, nesting depth, and type/callable sizes for ordinary PHP declarations.
Anonymous functions and highly atypical syntax are left unmeasured.
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
    PHP_COMPLEXITY_PROVIDER_ID,
    PHP_COMPLEXITY_PROVIDER_VERSION,
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

_TYPE_DECL = re.compile(
    r"\b(?P<kind>class|interface|enum|trait)\s+(?P<name>[A-Za-z_][\w]*)\b"
)
_METHOD_LIKE = re.compile(
    r"(?P<mods>(?:(?:public|protected|private|static|final|abstract)\s+)*)"
    r"function\s+(?P<name>&?[A-Za-z_][\w]*)\s*"
    r"\((?P<params>[^;{}]*)\)\s*(?::\s*[^{;]+)?\s*\{",
    re.MULTILINE,
)
_FUNCTION_LIKE = re.compile(
    r"(?<![\w$])function\s+(?P<name>&?[A-Za-z_][\w]*)\s*"
    r"\((?P<params>[^;{}]*)\)\s*(?::\s*[^{;]+)?\s*\{",
    re.MULTILINE,
)
_BRANCH_WORD = re.compile(r"\b(?:if|for|foreach|while|case|catch)\b")
_BOOL_OP = re.compile(r"&&|\|\|")
_TERNARY = re.compile(r"(?<![?:])\?(?![?:])")
_KEYWORDS = frozenset(
    {
        "abstract",
        "and",
        "as",
        "break",
        "callable",
        "case",
        "catch",
        "class",
        "clone",
        "const",
        "continue",
        "declare",
        "default",
        "do",
        "echo",
        "else",
        "elseif",
        "empty",
        "enddeclare",
        "endfor",
        "endforeach",
        "endif",
        "endswitch",
        "endwhile",
        "enum",
        "eval",
        "exit",
        "extends",
        "final",
        "finally",
        "fn",
        "for",
        "foreach",
        "function",
        "global",
        "goto",
        "if",
        "implements",
        "include",
        "include_once",
        "instanceof",
        "insteadof",
        "interface",
        "isset",
        "list",
        "match",
        "namespace",
        "new",
        "or",
        "print",
        "private",
        "protected",
        "public",
        "readonly",
        "require",
        "require_once",
        "return",
        "static",
        "switch",
        "throw",
        "trait",
        "try",
        "unset",
        "use",
        "var",
        "while",
        "xor",
        "yield",
        "true",
        "false",
        "null",
    }
)


@dataclass
class PhpFileComplexityResult:
    file: FileComplexityEvidence
    types: list[TypeComplexityEvidence] = field(default_factory=list)
    callables: list[CallableComplexityEvidence] = field(default_factory=list)
    failed: bool = False
    diagnostic: str | None = None


def extract_php_file_complexity(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> PhpFileComplexityResult:
    provenance = EvidenceProvenance(
        provider_id=PHP_COMPLEXITY_PROVIDER_ID,
        provider_version=PHP_COMPLEXITY_PROVIDER_VERSION,
        source_analyzer="language.php.complexity.structural",
        extraction_method="php_structural_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        transformation_chain=("php_structural_scan", "complexity_evidence"),
        configuration_fingerprint=configuration_fingerprint,
        notes=("closures_not_extracted", "comments_strings_scrubbed_for_structure"),
    )
    classification = classification_for_path(path)
    lines = physical_line_count(text)
    file_evidence = FileComplexityEvidence(
        evidence_id=make_file_complexity_id(
            provider_id=PHP_COMPLEXITY_PROVIDER_ID,
            language="php",
            path=path,
        ),
        language="php",
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
    covered_spans: set[tuple[int, int]] = set()

    try:
        for match in _TYPE_DECL.finditer(scrubbed):
            kind_text = match.group("kind")
            name = match.group("name")
            body_open = scrubbed.find("{", match.end())
            if body_open < 0:
                continue
            body_close = _matching_brace(scrubbed, body_open)
            if body_close < 0:
                continue
            type_kind = {
                "class": ComplexityTypeKind.CLASS,
                "interface": ComplexityTypeKind.INTERFACE,
                "enum": ComplexityTypeKind.ENUM,
                "trait": ComplexityTypeKind.CLASS,
            }.get(kind_text, ComplexityTypeKind.UNKNOWN)
            line_start = _line_number(line_starts, match.start())
            line_end = _line_number(line_starts, body_close)
            body = scrubbed[body_open + 1 : body_close]
            body_offset = body_open + 1
            type_callables = _extract_callables_in_type(
                path=path,
                type_name=name,
                body=body,
                body_offset=body_offset,
                line_starts=line_starts,
                classification=classification,
                provenance=provenance,
            )
            for item in type_callables:
                key = (item.span.line_start or 0, item.span.line_end or 0)
                covered_spans.add(key)
            callables.extend(type_callables)
            types.append(
                TypeComplexityEvidence(
                    evidence_id=make_type_complexity_id(
                        provider_id=PHP_COMPLEXITY_PROVIDER_ID,
                        language="php",
                        path=path,
                        qualified_name=name,
                    ),
                    language="php",
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

        # Top-level named functions (outside type bodies).
        for match in _FUNCTION_LIKE.finditer(scrubbed):
            name = match.group("name").lstrip("&")
            if name.lower() in _KEYWORDS:
                continue
            body_open_local = match.end() - 1
            body_close = _matching_brace(scrubbed, body_open_local)
            if body_close < 0:
                continue
            # Skip functions nested inside already-extracted types.
            if any(
                type_item.span.line_start
                and type_item.span.line_end
                and type_item.span.line_start
                <= _line_number(line_starts, match.start())
                <= type_item.span.line_end
                for type_item in types
            ):
                continue
            candidate = _callable_from_match(
                path=path,
                owner="",
                name=name,
                params_text=match.group("params"),
                match_start=match.start(),
                body_open_local=body_open_local,
                scrubbed_body=scrubbed,
                body_offset=0,
                line_starts=line_starts,
                classification=classification,
                provenance=provenance,
                callable_kind=ComplexityCallableKind.FUNCTION,
            )
            if candidate is None:
                continue
            key = (candidate.span.line_start or 0, candidate.span.line_end or 0)
            if key in covered_spans:
                continue
            covered_spans.add(key)
            callables.append(candidate)
    except Exception as error:  # noqa: BLE001
        return PhpFileComplexityResult(
            file=file_evidence,
            failed=True,
            diagnostic=f"php_structural_error:{path}:{type(error).__name__}",
        )

    file_evidence = file_evidence.model_copy(
        update={
            "type_count": IntMetric.available(len(types)),
            "callable_count": IntMetric.available(len(callables)),
        }
    )
    return PhpFileComplexityResult(file=file_evidence, types=types, callables=callables)


def _extract_callables_in_type(
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
    seen_spans: set[tuple[int, int]] = set()

    for match in _METHOD_LIKE.finditer(body):
        name = match.group("name").lstrip("&")
        if name.lower() in _KEYWORDS:
            continue
        callable_kind = (
            ComplexityCallableKind.CONSTRUCTOR
            if name == "__construct"
            else ComplexityCallableKind.METHOD
        )
        item = _callable_from_match(
            path=path,
            owner=type_name,
            name=name,
            params_text=match.group("params"),
            match_start=body_offset + match.start(),
            body_open_local=match.end() - 1,
            scrubbed_body=body,
            body_offset=body_offset,
            line_starts=line_starts,
            classification=classification,
            provenance=provenance,
            callable_kind=callable_kind,
        )
        if item is None:
            continue
        key = (item.span.line_start or 0, item.span.line_end or 0)
        if key in seen_spans:
            continue
        seen_spans.add(key)
        found.append(item)

    return sorted(found, key=lambda item: (item.span.line_start or 0, item.name))


def _callable_from_match(
    *,
    path: str,
    owner: str,
    name: str,
    params_text: str,
    match_start: int,
    body_open_local: int,
    scrubbed_body: str,
    body_offset: int,
    line_starts: list[int],
    classification: SourceClassification,
    provenance: EvidenceProvenance,
    callable_kind: ComplexityCallableKind,
) -> CallableComplexityEvidence | None:
    body_close_local = _matching_brace(scrubbed_body, body_open_local)
    if body_close_local < 0:
        return None
    absolute_close = body_offset + body_close_local
    line_start = _line_number(line_starts, match_start)
    line_end = _line_number(line_starts, absolute_close)
    method_body = scrubbed_body[body_open_local + 1 : body_close_local]
    params = _parameter_count(params_text)
    branches = _branch_point_count(method_body)
    nesting = _max_nesting_depth(method_body)
    owner_prefix = f"{owner}." if owner else ""
    signature = f"{owner_prefix}{name}#{params}@{line_start}"
    return CallableComplexityEvidence(
        evidence_id=make_callable_complexity_id(
            provider_id=PHP_COMPLEXITY_PROVIDER_ID,
            language="php",
            path=path,
            qualified_signature=signature,
        ),
        language="php",
        path=path,
        name=name,
        qualified_signature=signature,
        callable_kind=callable_kind,
        owner_qualified_name=owner or None,
        classification=classification,
        span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
        physical_line_count=IntMetric.available(line_end - line_start + 1),
        parameter_count=IntMetric.available(params),
        branch_point_count=IntMetric.available(branches),
        max_nesting_depth=IntMetric.available(nesting),
        provenance=provenance,
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
        len(_BRANCH_WORD.findall(body))
        + len(_BOOL_OP.findall(body))
        + len(_TERNARY.findall(body))
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
    """Replace comments/strings with spaces, preserving newlines and indexes."""

    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "#":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            out.extend([" ", " "])
            i += 2
            while i < n - 1 and not (text[i] == "*" and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n - 1:
                out.extend([" ", " "])
                i += 2
            continue
        if ch in {'"', "'"}:
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                cur = text[i]
                if cur == "\\" and i + 1 < n:
                    out.extend([" ", " "])
                    i += 2
                    continue
                if cur == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if cur == "\n" else " ")
                i += 1
            continue
        out.append(ch)
        i += 1
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
    return max(high + 1, 1)
