"""Filename/extension language detection for inventory entries.

Detection is path-based only. No source parsing or content inspection.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Exact basenames (case-insensitive) mapped before extension lookup.
_BASENAME_LANGUAGES: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "cmakelists.txt": "CMake",
    "gemfile": "Ruby",
}

# Extension → display language name.
_EXTENSION_LANGUAGES: dict[str, str] = {
    ".java": "Java",
    ".php": "PHP",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".py": "Python",
    ".pyi": "Python",
    ".cs": "C#",
    ".go": "Go",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".swift": "Swift",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".xml": "XML",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".toml": "TOML",
    ".ini": "INI",
    ".properties": "Java Properties",
    ".gradle": "Gradle",
}


class FilenameLanguageDetector:
    """Detect language from filename and extension only."""

    def detect(self, relative_path: str) -> str | None:
        """Return a language label, or ``None`` when unknown."""

        name = PurePosixPath(relative_path.replace("\\", "/")).name
        lowered = name.lower()
        if lowered in _BASENAME_LANGUAGES:
            return _BASENAME_LANGUAGES[lowered]

        # Prefer the longest matching multi-part extension (e.g. .d.ts).
        for extension, language in sorted(
            _EXTENSION_LANGUAGES.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if lowered.endswith(extension):
                return language
        return None
