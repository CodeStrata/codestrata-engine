"""Language-specific tokenizers for complexity walks and clone normalization."""

from __future__ import annotations

import io
import tokenize as py_tokenize
from dataclasses import dataclass
from token import COMMENT, ENCODING, ENDMARKER, NL, NUMBER, STRING
from token import NAME as PY_NAME
from token import NEWLINE as PY_NEWLINE
from token import OP as PY_OP

from codestrata.application.evidence.quality.maps import TOKEN_MAPS

JAVA_KEYWORDS = frozenset(
    {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "null",
        "record",
        "var",
        "yield",
    }
)
JS_KEYWORDS = frozenset(
    {
        "abstract",
        "as",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "from",
        "function",
        "get",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "null",
        "of",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "set",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
        "type",
        "namespace",
        "declare",
        "readonly",
        "keyof",
        "infer",
        "never",
        "unknown",
        "any",
        "boolean",
        "number",
        "string",
        "symbol",
        "undefined",
    }
)
PYTHON_KEYWORDS = frozenset(
    {
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "match",
        "case",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        "True",
        "False",
        "None",
    }
)


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int
    raw: str = ""


def _keywords_for(language: str) -> frozenset[str]:
    if language == "java":
        return JAVA_KEYWORDS
    if language in {"javascript", "typescript"}:
        return JS_KEYWORDS
    if language == "python":
        return PYTHON_KEYWORDS
    return frozenset()


def tokenize_source(text: str, *, language: str) -> tuple[Token, ...]:
    if language == "python":
        return _tokenize_python(text)
    if language in {"java", "javascript", "typescript"}:
        return _tokenize_cfamily(text, language=language)
    return ()


def classify_lines(tokens: tuple[Token, ...]) -> frozenset[int]:
    """Nonblank noncomment physical lines that carried a kept token."""

    lines = {token.line for token in tokens if token.kind not in {"comment", "whitespace"}}
    return frozenset(line for line in lines if line >= 1)


def normalize_tokens(tokens: tuple[Token, ...], *, language: str) -> tuple[Token, ...]:
    mapping = TOKEN_MAPS[language]
    out: list[Token] = []
    for token in tokens:
        if token.kind in mapping.drop or token.kind in {"whitespace", "comment"}:
            continue
        if token.kind == "string":
            out.append(
                Token(
                    kind="string",
                    value=mapping.replace_string,
                    line=token.line,
                    column=token.column,
                    raw=token.raw,
                )
            )
            continue
        if token.kind == "number":
            out.append(
                Token(
                    kind="number",
                    value=mapping.replace_number,
                    line=token.line,
                    column=token.column,
                    raw=token.raw,
                )
            )
            continue
        out.append(token)
    return tuple(out)


def clone_key(token: Token) -> str:
    return f"{token.kind}\0{token.value}"


def _tokenize_python(text: str) -> tuple[Token, ...]:
    out: list[Token] = []
    reader = io.StringIO(text).readline
    try:
        for item in py_tokenize.generate_tokens(reader):
            if item.type in {ENCODING, ENDMARKER, PY_NEWLINE, NL}:
                continue
            line = int(item.start[0] or 1)
            column = int(item.start[1] or 0)
            raw = item.string
            if item.type == COMMENT:
                out.append(Token(kind="comment", value=raw, line=line, column=column, raw=raw))
                continue
            if item.type == STRING:
                out.append(Token(kind="string", value=raw, line=line, column=column, raw=raw))
                continue
            if item.type == NUMBER:
                out.append(Token(kind="number", value=raw, line=line, column=column, raw=raw))
                continue
            if item.type == PY_NAME:
                kind = "keyword" if raw in PYTHON_KEYWORDS else "ident"
                out.append(Token(kind=kind, value=raw, line=line, column=column, raw=raw))
                continue
            if item.type == PY_OP:
                out.append(Token(kind="punct", value=raw, line=line, column=column, raw=raw))
                continue
            if raw.strip():
                out.append(Token(kind="punct", value=raw, line=line, column=column, raw=raw))
    except (py_tokenize.TokenError, IndentationError, SyntaxError):
        return tuple(out)
    return tuple(out)


def _tokenize_cfamily(text: str, *, language: str) -> tuple[Token, ...]:
    keywords = _keywords_for(language)
    out: list[Token] = []
    i = 0
    n = len(text)
    line = 1
    column = 0
    template_ok = language in {"javascript", "typescript"}

    def push(
        kind: str,
        value: str,
        start_line: int,
        start_col: int,
        raw: str | None = None,
    ) -> None:
        out.append(
            Token(
                kind=kind,
                value=value,
                line=start_line,
                column=start_col,
                raw=raw or value,
            )
        )

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "\n":
            line += 1
            column = 0
            i += 1
            continue
        if ch in " \t\r\f":
            column += 1
            i += 1
            continue
        if ch == "/" and nxt == "/":
            start_line, start_col = line, column
            raw = []
            while i < n and text[i] != "\n":
                raw.append(text[i])
                i += 1
                column += 1
            push("comment", "".join(raw), start_line, start_col)
            continue
        if ch == "/" and nxt == "*":
            start_line, start_col = line, column
            raw = ["/", "*"]
            i += 2
            column += 2
            while i < n - 1 and not (text[i] == "*" and text[i + 1] == "/"):
                if text[i] == "\n":
                    line += 1
                    column = 0
                else:
                    column += 1
                raw.append(text[i])
                i += 1
            if i < n - 1:
                raw.extend(["*", "/"])
                i += 2
                column += 2
            push("comment", "".join(raw), start_line, start_col)
            continue
        if ch in {'"', "'"} or (template_ok and ch == "`"):
            quote = ch
            start_line, start_col = line, column
            raw = [ch]
            i += 1
            column += 1
            while i < n:
                cur = text[i]
                raw.append(cur)
                if cur == "\\" and i + 1 < n:
                    raw.append(text[i + 1])
                    i += 2
                    column += 2
                    continue
                if cur == "\n":
                    line += 1
                    column = 0
                    i += 1
                    if quote != "`":
                        break
                    continue
                i += 1
                column += 1
                if cur == quote:
                    break
            push("string", "".join(raw), start_line, start_col)
            continue
        if ch.isdigit():
            start_line, start_col = line, column
            raw = [ch]
            i += 1
            column += 1
            while i < n and (text[i].isalnum() or text[i] in "._"):
                raw.append(text[i])
                i += 1
                column += 1
            push("number", "".join(raw), start_line, start_col)
            continue
        if ch.isalpha() or ch in "_$":
            start_line, start_col = line, column
            raw = [ch]
            i += 1
            column += 1
            while i < n and (text[i].isalnum() or text[i] in "_$"):
                raw.append(text[i])
                i += 1
                column += 1
            word = "".join(raw)
            kind = "keyword" if word in keywords else "ident"
            push(kind, word, start_line, start_col)
            continue
        two = ch + nxt
        start_line, start_col = line, column
        if two in {"&&", "||", "??", "?.", "=>", "==", "!=", "<=", ">=", "++", "--", "<<", ">>"}:
            push("punct", two, start_line, start_col)
            i += 2
            column += 2
            continue
        if language in {"javascript", "typescript"} and i + 2 < n and text[i : i + 3] == "===":
            push("punct", "===", start_line, start_col)
            i += 3
            column += 3
            continue
        if language in {"javascript", "typescript"} and i + 2 < n and text[i : i + 3] == "!==":
            push("punct", "!==", start_line, start_col)
            i += 3
            column += 3
            continue
        push("punct", ch, start_line, start_col)
        i += 1
        column += 1
    return tuple(out)


__all__ = [
    "Token",
    "classify_lines",
    "clone_key",
    "normalize_tokens",
    "tokenize_source",
]
