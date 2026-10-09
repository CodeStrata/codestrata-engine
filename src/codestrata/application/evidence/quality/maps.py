"""Frozen language-specific branch, nesting and token-normalization maps.

There is no language-independent maintainability index. Each supported
language has an explicit construct map and formula version. Unsupported
syntax is left unmapped rather than guessed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

CYCLOMATIC_FORMULA_VERSION = "cyclomatic.v1"
NESTING_FORMULA_VERSION = "nesting.v1"
TOKEN_NORMALIZATION_VERSION = "token.normalize.v1"
CLONE_FORMULA_VERSION = "clone.v1"
SIZE_FORMULA_VERSION = "nloc.v1"

# cyclomatic v1 = 1 + count of declared branch constructs (frozen per language).
CYCLOMATIC_BASE = 1
CLONE_MIN_TOKENS = 50
CLONE_MIN_LINES = 5
DEFAULT_COMPLEXITY_THRESHOLD = 15
DEFAULT_FUNCTION_SIZE_THRESHOLD = 80
DEFAULT_NESTING_THRESHOLD = 4
DEFAULT_CLONE_RATIO_THRESHOLD = 0.10

SUPPORTED_COMPLEXITY_LANGUAGES = frozenset({"java", "javascript", "typescript", "python"})
LANGUAGE_SUFFIXES: dict[str, frozenset[str]] = {
    "java": frozenset({".java"}),
    "javascript": frozenset({".js", ".jsx"}),
    "typescript": frozenset({".ts", ".tsx"}),
    "python": frozenset({".py"}),
    "php": frozenset({".php"}),
    "csharp": frozenset({".cs"}),
}

# Explicitly not counted until a parser/version mapping is published.
UNMAPPED_CONSTRUCTS: dict[str, tuple[str, ...]] = {
    "java": ("switch-expression", "record-pattern", "lambda-body-as-function"),
    "javascript": (
        "optional-chaining",
        "nullish-coalescing",
        "switch-expression",
    ),
    "typescript": (
        "optional-chaining",
        "nullish-coalescing",
        "switch-expression",
        "typescript-compiler-api",
    ),
    "python": ("exec-eval", "dynamic-import"),
}


class BranchMap(BaseModel):
    """Declared decision constructs for cyclomatic v1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    version: str = CYCLOMATIC_FORMULA_VERSION
    decisions: tuple[str, ...]
    excluded: tuple[str, ...]
    unmapped: tuple[str, ...] = ()
    nested_functions: str = "excluded_from_enclosing"


class NestingMap(BaseModel):
    """Declared control-flow constructs that increase nesting depth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    version: str = NESTING_FORMULA_VERSION
    enter: tuple[str, ...]
    same_depth_as_parent: tuple[str, ...]
    nested_functions: str = "separate_function"


class TokenNormalizeMap(BaseModel):
    """Declared token-normalization policy for clone detection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    version: str = TOKEN_NORMALIZATION_VERSION
    drop: tuple[str, ...]
    keep_identifiers: bool = True
    replace_string: str = "$STR"
    replace_number: str = "$NUM"
    rename_policy: str = "identifiers_kept_rename_is_not_clone"


JAVA_BRANCH = BranchMap(
    language="java",
    decisions=(
        "if",
        "for",
        "while",
        "do_while",
        "catch",
        "switch_case_non_default",
        "ternary",
        "logical_and",
        "logical_or",
    ),
    excluded=("else", "default", "finally", "nested_method", "lambda_body"),
    unmapped=UNMAPPED_CONSTRUCTS["java"],
)
JAVASCRIPT_BRANCH = BranchMap(
    language="javascript",
    decisions=(
        "if",
        "for",
        "for_in",
        "for_of",
        "while",
        "do_while",
        "catch",
        "switch_case_non_default",
        "ternary",
        "logical_and",
        "logical_or",
    ),
    excluded=("else", "default", "finally", "nested_function", "arrow_body"),
    unmapped=UNMAPPED_CONSTRUCTS["javascript"],
)
TYPESCRIPT_BRANCH = JAVASCRIPT_BRANCH.model_copy(update={"language": "typescript"})
PYTHON_BRANCH = BranchMap(
    language="python",
    decisions=(
        "if",
        "for",
        "async_for",
        "while",
        "except",
        "match_case_non_wildcard",
        "ifexp",
        "boolop_and",
        "boolop_or",
        "comprehension_if",
    ),
    excluded=("else", "elif_same_as_if", "finally", "wildcard_case", "nested_function"),
    unmapped=UNMAPPED_CONSTRUCTS["python"],
)

JAVA_NESTING = NestingMap(
    language="java",
    enter=("if", "for", "while", "do", "switch", "try", "catch"),
    same_depth_as_parent=("else", "finally", "default"),
)
JAVASCRIPT_NESTING = NestingMap(
    language="javascript",
    enter=("if", "for", "while", "do", "switch", "try", "catch"),
    same_depth_as_parent=("else", "finally", "default"),
)
TYPESCRIPT_NESTING = JAVASCRIPT_NESTING.model_copy(update={"language": "typescript"})
PYTHON_NESTING = NestingMap(
    language="python",
    enter=("if", "for", "async_for", "while", "with", "async_with", "try", "except", "match"),
    same_depth_as_parent=("else", "elif", "finally", "wildcard_case"),
)

_TOKEN_DROP = ("whitespace", "comment", "line_continuation")
JAVA_TOKEN = TokenNormalizeMap(language="java", drop=_TOKEN_DROP)
JAVASCRIPT_TOKEN = TokenNormalizeMap(language="javascript", drop=_TOKEN_DROP)
TYPESCRIPT_TOKEN = TokenNormalizeMap(language="typescript", drop=_TOKEN_DROP)
PYTHON_TOKEN = TokenNormalizeMap(language="python", drop=_TOKEN_DROP)

BRANCH_MAPS: dict[str, BranchMap] = {
    "java": JAVA_BRANCH,
    "javascript": JAVASCRIPT_BRANCH,
    "typescript": TYPESCRIPT_BRANCH,
    "python": PYTHON_BRANCH,
}
NESTING_MAPS: dict[str, NestingMap] = {
    "java": JAVA_NESTING,
    "javascript": JAVASCRIPT_NESTING,
    "typescript": TYPESCRIPT_NESTING,
    "python": PYTHON_NESTING,
}
TOKEN_MAPS: dict[str, TokenNormalizeMap] = {
    "java": JAVA_TOKEN,
    "javascript": JAVASCRIPT_TOKEN,
    "typescript": TYPESCRIPT_TOKEN,
    "python": PYTHON_TOKEN,
}


class QualityBudgets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_file_bytes: int = Field(default=1_048_576, ge=1)
    max_files: int = Field(default=2000, ge=1)
    max_tokens: int = Field(default=500_000, ge=1)


def language_for_path(path: str) -> str | None:
    lower = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if "." not in lower:
        return None
    suffix = "." + lower.rsplit(".", 1)[-1]
    # .tsx/.jsx take two-part suffixes already captured by last suffix.
    if lower.endswith(".tsx"):
        return "typescript"
    if lower.endswith(".ts"):
        return "typescript"
    if lower.endswith(".jsx") or lower.endswith(".js"):
        return "javascript"
    if lower.endswith(".php"):
        return "php"
    if lower.endswith(".cs"):
        return "csharp"
    for language, suffixes in LANGUAGE_SUFFIXES.items():
        if suffix in suffixes:
            return language
    return None


__all__ = [
    "BRANCH_MAPS",
    "CLONE_FORMULA_VERSION",
    "CLONE_MIN_LINES",
    "CLONE_MIN_TOKENS",
    "CYCLOMATIC_BASE",
    "CYCLOMATIC_FORMULA_VERSION",
    "DEFAULT_CLONE_RATIO_THRESHOLD",
    "DEFAULT_COMPLEXITY_THRESHOLD",
    "DEFAULT_FUNCTION_SIZE_THRESHOLD",
    "DEFAULT_NESTING_THRESHOLD",
    "LANGUAGE_SUFFIXES",
    "NESTING_FORMULA_VERSION",
    "NESTING_MAPS",
    "QualityBudgets",
    "SIZE_FORMULA_VERSION",
    "SUPPORTED_COMPLEXITY_LANGUAGES",
    "TOKEN_MAPS",
    "TOKEN_NORMALIZATION_VERSION",
    "language_for_path",
]
