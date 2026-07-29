"""Tests for filename/extension language detection."""

from __future__ import annotations

import pytest

from codestrata.services.inventory import FilenameLanguageDetector


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/App.java", "Java"),
        ("index.php", "PHP"),
        ("app.js", "JavaScript"),
        ("app.ts", "TypeScript"),
        ("main.py", "Python"),
        ("Program.cs", "C#"),
        ("main.go", "Go"),
        ("App.kt", "Kotlin"),
        ("Main.scala", "Scala"),
        ("pom.xml", "XML"),
        ("application.yml", "YAML"),
        ("application.yaml", "YAML"),
        ("package.json", "JSON"),
        ("README.md", "Markdown"),
        ("unknown.bin", None),
    ],
)
def test_language_detection(path: str, expected: str | None) -> None:
    assert FilenameLanguageDetector().detect(path) == expected
