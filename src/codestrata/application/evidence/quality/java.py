"""Java function extraction using the frozen java.cyclomatic.v1 map."""

from __future__ import annotations

from codestrata.application.evidence.quality.cfamily import matching_punct, measure_cfamily_body
from codestrata.application.evidence.quality.loc import nloc_in_span
from codestrata.application.evidence.quality.maps import (
    BRANCH_MAPS,
    CYCLOMATIC_FORMULA_VERSION,
    NESTING_FORMULA_VERSION,
    SIZE_FORMULA_VERSION,
)
from codestrata.application.evidence.quality.models import (
    FileRole,
    FunctionRecord,
    FunctionStatus,
    SourceSpan,
)
from codestrata.application.evidence.quality.tokenize import Token, tokenize_source

_TYPE_KEYWORDS = frozenset({"class", "interface", "enum", "record"})
_MODIFIERS = frozenset(
    {
        "public",
        "protected",
        "private",
        "static",
        "final",
        "abstract",
        "synchronized",
        "native",
        "default",
        "strictfp",
        "transient",
        "volatile",
    }
)


def extract_java_functions(
    *,
    path: str,
    text: str,
    role: FileRole,
) -> tuple[tuple[FunctionRecord, ...], bool]:
    tokens = tokenize_source(text, language="java")
    if not tokens:
        return (), False
    records: list[FunctionRecord] = []
    incomplete = False
    index = 0
    n = len(tokens)
    while index < n:
        token = tokens[index]
        if token.kind == "keyword" and token.value in _TYPE_KEYWORDS:
            name = ""
            if index + 1 < n and tokens[index + 1].kind == "ident":
                name = tokens[index + 1].value
            cursor = index + 1
            while cursor < n and tokens[cursor].value != "{":
                cursor += 1
            if cursor >= n:
                incomplete = True
                break
            close = matching_punct(tokens, cursor, "{", "}")
            if close < 0:
                incomplete = True
                break
            body = tokens[cursor + 1 : close]
            nested, inner_incomplete = _extract_in_type(
                path=path,
                text=text,
                role=role,
                type_name=name,
                body=body,
            )
            records.extend(nested)
            incomplete = incomplete or inner_incomplete
            index = close + 1
            continue
        index += 1
    ordered = tuple(sorted(records, key=lambda item: (item.span.line_start, item.qualified_name)))
    return ordered, incomplete


def _extract_in_type(
    *,
    path: str,
    text: str,
    role: FileRole,
    type_name: str,
    body: tuple[Token, ...],
) -> tuple[list[FunctionRecord], bool]:
    records: list[FunctionRecord] = []
    incomplete = False
    index = 0
    n = len(body)
    while index < n:
        token = body[index]
        if token.kind == "keyword" and token.value in _TYPE_KEYWORDS:
            cursor = index + 1
            while cursor < n and body[cursor].value != "{":
                cursor += 1
            if cursor >= n or body[cursor].value != "{":
                incomplete = True
                break
            close = matching_punct(body, cursor, "{", "}")
            if close < 0:
                incomplete = True
                break
            nested_name = ""
            if index + 1 < n and body[index + 1].kind == "ident":
                nested_name = body[index + 1].value
            owner = f"{type_name}.{nested_name}" if type_name else nested_name
            nested, inner_incomplete = _extract_in_type(
                path=path,
                text=text,
                role=role,
                type_name=owner,
                body=body[cursor + 1 : close],
            )
            records.extend(nested)
            incomplete = incomplete or inner_incomplete
            index = close + 1
            continue
        header = _method_header(body, index)
        if header is None:
            index += 1
            continue
        name, params_open, brace_open = header
        params_close = matching_punct(body, params_open, "(", ")")
        brace_close = matching_punct(body, brace_open, "{", "}")
        if params_close < 0 or brace_close < 0:
            incomplete = True
            index += 1
            continue
        fn_tokens = body[brace_open + 1 : brace_close]
        cyclomatic, nesting, branches, witnesses, inner_incomplete = measure_cfamily_body(
            fn_tokens, javascript=False
        )
        incomplete = incomplete or inner_incomplete
        line_start = body[index].line
        line_end = body[brace_close].line
        qualified = f"{type_name}.{name}" if type_name else name
        status = FunctionStatus.UNKNOWN if inner_incomplete else FunctionStatus.MEASURED
        records.append(
            FunctionRecord(
                function_id=f"java:{path}:{qualified}@{line_start}",
                language="java",
                path=path,
                name=name,
                qualified_name=qualified,
                span=SourceSpan(path=path, line_start=line_start, line_end=line_end),
                role=role,
                status=status,
                cyclomatic=None if inner_incomplete else cyclomatic,
                branch_count=None if inner_incomplete else len(branches),
                nloc=nloc_in_span(text, language="java", line_start=line_start, line_end=line_end),
                max_nesting_depth=None if inner_incomplete else nesting,
                cyclomatic_version=CYCLOMATIC_FORMULA_VERSION,
                nesting_version=NESTING_FORMULA_VERSION,
                size_version=SIZE_FORMULA_VERSION,
                branch_map_language=BRANCH_MAPS["java"].language,
                branches=() if inner_incomplete else branches,
                nesting_witness=() if inner_incomplete else witnesses,
                unknown_reason="unbalanced_block" if inner_incomplete else None,
            )
        )
        index = brace_close + 1
    return records, incomplete


def _method_header(tokens: tuple[Token, ...], index: int) -> tuple[str, int, int] | None:
    """Return (name, params_open, brace_open) when a method/ctor starts at index."""

    n = len(tokens)
    cursor = index
    saw_type_or_name = False
    name: str | None = None
    while cursor < n and tokens[cursor].kind == "keyword" and tokens[cursor].value in _MODIFIERS:
        cursor += 1
    if cursor >= n:
        return None
    # Walk type tokens then name, or constructor name.
    while cursor < n:
        token = tokens[cursor]
        if token.value == "(" and name is not None:
            params_open = cursor
            close = matching_punct(tokens, params_open, "(", ")")
            if close < 0:
                return None
            after = close + 1
            while after < n and tokens[after].kind == "keyword" and tokens[after].value == "throws":
                after += 1
                while after < n and tokens[after].value not in {"{", ";"}:
                    after += 1
            if after < n and tokens[after].value == "{":
                return name, params_open, after
            return None
        if token.value in {"{", ";", "="}:
            return None
        if token.kind in {"ident", "keyword"} and token.value not in _MODIFIERS:
            if token.value in _TYPE_KEYWORDS:
                return None
            name = token.value
            saw_type_or_name = True
            cursor += 1
            # Skip generics / arrays after a type or name.
            if cursor < n and tokens[cursor].value == "<":
                close = matching_punct(tokens, cursor, "<", ">")
                cursor = close + 1 if close >= 0 else cursor + 1
            while cursor < n and tokens[cursor].value in {"[", "]"}:
                cursor += 1
            continue
        if token.value in {"<", "[", ".", ",", "?"}:
            cursor += 1
            continue
        if token.value == ">":
            cursor += 1
            continue
        cursor += 1
        if cursor - index > 40 and not saw_type_or_name:
            return None
    return None


__all__ = ["extract_java_functions"]
