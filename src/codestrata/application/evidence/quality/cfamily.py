"""Shared C-family body walk for Java/JS/TS cyclomatic v1 and nesting v1.

Counts declared constructs from the frozen language map. Nested function
bodies are excluded from the enclosing function. Else/default/finally do not
add decisions. Optional chaining and nullish coalescing stay unmapped.
"""

from __future__ import annotations

from collections.abc import Callable

from codestrata.application.evidence.quality.maps import CYCLOMATIC_BASE
from codestrata.application.evidence.quality.models import BranchWitness
from codestrata.application.evidence.quality.tokenize import Token

EnterFn = Callable[[str, int], None]


def matching_punct(tokens: tuple[Token, ...], open_index: int, opener: str, closer: str) -> int:
    if open_index < 0 or open_index >= len(tokens) or tokens[open_index].value != opener:
        return -1
    depth = 0
    for index in range(open_index, len(tokens)):
        value = tokens[index].value
        if value == opener:
            depth += 1
        elif value == closer:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _skip_nested(tokens: tuple[Token, ...], index: int, *, javascript: bool) -> int:
    """Index after a nested function/class/lambda, or ``index`` if none starts here."""

    token = tokens[index]
    if javascript and token.kind == "keyword" and token.value == "function":
        return _skip_js_function(tokens, index)
    if javascript and token.value == "=>":
        return _skip_arrow(tokens, index)
    if token.value == "->" and not javascript:
        return _skip_arrow(tokens, index)
    if token.kind == "keyword" and token.value in {"class", "interface", "enum", "record"}:
        cursor = index + 1
        while cursor < len(tokens) and tokens[cursor].value != "{":
            cursor += 1
        if cursor < len(tokens) and tokens[cursor].value == "{":
            close = matching_punct(tokens, cursor, "{", "}")
            return close + 1 if close >= 0 else index
    return index


def _skip_js_function(tokens: tuple[Token, ...], index: int) -> int:
    cursor = index + 1
    if cursor < len(tokens) and tokens[cursor].value == "*":
        cursor += 1
    if cursor < len(tokens) and tokens[cursor].kind == "ident":
        cursor += 1
    if cursor < len(tokens) and tokens[cursor].value == "(":
        close = matching_punct(tokens, cursor, "(", ")")
        if close < 0:
            return index
        cursor = close + 1
    if cursor < len(tokens) and tokens[cursor].value == "{":
        close = matching_punct(tokens, cursor, "{", "}")
        return close + 1 if close >= 0 else index
    return cursor


def _skip_arrow(tokens: tuple[Token, ...], index: int) -> int:
    cursor = index + 1
    if cursor < len(tokens) and tokens[cursor].value == "{":
        close = matching_punct(tokens, cursor, "{", "}")
        return close + 1 if close >= 0 else index
    while cursor < len(tokens) and tokens[cursor].value not in {",", ";", ")", "}", "]"}:
        if tokens[cursor].value == "(":
            nested = matching_punct(tokens, cursor, "(", ")")
            cursor = nested + 1 if nested >= 0 else cursor + 1
            continue
        if tokens[cursor].value == "{":
            nested = matching_punct(tokens, cursor, "{", "}")
            cursor = nested + 1 if nested >= 0 else cursor + 1
            continue
        cursor += 1
    return cursor


def measure_cfamily_body(
    tokens: tuple[Token, ...],
    *,
    javascript: bool,
) -> tuple[int, int, tuple[BranchWitness, ...], tuple[BranchWitness, ...], bool]:
    """Return (cyclomatic, max_nesting, branches, nesting witnesses, incomplete)."""

    branches: list[BranchWitness] = []
    nesting_witness: list[BranchWitness] = []
    deepest = 0
    incomplete = False
    index = 0
    pending_do = False
    n = len(tokens)

    def bump(construct: str, line: int) -> None:
        branches.append(BranchWitness(syntax=construct, line=line))

    while index < n:
        skipped = _skip_nested(tokens, index, javascript=javascript)
        if skipped != index:
            if skipped <= index:
                incomplete = True
                index += 1
            else:
                index = skipped
            continue
        token = tokens[index]
        value = token.value
        control = {"if", "for", "while", "catch", "switch", "try", "do"}
        if token.kind == "keyword" and value in control:
            if value == "while" and pending_do:
                bump("do_while", token.line)
                pending_do = False
                if index + 1 < n and tokens[index + 1].value == "(":
                    close = matching_punct(tokens, index + 1, "(", ")")
                    if close >= 0:
                        _scan_expr_decisions(tokens[index + 2 : close], branches)
                        index = close + 1
                        continue
                index = _skip_paren(tokens, index + 1)
                continue
            if value == "if":
                bump("if", token.line)
            elif value == "for":
                bump("for", token.line)
            elif value == "while":
                bump("while", token.line)
            elif value == "catch":
                bump("catch", token.line)
            elif value == "do":
                pending_do = True
            after, inner_depth, inner_incomplete = _control_body(
                tokens,
                index,
                construct=value,
                javascript=javascript,
                branches=branches,
                nesting_witness=nesting_witness,
            )
            deepest = max(deepest, inner_depth)
            incomplete = incomplete or inner_incomplete
            if after <= index:
                incomplete = True
                index += 1
            else:
                index = after
            continue
        if token.kind == "keyword" and value == "case":
            bump("switch_case_non_default", token.line)
            index += 1
            continue
        if token.kind == "keyword" and value in {"else", "finally", "default"}:
            index += 1
            continue
        if token.value == "?" and token.kind == "punct":
            bump("ternary", token.line)
            index += 1
            continue
        if token.value == "&&":
            bump("logical_and", token.line)
            index += 1
            continue
        if token.value == "||":
            bump("logical_or", token.line)
            index += 1
            continue
        if token.value in {"?.", "??"}:
            index += 1
            continue
        if token.value == "{":
            close = matching_punct(tokens, index, "{", "}")
            if close < 0:
                incomplete = True
                index += 1
                continue
            inner = measure_cfamily_body(tokens[index + 1 : close], javascript=javascript)
            branches.extend(inner[2])
            nesting_witness.extend(inner[3])
            deepest = max(deepest, inner[1])
            incomplete = incomplete or inner[4]
            index = close + 1
            continue
        index += 1

    return (
        CYCLOMATIC_BASE + len(branches),
        deepest,
        tuple(branches),
        tuple(nesting_witness),
        incomplete,
    )


def _skip_paren(tokens: tuple[Token, ...], index: int) -> int:
    if index < len(tokens) and tokens[index].value == "(":
        close = matching_punct(tokens, index, "(", ")")
        return close + 1 if close >= 0 else index + 1
    return index


def _control_body(
    tokens: tuple[Token, ...],
    index: int,
    *,
    construct: str,
    javascript: bool,
    branches: list[BranchWitness],
    nesting_witness: list[BranchWitness],
) -> tuple[int, int, bool]:
    """Parse a control construct. Returns (index_after, max_depth, incomplete)."""

    cursor = index + 1
    if construct != "do" and cursor < len(tokens) and tokens[cursor].value == "(":
        close = matching_punct(tokens, cursor, "(", ")")
        if close < 0:
            return index + 1, 1, True
        _scan_expr_decisions(tokens[cursor + 1 : close], branches)
        cursor = close + 1
    line = tokens[index].line
    if cursor < len(tokens) and tokens[cursor].value == "{":
        close = matching_punct(tokens, cursor, "{", "}")
        if close < 0:
            return cursor + 1, 1, True
        inner = measure_cfamily_body(tokens[cursor + 1 : close], javascript=javascript)
        branches.extend(inner[2])
        nesting_witness.append(BranchWitness(syntax=construct, line=line))
        nesting_witness.extend(inner[3])
        return close + 1, 1 + inner[1], inner[4]
    end = _statement_end(tokens, cursor)
    inner = measure_cfamily_body(tokens[cursor:end], javascript=javascript)
    branches.extend(inner[2])
    nesting_witness.append(BranchWitness(syntax=construct, line=line))
    nesting_witness.extend(inner[3])
    return end, 1 + inner[1], inner[4]


def _scan_expr_decisions(tokens: tuple[Token, ...], branches: list[BranchWitness]) -> None:
    for token in tokens:
        if token.value == "&&":
            branches.append(BranchWitness(syntax="logical_and", line=token.line))
        elif token.value == "||":
            branches.append(BranchWitness(syntax="logical_or", line=token.line))
        elif token.value == "?" and token.kind == "punct":
            branches.append(BranchWitness(syntax="ternary", line=token.line))


def _statement_end(tokens: tuple[Token, ...], start: int) -> int:
    depth_paren = 0
    index = start
    while index < len(tokens):
        value = tokens[index].value
        if value == "(":
            depth_paren += 1
        elif value == ")":
            depth_paren = max(depth_paren - 1, 0)
        elif value == "{" and depth_paren == 0:
            close = matching_punct(tokens, index, "{", "}")
            return close + 1 if close >= 0 else index + 1
        elif value == ";" and depth_paren == 0:
            return index + 1
        index += 1
    return index


__all__ = ["matching_punct", "measure_cfamily_body"]
