"""Static test declarations by supported framework. No test execution."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.quality.maps import language_for_path
from codestrata.application.evidence.testing.capability import ASSOCIATION_FORMULA_VERSION
from codestrata.application.evidence.testing.models import SourceSpan, TestDeclaration
from codestrata.application.evidence.testing.paths import (
    is_generated_path,
    normalize_relative_path,
    unsupported_language_for_path,
)

_JAVA_TEST = re.compile(
    r"@(?:Test|ParameterizedTest|RepeatedTest|TestFactory)\b"
)
_JAVA_METHOD = re.compile(r"(?:public|protected|private|static|\s)+[\w.<>,\[\]]+\s+(\w+)\s*\(")
_JS_TEST = re.compile(
    r"\b(?:test|it|describe|xdescribe|xit)\s*\(\s*(['\"`])([^'\"`]+)\1"
)
_JS_FRAMEWORK_HINTS: tuple[tuple[str, str], ...] = (
    ("@playwright/test", "playwright"),
    ("cypress", "cypress"),
    ("vitest", "vitest"),
    ("mocha", "mocha"),
    ("jest", "jest"),
)


def _python_framework(tree: ast.AST) -> str:
    text_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            text_imports.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            text_imports.append(node.module.split(".", 1)[0])
    if "pytest" in text_imports:
        return "pytest"
    if "unittest" in text_imports:
        return "unittest"
    return "pytest"


def _python_declarations(path: str, text: str) -> list[TestDeclaration]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    framework = _python_framework(tree)
    generated = is_generated_path(path)
    found: list[TestDeclaration] = []

    def add(name: str, node: ast.AST, chosen: str) -> None:
        line = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", line) or line
        found.append(
            TestDeclaration(
                test_id=f"test:{path}:{name}:{line}",
                path=path,
                name=name,
                framework=chosen,
                language="python",
                span=SourceSpan(path=path, line_start=line, line_end=end),
                generated=generated,
            )
        )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            add(node.name, node, framework)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_framework = "unittest" if _extends_unittest(node) else framework
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    child.name.startswith("test") or child.name.startswith("test_")
                ):
                    add(f"{node.name}.{child.name}", child, class_framework)
    return found


def _extends_unittest(node: ast.ClassDef) -> bool:
    for base in node.bases:
        rendered = ast.unparse(base) if hasattr(ast, "unparse") else ""
        if "TestCase" in rendered or "unittest" in rendered:
            return True
    return False


def _java_declarations(path: str, text: str) -> list[TestDeclaration]:
    generated = is_generated_path(path)
    found: list[TestDeclaration] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if _JAVA_TEST.search(line) is None:
            continue
        name = None
        end = index + 1
        same = _JAVA_METHOD.search(line)
        if same:
            name = same.group(1)
        else:
            for ahead in range(index + 1, min(index + 8, len(lines))):
                match = _JAVA_METHOD.search(lines[ahead])
                if match:
                    name = match.group(1)
                    end = ahead + 1
                    break
        if name is None:
            continue
        framework = "junit_jupiter" if "ParameterizedTest" in line else "junit"
        found.append(
            TestDeclaration(
                test_id=f"test:{path}:{name}:{index + 1}",
                path=path,
                name=name,
                framework=framework,
                language="java",
                span=SourceSpan(path=path, line_start=index + 1, line_end=end),
                generated=generated,
            )
        )
    return found


def _js_framework(text: str) -> str:
    lowered = text.lower()
    for token, framework in _JS_FRAMEWORK_HINTS:
        if token in lowered:
            return framework
    return "jest"


def _js_declarations(path: str, text: str, language: str) -> list[TestDeclaration]:
    generated = is_generated_path(path)
    framework = _js_framework(text)
    found: list[TestDeclaration] = []
    for match in _JS_TEST.finditer(text):
        name = match.group(2)
        line = text.count("\n", 0, match.start()) + 1
        found.append(
            TestDeclaration(
                test_id=f"test:{path}:{name}:{line}",
                path=path,
                name=name,
                framework=framework,
                language=language,
                span=SourceSpan(path=path, line_start=line, line_end=line),
                generated=generated,
            )
        )
    return found


def collect_test_declarations(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    notes: list[str],
    max_file_bytes: int,
) -> tuple[TestDeclaration, ...]:
    results: list[TestDeclaration] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        text = file_texts.get(path, file_texts.get(raw))
        if text is None:
            continue
        if len(text.encode("utf-8")) > max_file_bytes:
            notes.append(f"file_over_budget:{path}")
            continue
        language = language_for_path(path)
        unsupported = unsupported_language_for_path(path)
        if unsupported and language is None:
            results.append(
                TestDeclaration(
                    test_id=f"test:{path}:unsupported:1",
                    path=path,
                    name=path,
                    framework=unsupported,
                    language=unsupported,
                    span=SourceSpan(path=path, line_start=1, line_end=1),
                    generated=is_generated_path(path),
                    unsupported_framework=True,
                )
            )
            continue
        if language == "python":
            results.extend(_python_declarations(path, text))
        elif language == "java":
            results.extend(_java_declarations(path, text))
        elif language in {"javascript", "typescript"}:
            results.extend(_js_declarations(path, text, language))
    results.sort(key=lambda item: item.test_id)
    _ = ASSOCIATION_FORMULA_VERSION
    return tuple(results)


__all__ = ["collect_test_declarations"]
