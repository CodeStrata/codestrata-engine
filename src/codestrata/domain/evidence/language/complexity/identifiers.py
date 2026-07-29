"""Stable identity helpers for complexity evidence."""

from __future__ import annotations

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

COMPLEXITY_BUNDLE_SCHEMA_VERSION = "1.0.0"
COMPLEXITY_ARTIFACT_FILENAME = "complexity-evidence.json"

PYTHON_COMPLEXITY_PROVIDER_ID = "language.python.complexity"
PYTHON_COMPLEXITY_PROVIDER_VERSION = "1.0.0"
JAVA_COMPLEXITY_PROVIDER_ID = "language.java.complexity"
JAVA_COMPLEXITY_PROVIDER_VERSION = "1.0.0"
PHP_COMPLEXITY_PROVIDER_ID = "language.php.complexity"
PHP_COMPLEXITY_PROVIDER_VERSION = "1.0.0"
CSHARP_COMPLEXITY_PROVIDER_ID = "language.csharp.complexity"
CSHARP_COMPLEXITY_PROVIDER_VERSION = "1.0.0"


def make_file_complexity_id(*, provider_id: str, language: str, path: str) -> str:
    return stable_evidence_id("complexity.file", provider_id, language, path)


def make_type_complexity_id(
    *,
    provider_id: str,
    language: str,
    path: str,
    qualified_name: str,
) -> str:
    return stable_evidence_id(
        "complexity.type", provider_id, language, path, qualified_name
    )


def make_callable_complexity_id(
    *,
    provider_id: str,
    language: str,
    path: str,
    qualified_signature: str,
) -> str:
    return stable_evidence_id(
        "complexity.callable",
        provider_id,
        language,
        path,
        qualified_signature,
    )
