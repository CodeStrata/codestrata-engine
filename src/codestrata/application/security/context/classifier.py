"""Classify security evidence context from path and content heuristics.

Does not suppress detections. Callers adjust severity/confidence using
:mod:`codestrata.application.security.context.policy`.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.security.context import (
    SecurityContextDecision,
    SecurityEvidenceContext,
)
from codestrata.scan_boundary import ScanSourceRole, classify_path_role

_CI_EXPRESSION_RE = re.compile(
    r"\$\{\{\s*(secrets\.|steps\.[^}]+\.outputs\.)|"
    r"\$\(\s*[\w.-]*(password|token|secret|key)[\w.-]*\s*\)",
    re.IGNORECASE,
)
_GHA_SECRETS_RE = re.compile(r"\$\{\{\s*secrets\.", re.IGNORECASE)
_PIPELINE_MACRO_RE = re.compile(
    r"\$\([\w.-]*(password|token|secret|key)[\w.-]*\)",
    re.IGNORECASE,
)

_MOCK_VALUE_RE = re.compile(
    r"("
    r"AKIA[0-9A-Z]{16}EXAMPLE|"
    r"AKIAIOSFODNN7EXAMPLE|"
    r"client_secret_value|"
    r"AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe|"
    r"your[_-]?api[_-]?key|"
    r"changeme|"
    r"placeholder|"
    r"xxxxx|"
    r"dummy|"
    r"fake[_-]?(secret|token|key|password)|"
    r"not[_-]?a[_-]?(real[_-]?)?(secret|token|key)"
    r")",
    re.IGNORECASE,
)

_PEM_BEGIN_RE = re.compile(r"-----BEGIN ([A-Z0-9 ]+)?PRIVATE KEY-----")

_LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "poetry.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "packages.lock.json",
        "go.sum",
    }
)

_BUILD_DIR_MARKERS = frozenset(
    {
        "dist",
        "build",
        "out",
        "target",
        ".next",
        "coverage",
        "__pycache__",
        "node_modules",
    }
)

_SCHEMA_KEY_MARKERS = frozenset(
    {
        "type",
        "title",
        "description",
        "minlength",
        "maxlength",
        "deprecationmessage",
        "markdowndescription",
        "default",
        "enum",
        "examples",
        "pattern",
        "format",
        "properties",
    }
)


def classify_security_context(
    *,
    path: str,
    value: str | None = None,
    normalized_key: str | None = None,
    redacted_preview: str | None = None,
) -> SecurityContextDecision:
    """Classify security evidence context for a path and optional value/key."""

    normalized_path = path.replace("\\", "/")
    while normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    normalized_path = normalized_path.lstrip("/")
    reasons: list[str] = []
    path_role = classify_path_role(normalized_path)
    source_class = classify_source_path(normalized_path)

    # Content/value heuristics (override path when clearly non-literal secrets).
    value_text = " ".join(
        part for part in (value or "", redacted_preview or "") if part
    ).strip()
    if value_text:
        if _GHA_SECRETS_RE.search(value_text) or _PIPELINE_MACRO_RE.search(value_text):
            reasons.append("ci-secret-expression")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.CI_EXPRESSION,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        if _CI_EXPRESSION_RE.search(value_text):
            reasons.append("ci-expression")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.CI_EXPRESSION,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        if _MOCK_VALUE_RE.search(value_text):
            reasons.append("known-mock-or-example-credential")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.MOCK_CREDENTIAL,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        # Synthetic GitHub PAT style strings in tests/fixtures only.
        if (
            path_role in {ScanSourceRole.TEST, ScanSourceRole.FIXTURE}
            or ".spec." in normalized_path
            or ".test." in normalized_path
        ) and re.search(r"\bghp_[A-Za-z0-9]{20,}\b", value_text):
            reasons.append("github-pat-in-test")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.MOCK_CREDENTIAL,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        # Truncated PEM fixtures used by secret-filter tests.
        if _PEM_BEGIN_RE.search(value_text) and (
            path_role in {ScanSourceRole.TEST, ScanSourceRole.FIXTURE}
            or ".spec." in normalized_path
            or ".test." in normalized_path
        ):
            reasons.append("private-key-in-test")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.TEST_FIXTURE
                if path_role is ScanSourceRole.FIXTURE
                else SecurityEvidenceContext.MOCK_CREDENTIAL,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )

    # Path-based dependency / schema / build classification.
    name = PurePosixPath(normalized_path).name
    parts = set(normalized_path.lower().split("/"))

    if name in _LOCKFILE_NAMES or "node_modules" in parts:
        reasons.append("dependency-lockfile-or-vendor")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.DEPENDENCY_METADATA,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )

    if parts & _BUILD_DIR_MARKERS and path_role is ScanSourceRole.GENERATED:
        reasons.append("build-or-generated-path")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.BUILD_ARTIFACT,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )

    key = (normalized_key or "").strip().lower().replace("-", "_")
    if key:
        leaf = key.split(".")[-1].split("_")[-1]
        # package.json contributes.*.properties.apiKey.title|description|type
        if "properties_apikey" in key.replace(".", "_") or key.endswith(
            (
                "apikey_title",
                "apikey_description",
                "apikey_type",
                "apikey_minlength",
                "apikey_deprecationmessage",
                "apikey_markdowndescription",
            )
        ):
            reasons.append("contribution-schema-apikey-metadata")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.CONFIGURATION_SCHEMA,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        if leaf in _SCHEMA_KEY_MARKERS and "apikey" in key.replace(".", "").replace("_", ""):
            reasons.append("schema-field-under-apikey")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.CONFIGURATION_SCHEMA,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )
        if name == "package.json" and (
            key.startswith("contributes_")
            or "configuration_properties" in key
            or key.startswith("scripts_")
        ):
            # Scripts named get_token / schema contribution points.
            if "token" in key or "secret" in key or "apikey" in key or "password" in key:
                if value_text and not _looks_like_secret_literal(value_text):
                    reasons.append("package-json-non-secret-metadata")
                    return SecurityContextDecision(
                        context=SecurityEvidenceContext.CONFIGURATION_SCHEMA,
                        reasons=tuple(reasons),
                        path_role=path_role.value,
                    )

    # GHA permissions.id-token — permission verbs, not secret material.
    # Match even when preview is fully redacted (value may be "write"/"read").
    if (
        normalized_path.startswith(".github/")
        and key
        and (key.endswith("id_token") or key.endswith("permissions_id_token"))
    ):
        preview = (value_text or "").strip().lower()
        # value and redacted_preview are often both "[REDACTED]" → joined twice
        preview_tokens = {t for t in preview.replace(",", " ").split() if t}
        allowed = {"", "[redacted]", "[empty]", "write", "read", "none"}
        if preview in allowed or (preview_tokens and preview_tokens <= allowed - {""}):
            reasons.append("gha-permissions-id-token")
            return SecurityContextDecision(
                context=SecurityEvidenceContext.CI_EXPRESSION,
                reasons=tuple(reasons),
                path_role=path_role.value,
            )

    # Path roles from shared boundary classifier.
    if path_role is ScanSourceRole.FIXTURE or source_class is SourceClassification.FIXTURE:
        reasons.append("path-fixture")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.TEST_FIXTURE,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.TEST or source_class is SourceClassification.TEST:
        reasons.append("path-test")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.TEST,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.DOCUMENTATION or (
        source_class is SourceClassification.DOCUMENTATION
    ):
        reasons.append("path-documentation")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.DOCUMENTATION,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.EXAMPLE or source_class is SourceClassification.EXAMPLE:
        reasons.append("path-sample")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.SAMPLE,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.GENERATED or source_class is SourceClassification.GENERATED:
        reasons.append("path-generated")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.GENERATED,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.VENDOR:
        reasons.append("path-vendor")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.DEPENDENCY_METADATA,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )
    if path_role is ScanSourceRole.PRODUCTION or source_class is SourceClassification.SOURCE:
        reasons.append("path-production")
        return SecurityContextDecision(
            context=SecurityEvidenceContext.PRODUCTION,
            reasons=tuple(reasons),
            path_role=path_role.value,
        )

    reasons.append("unclassified")
    return SecurityContextDecision(
        context=SecurityEvidenceContext.UNKNOWN,
        reasons=tuple(reasons),
        path_role=path_role.value,
    )


def _looks_like_secret_literal(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith(("${{", "$(")):
        return False
    if text.lower() in {"string", "boolean", "number", "object", "array"}:
        return False
    if len(text) <= 2:
        return False
    # npm script paths, prose descriptions
    if " " in text and not text.startswith(("AKIA", "ghp_", "sk-", "xox")):
        return False
    if text.endswith((".mts", ".ts", ".js", ".py", ".sh")):
        return False
    return True


__all__ = ["classify_security_context"]
