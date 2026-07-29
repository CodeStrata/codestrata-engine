"""Tests for deterministic repository security analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.models import Repository
from codestrata.services.analyzers.security_analyzer import (
    SecurityAnalyzer,
)


def _repository(
    root: Path,
    files: dict[str, str],
) -> Repository:
    """Create a repository fixture with the provided files."""

    relative_paths: list[str] = []

    for relative_path, content in files.items():
        file_path = root / relative_path
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        file_path.write_text(
            content,
            encoding="utf-8",
        )
        relative_paths.append(relative_path)

    return Repository(
        name=root.name,
        path=root,
        files=relative_paths,
    )


def _rule_ids(
    repository: Repository,
) -> list[str]:
    """Run the analyzer and return finding rule identifiers."""

    result = SecurityAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    return [finding.rule_id for finding in result.findings if finding.rule_id is not None]


def test_detects_committed_environment_file(
    tmp_path: Path,
) -> None:
    """A committed .env file should be reported."""

    repository = _repository(
        tmp_path,
        {
            ".env": "DATABASE_PASSWORD=actual-secret",
        },
    )

    assert "SEC001" in _rule_ids(repository)


def test_does_not_flag_environment_example_file(
    tmp_path: Path,
) -> None:
    """An example environment file should not be treated as sensitive."""

    repository = _repository(
        tmp_path,
        {
            ".env.example": "DATABASE_PASSWORD=changeme",
        },
    )

    assert "SEC001" not in _rule_ids(repository)


def test_detects_private_key_material(
    tmp_path: Path,
) -> None:
    """Embedded private keys should be reported as critical."""

    repository = _repository(
        tmp_path,
        {
            "config/private.pem": (
                "-----BEGIN PRIVATE KEY-----\nprivate-key-content\n-----END PRIVATE KEY-----"
            ),
        },
    )

    assert "SEC002" in _rule_ids(repository)


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        (
            "config/aws.properties",
            "access_key=AKIA1234567890ABCDEF",
        ),
        (
            "config/github.properties",
            "token=ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        ),
        (
            "config/google.properties",
            "apiKey=AIza1234567890abcdefghijklmnopqrstuvwxy",
        ),
    ],
)
def test_detects_recognizable_secret_formats(
    tmp_path: Path,
    relative_path: str,
    content: str,
) -> None:
    """Known secret formats should produce SEC003 findings."""

    repository = _repository(
        tmp_path,
        {
            relative_path: content,
        },
    )

    assert "SEC003" in _rule_ids(repository)


def test_redacts_known_secret_evidence(
    tmp_path: Path,
) -> None:
    """Secret values must not be copied into finding evidence."""

    secret = "AKIA1234567890ABCDEF"

    repository = _repository(
        tmp_path,
        {
            "application.properties": (f"aws.accessKey={secret}"),
        },
    )

    result = SecurityAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    finding = next(finding for finding in result.findings if finding.rule_id == "SEC003")

    evidence_text = " ".join(
        item.description or item.detected_value or "" for item in finding.evidence
    )

    assert secret not in evidence_text
    assert secret not in finding.description
    assert "***" in evidence_text


def test_detects_hardcoded_password(
    tmp_path: Path,
) -> None:
    """Literal credential assignments should be reported."""

    repository = _repository(
        tmp_path,
        {
            "src/config.js": ('const password = "production-password";'),
        },
    )

    assert "SEC004" in _rule_ids(repository)


@pytest.mark.parametrize(
    "credential_value",
    [
        "changeme",
        "placeholder",
        "your_password",
        "${DATABASE_PASSWORD}",
        "{{ database_password }}",
    ],
)
def test_ignores_placeholder_credentials(
    tmp_path: Path,
    credential_value: str,
) -> None:
    """Common placeholder values should not create findings."""

    repository = _repository(
        tmp_path,
        {
            "src/config.js": (f'const password = "{credential_value}";'),
        },
    )

    assert "SEC004" not in _rule_ids(repository)


@pytest.mark.parametrize(
    "content",
    [
        'MessageDigest.getInstance("MD5");',
        'MessageDigest.getInstance("SHA-1");',
        'Cipher.getInstance("DES");',
    ],
)
def test_detects_weak_cryptography(
    tmp_path: Path,
    content: str,
) -> None:
    """Weak cryptographic algorithms should be reported."""

    repository = _repository(
        tmp_path,
        {
            "src/Security.java": content,
        },
    )

    assert "SEC005" in _rule_ids(repository)


@pytest.mark.parametrize(
    "content",
    [
        "eval(user_input);",
        "exec(user_input);",
        "shell_exec($command);",
        "Runtime.getRuntime().exec(command);",
    ],
)
def test_detects_dangerous_dynamic_execution(
    tmp_path: Path,
    content: str,
) -> None:
    """Potentially unsafe command execution should be reported."""

    repository = _repository(
        tmp_path,
        {
            "src/example.php": content,
        },
    )

    assert "SEC006" in _rule_ids(repository)


def test_ignores_dependency_directories(
    tmp_path: Path,
) -> None:
    """Vendored dependencies must not generate repository findings."""

    repository = _repository(
        tmp_path,
        {
            "node_modules/example/config.js": ('const password = "third-party-secret";'),
            "vendor/example/config.php": ('$password = "third-party-secret";'),
        },
    )

    assert _rule_ids(repository) == []


def test_skips_large_files(
    tmp_path: Path,
) -> None:
    """Files larger than the configured limit should not be read."""

    repository = _repository(
        tmp_path,
        {
            "src/large.js": ('const password = "production-password";' + ("x" * 1_000_001)),
        },
    )

    assert "SEC004" not in _rule_ids(repository)
