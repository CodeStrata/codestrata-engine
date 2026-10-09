"""JavaScript/TypeScript function extraction (javascript.cyclomatic.v1).

Optional chaining, nullish coalescing and switch expressions stay unmapped.
Nested functions and arrow bodies are separate functions.
"""

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


def extract_js_functions(
    *,
    path: str,
    text: str,
    role: FileRole,
    language: str,
) -> tuple[tuple[FunctionRecord, ...], bool]:
    tokens = tokenize_source(text, language=language)
    records, incomplete = _scan_functions(
        path=path,
        text=text,
        role=role,
        language=language,
        tokens=tokens,
        start=0,
        end=len(tokens),
        owner="",
    )
    ordered = tuple(sorted(records, key=lambda item: (item.span.line_start, item.qualified_name)))
    return ordered, incomplete


def _scan_functions(
    *,
    path: str,
    text: str,
    role: FileRole,
    language: str,
    tokens: tuple[Token, ...],
    start: int,
    end: int,
    owner: str,
) -> tuple[list[FunctionRecord], bool]:
    records: list[FunctionRecord] = []
    incomplete = False
    index = start
    while index < end:
        token = tokens[index]
        if token.kind == "keyword" and token.value == "function":
            name, body_open, body_close = _function_span(tokens, index)
            if body_open < 0 or body_close < 0:
                incomplete = True
                index += 1
                continue
            fn_name = name or f"<anonymous>@{token.line}"
            record, inner_incomplete = _record_from_body(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                name=fn_name,
                owner=owner,
                header_line=token.line,
                body_open=body_open,
                body_close=body_close,
            )
            records.append(record)
            nested, nested_incomplete = _scan_functions(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                start=body_open + 1,
                end=body_close,
                owner=record.qualified_name,
            )
            records.extend(nested)
            incomplete = incomplete or inner_incomplete or nested_incomplete
            index = body_close + 1
            continue
        if token.value == "=>":
            body_open, body_close = _arrow_body(tokens, index)
            if body_open < 0:
                index += 1
                continue
            fn_name = f"<arrow>@{token.line}"
            record, inner_incomplete = _record_from_body(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                name=fn_name,
                owner=owner,
                header_line=token.line,
                body_open=body_open,
                body_close=body_close,
            )
            records.append(record)
            if body_open < body_close and tokens[body_open].value == "{":
                nested, nested_incomplete = _scan_functions(
                    path=path,
                    text=text,
                    role=role,
                    language=language,
                    tokens=tokens,
                    start=body_open + 1,
                    end=body_close,
                    owner=record.qualified_name,
                )
                records.extend(nested)
                incomplete = incomplete or nested_incomplete
            incomplete = incomplete or inner_incomplete
            index = body_close + 1
            continue
        if token.kind == "keyword" and token.value == "class":
            cursor = index + 1
            class_name = (
                tokens[cursor].value
                if cursor < end and tokens[cursor].kind == "ident"
                else f"<class>@{token.line}"
            )
            while cursor < end and tokens[cursor].value != "{":
                cursor += 1
            if cursor < end and tokens[cursor].value == "{":
                close = matching_punct(tokens, cursor, "{", "}")
                if close < 0:
                    incomplete = True
                    index += 1
                    continue
                nested, nested_incomplete = _scan_class_methods(
                    path=path,
                    text=text,
                    role=role,
                    language=language,
                    tokens=tokens,
                    start=cursor + 1,
                    end=close,
                    owner=class_name,
                )
                records.extend(nested)
                incomplete = incomplete or nested_incomplete
                index = close + 1
                continue
        index += 1
    return records, incomplete


def _scan_class_methods(
    *,
    path: str,
    text: str,
    role: FileRole,
    language: str,
    tokens: tuple[Token, ...],
    start: int,
    end: int,
    owner: str,
) -> tuple[list[FunctionRecord], bool]:
    records: list[FunctionRecord] = []
    incomplete = False
    index = start
    while index < end:
        token = tokens[index]
        if token.kind in {"ident", "keyword"} and token.value not in {"class", "function"}:
            cursor = index + 1
            if cursor < end and tokens[cursor].value == "(":
                params_close = matching_punct(tokens, cursor, "(", ")")
                after = params_close + 1 if params_close >= 0 else cursor + 1
                after = _skip_type_annotation(tokens, after)
                if after < end and tokens[after].value == "{":
                    close = matching_punct(tokens, after, "{", "}")
                    if close < 0:
                        incomplete = True
                        index += 1
                        continue
                    record, inner_incomplete = _record_from_body(
                        path=path,
                        text=text,
                        role=role,
                        language=language,
                        tokens=tokens,
                        name=token.value,
                        owner=owner,
                        header_line=token.line,
                        body_open=after,
                        body_close=close,
                    )
                    records.append(record)
                    nested, nested_incomplete = _scan_functions(
                        path=path,
                        text=text,
                        role=role,
                        language=language,
                        tokens=tokens,
                        start=after + 1,
                        end=close,
                        owner=record.qualified_name,
                    )
                    records.extend(nested)
                    incomplete = incomplete or inner_incomplete or nested_incomplete
                    index = close + 1
                    continue
        if token.kind == "keyword" and token.value == "function":
            nested, nested_incomplete = _scan_functions(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                start=index,
                end=index + 1,
                owner=owner,
            )
            # Fall through to generic function scan of remaining region.
            rest, rest_incomplete = _scan_functions(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                start=index,
                end=end,
                owner=owner,
            )
            records.extend(rest)
            return records, incomplete or nested_incomplete or rest_incomplete
        if token.value == "=>":
            rest, rest_incomplete = _scan_functions(
                path=path,
                text=text,
                role=role,
                language=language,
                tokens=tokens,
                start=index,
                end=end,
                owner=owner,
            )
            records.extend(rest)
            return records, incomplete or rest_incomplete
        index += 1
    return records, incomplete


def _skip_type_annotation(tokens: tuple[Token, ...], index: int) -> int:
    """Skip a TypeScript `: Type` annotation so `{` is the function body."""

    cursor = index
    if cursor >= len(tokens) or tokens[cursor].value != ":":
        return index
    cursor += 1
    depth_angle = 0
    while cursor < len(tokens):
        value = tokens[cursor].value
        if value == "<":
            depth_angle += 1
        elif value == ">":
            depth_angle = max(depth_angle - 1, 0)
        elif value == "{" and depth_angle == 0:
            return cursor
        elif value in {";", ",", "=>"} and depth_angle == 0:
            return cursor
        cursor += 1
    return index


def _function_span(tokens: tuple[Token, ...], index: int) -> tuple[str, int, int]:
    cursor = index + 1
    if cursor < len(tokens) and tokens[cursor].value == "*":
        cursor += 1
    name = ""
    if cursor < len(tokens) and tokens[cursor].kind == "ident":
        name = tokens[cursor].value
        cursor += 1
    if cursor < len(tokens) and tokens[cursor].value == "(":
        close = matching_punct(tokens, cursor, "(", ")")
        cursor = close + 1 if close >= 0 else cursor + 1
    cursor = _skip_type_annotation(tokens, cursor)
    if cursor < len(tokens) and tokens[cursor].value == "{":
        close = matching_punct(tokens, cursor, "{", "}")
        return name, cursor, close
    return name, -1, -1


def _arrow_body(tokens: tuple[Token, ...], index: int) -> tuple[int, int]:
    cursor = index + 1
    if cursor < len(tokens) and tokens[cursor].value == "{":
        close = matching_punct(tokens, cursor, "{", "}")
        return cursor, close
    start = cursor
    while cursor < len(tokens) and tokens[cursor].value not in {",", ";", ")", "}", "]"}:
        if tokens[cursor].value == "(":
            nested = matching_punct(tokens, cursor, "(", ")")
            cursor = nested + 1 if nested >= 0 else cursor + 1
            continue
        cursor += 1
    if cursor <= start:
        return -1, -1
    return start - 1, cursor - 1


def _record_from_body(
    *,
    path: str,
    text: str,
    role: FileRole,
    language: str,
    tokens: tuple[Token, ...],
    name: str,
    owner: str,
    header_line: int,
    body_open: int,
    body_close: int,
) -> tuple[FunctionRecord, bool]:
    if body_open < 0 or body_close < 0 or body_close >= len(tokens):
        qualified = f"{owner}.{name}" if owner else name
        return (
            FunctionRecord(
                function_id=f"{language}:{path}:{qualified}@{header_line}",
                language=language,
                path=path,
                name=name,
                qualified_name=qualified,
                span=SourceSpan(path=path, line_start=header_line, line_end=header_line),
                role=role,
                status=FunctionStatus.UNKNOWN,
                cyclomatic_version=CYCLOMATIC_FORMULA_VERSION,
                nesting_version=NESTING_FORMULA_VERSION,
                size_version=SIZE_FORMULA_VERSION,
                branch_map_language=BRANCH_MAPS[language].language,
                unknown_reason="unbalanced_block",
            ),
            True,
        )
    if tokens[body_open].value == "{":
        body = tokens[body_open + 1 : body_close]
        line_end = tokens[body_close].line
    else:
        body = tokens[body_open + 1 : body_close + 1]
        line_end = tokens[body_close].line
    cyclomatic, nesting, branches, witnesses, incomplete = measure_cfamily_body(
        body, javascript=True
    )
    qualified = f"{owner}.{name}" if owner else name
    status = FunctionStatus.UNKNOWN if incomplete else FunctionStatus.MEASURED
    return (
        FunctionRecord(
            function_id=f"{language}:{path}:{qualified}@{header_line}",
            language=language,
            path=path,
            name=name,
            qualified_name=qualified,
            span=SourceSpan(path=path, line_start=header_line, line_end=line_end),
            role=role,
            status=status,
            cyclomatic=None if incomplete else cyclomatic,
            branch_count=None if incomplete else len(branches),
            nloc=nloc_in_span(text, language=language, line_start=header_line, line_end=line_end),
            max_nesting_depth=None if incomplete else nesting,
            cyclomatic_version=CYCLOMATIC_FORMULA_VERSION,
            nesting_version=NESTING_FORMULA_VERSION,
            size_version=SIZE_FORMULA_VERSION,
            branch_map_language=BRANCH_MAPS[language].language,
            branches=() if incomplete else branches,
            nesting_witness=() if incomplete else witnesses,
            unknown_reason="unbalanced_block" if incomplete else None,
        ),
        incomplete,
    )


__all__ = ["extract_js_functions"]
