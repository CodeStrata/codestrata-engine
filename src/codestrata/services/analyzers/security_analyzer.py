"""Detect common security risks in repository source and configuration files."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)
from codestrata.models.normalized_facts import SecurityFacts


class SecurityAnalyzer:
    """Detect high-confidence security risks using deterministic rules."""

    _MAX_FILE_SIZE_BYTES = 1_000_000

    _IGNORED_DIRECTORIES = {
        ".git",
        ".codestrata",
        ".idea",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "target",
        "coverage",
    }

    _TEXT_FILE_SUFFIXES = {
        ".crt",
        ".env",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".key",
        ".kt",
        ".pem",
        ".php",
        ".cs",
        ".properties",
        ".py",
        ".rb",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".xml",
        ".yaml",
        ".yml",
    }

    _SECRET_FILE_NAMES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }

    _PRIVATE_KEY_MARKERS = (
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
    )

    _SECRET_PATTERNS: tuple[
        tuple[str, re.Pattern[str]],
        ...,
    ] = (
        (
            "AWS access key",
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        ),
        (
            "GitHub token",
            re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,255}\b"),
        ),
        (
            "Slack token",
            re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        ),
        (
            "Stripe secret key",
            re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
        ),
        (
            "Google API key",
            re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        ),
    )

    _HARDCODED_CREDENTIAL_PATTERN = re.compile(
        r"""
        \b
        (
            password
            | passwd
            | pwd
            | secret
            | client_secret
            | api_key
            | apikey
            | access_token
            | auth_token
        )
        \b
        \s*
        (?:=|:)\s*
        ["']
        ([^"'{}\s]{6,})
        ["']
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _SAFE_PLACEHOLDER_VALUES = {
        "changeme",
        "example",
        "placeholder",
        "password",
        "secret",
        "test",
        "your_api_key",
        "your_password",
        "your_secret",
    }

    _WEAK_CRYPTO_PATTERNS: tuple[
        tuple[str, re.Pattern[str]],
        ...,
    ] = (
        (
            "MD5",
            re.compile(r"(?i)\b(?:md5|MessageDigest\.getInstance\([\"']MD5[\"']\))"),
        ),
        (
            "SHA-1",
            re.compile(r"(?i)\b(?:sha1|sha-1|MessageDigest\.getInstance\([\"']SHA-?1[\"']\))"),
        ),
        (
            "DES",
            re.compile(r"(?i)\bCipher\.getInstance\([\"']DES(?:/[^\"']*)?[\"']\)"),
        ),
    )

    _DANGEROUS_EXECUTION_PATTERNS: tuple[
        tuple[str, re.Pattern[str]],
        ...,
    ] = (
        (
            "Python eval",
            re.compile(r"\beval\s*\("),
        ),
        (
            "Python exec",
            re.compile(r"\bexec\s*\("),
        ),
        (
            "PHP eval",
            re.compile(r"(?i)\beval\s*\("),
        ),
        (
            "JavaScript dynamic evaluation",
            re.compile(r"\b(?:eval|Function)\s*\("),
        ),
        (
            "Shell execution",
            re.compile(r"(?i)\b(?:shell_exec|system|passthru|Runtime\.getRuntime\(\)\.exec)\s*\("),
        ),
    )

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Analyze repository files for common security risks."""

        del technologies
        del facts

        findings: list[Finding] = []

        for relative_path in repository.files:
            normalized_path = relative_path.replace("\\", "/")

            if self._should_ignore(normalized_path):
                continue

            file_path = repository.path / relative_path

            findings.extend(
                self._analyze_file(
                    file_path=file_path,
                    relative_path=normalized_path,
                )
            )

        sensitive_file_count = sum(finding.rule_id == "SEC001" for finding in findings)
        secret_finding_count = sum(
            finding.rule_id in {"SEC002", "SEC003", "SEC004"} for finding in findings
        )
        weak_crypto_count = sum(finding.rule_id == "SEC005" for finding in findings)
        dangerous_execution_count = sum(finding.rule_id == "SEC006" for finding in findings)

        return AnalyzerResult(
            findings=findings,
            facts=RepositoryFacts(
                security=SecurityFacts(
                    sensitive_file_count=sensitive_file_count,
                    secret_finding_count=secret_finding_count,
                    weak_crypto_count=weak_crypto_count,
                    dangerous_execution_count=dangerous_execution_count,
                )
            ),
        )

    def _analyze_file(
        self,
        file_path: Path,
        relative_path: str,
    ) -> list[Finding]:
        """Analyze one repository file."""

        findings: list[Finding] = []

        findings.extend(
            self._detect_sensitive_file(
                file_path=file_path,
                relative_path=relative_path,
            )
        )

        if not self._is_scannable_text_file(file_path):
            return findings

        content = self._read_file(file_path)

        if content is None:
            return findings

        findings.extend(
            self._detect_private_keys(
                content=content,
                relative_path=relative_path,
            )
        )
        findings.extend(
            self._detect_known_secrets(
                content=content,
                relative_path=relative_path,
            )
        )
        findings.extend(
            self._detect_hardcoded_credentials(
                content=content,
                relative_path=relative_path,
            )
        )
        findings.extend(
            self._detect_weak_crypto(
                content=content,
                relative_path=relative_path,
            )
        )
        findings.extend(
            self._detect_dangerous_execution(
                content=content,
                relative_path=relative_path,
            )
        )

        return findings

    def _detect_sensitive_file(
        self,
        file_path: Path,
        relative_path: str,
    ) -> list[Finding]:
        """Detect sensitive files committed to the repository."""

        if file_path.name not in self._SECRET_FILE_NAMES:
            return []

        if file_path.name == ".env.example":
            return []

        return [
            self._finding(
                rule_id="SEC001",
                title="Sensitive configuration file committed",
                severity=Severity.HIGH,
                relative_path=relative_path,
                evidence=(f"Repository contains sensitive file: {relative_path}"),
                metadata={
                    "file_name": file_path.name,
                },
            )
        ]

    def _detect_private_keys(
        self,
        content: str,
        relative_path: str,
    ) -> list[Finding]:
        """Detect embedded private key material."""

        for marker in self._PRIVATE_KEY_MARKERS:
            if marker in content:
                return [
                    self._finding(
                        rule_id="SEC002",
                        title="Private key material detected",
                        severity=Severity.CRITICAL,
                        relative_path=relative_path,
                        evidence=marker,
                        metadata={
                            "secret_type": "private-key",
                        },
                    )
                ]

        return []

    def _detect_known_secrets(
        self,
        content: str,
        relative_path: str,
    ) -> list[Finding]:
        """Detect secrets with recognizable token formats."""

        findings: list[Finding] = []

        for secret_name, pattern in self._SECRET_PATTERNS:
            match = pattern.search(content)

            if match is None:
                continue

            findings.append(
                self._finding(
                    rule_id="SEC003",
                    title=f"{secret_name} detected",
                    severity=Severity.CRITICAL,
                    relative_path=relative_path,
                    evidence=self._redact(match.group(0)),
                    metadata={
                        "secret_type": secret_name,
                    },
                )
            )

        return findings

    def _detect_hardcoded_credentials(
        self,
        content: str,
        relative_path: str,
    ) -> list[Finding]:
        """Detect likely hardcoded credentials."""

        findings: list[Finding] = []

        for match in self._HARDCODED_CREDENTIAL_PATTERN.finditer(content):
            credential_name = match.group(1)
            credential_value = match.group(2)

            if self._is_placeholder(credential_value):
                continue

            findings.append(
                self._finding(
                    rule_id="SEC004",
                    title="Possible hardcoded credential",
                    severity=Severity.HIGH,
                    relative_path=relative_path,
                    evidence=(f"{credential_name}={self._redact(credential_value)}"),
                    metadata={
                        "credential_name": credential_name.lower(),
                    },
                )
            )

        return findings

    def _detect_weak_crypto(
        self,
        content: str,
        relative_path: str,
    ) -> list[Finding]:
        """Detect use of weak cryptographic algorithms."""

        findings: list[Finding] = []

        for algorithm, pattern in self._WEAK_CRYPTO_PATTERNS:
            if pattern.search(content) is None:
                continue

            findings.append(
                self._finding(
                    rule_id="SEC005",
                    title=f"Weak cryptographic algorithm: {algorithm}",
                    severity=Severity.MEDIUM,
                    relative_path=relative_path,
                    evidence=algorithm,
                    metadata={
                        "algorithm": algorithm,
                    },
                )
            )

        return findings

    def _detect_dangerous_execution(
        self,
        content: str,
        relative_path: str,
    ) -> list[Finding]:
        """Detect potentially unsafe dynamic command execution."""

        findings: list[Finding] = []

        for execution_type, pattern in self._DANGEROUS_EXECUTION_PATTERNS:
            if pattern.search(content) is None:
                continue

            findings.append(
                self._finding(
                    rule_id="SEC006",
                    title="Potentially unsafe dynamic execution",
                    severity=Severity.MEDIUM,
                    relative_path=relative_path,
                    evidence=execution_type,
                    metadata={
                        "execution_type": execution_type,
                    },
                )
            )

        return findings

    def _finding(
        self,
        rule_id: str,
        title: str,
        severity: Severity,
        relative_path: str,
        evidence: str,
        metadata: dict[str, object],
    ) -> Finding:
        """Create a security finding."""

        description = f"{title} in {relative_path}: {evidence}"

        return Finding(
            rule_id=rule_id,
            title=title,
            description=description,
            category=FindingCategory.SECURITY,
            severity=severity,
            source=FindingSource.STATIC_ANALYSIS,
            evidence=[
                Evidence(
                    file_path=relative_path,
                    description=evidence,
                    detected_value=evidence,
                )
            ],
            affected_technologies=[],
            metadata={
                "path": relative_path,
                **metadata,
            },
        )

    def _should_ignore(
        self,
        relative_path: str,
    ) -> bool:
        """Return whether a repository path should be ignored."""

        path_parts = set(relative_path.split("/"))

        return bool(path_parts & self._IGNORED_DIRECTORIES)

    def _is_scannable_text_file(
        self,
        file_path: Path,
    ) -> bool:
        """Return whether the file should be read as text."""

        if file_path.name.startswith(".env"):
            return True

        return file_path.suffix.lower() in self._TEXT_FILE_SUFFIXES

    def _read_file(
        self,
        file_path: Path,
    ) -> str | None:
        """Read a reasonably sized UTF-8 text file."""

        try:
            if file_path.stat().st_size > self._MAX_FILE_SIZE_BYTES:
                return None

            return file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            return None

    def _is_placeholder(
        self,
        value: str,
    ) -> bool:
        """Return whether a credential value is clearly a placeholder."""

        normalized_value = value.strip().lower()

        if normalized_value in self._SAFE_PLACEHOLDER_VALUES:
            return True

        return any(
            marker in normalized_value
            for marker in (
                "${",
                "{{",
                "process.env",
                "system.getenv",
                "getenv(",
                "vault:",
                "secret://",
            )
        )

    def _redact(
        self,
        value: str,
    ) -> str:
        """Redact sensitive values before storing evidence."""

        if len(value) <= 6:
            return "***"

        return f"{value[:3]}***{value[-3:]}"
