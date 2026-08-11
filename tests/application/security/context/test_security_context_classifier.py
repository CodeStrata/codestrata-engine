"""Unit tests for security evidence context classification."""

from __future__ import annotations

import pytest

from codestrata.application.security.context import (
    SecurityEvidenceContext,
    adjust_phase1_severity,
    adjust_rule_confidence,
    adjust_rule_severity,
    classify_security_context,
)
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleSeverity
from codestrata.models.enums import Severity


@pytest.mark.parametrize(
    ("path", "value", "key", "expected"),
    [
        (
            ".github/workflows/pr.yml",
            "${{ secrets.GITHUB_TOKEN }}",
            "jobs_main_env_github_token",
            SecurityEvidenceContext.CI_EXPRESSION,
        ),
        (
            "extensions/copilot/test/simulation/fixtures/codeMapper/product-build-linux.yml",
            "$(github-distro-mixin-password)",
            "steps_env_github_token",
            SecurityEvidenceContext.CI_EXPRESSION,
        ),
        (
            "package-lock.json",
            "5.1.2",
            "packages_node_modules_@octokit_auth_token_version",
            SecurityEvidenceContext.DEPENDENCY_METADATA,
        ),
        (
            "extensions/copilot/package.json",
            "API Key",
            "contributes_languagemodelchatproviders_configuration_properties_apikey_title",
            SecurityEvidenceContext.CONFIGURATION_SCHEMA,
        ),
        (
            "src/service/config.py",
            "AKIAIOSFODNN7EXAMPLE",
            "aws_access_key_id",
            SecurityEvidenceContext.MOCK_CREDENTIAL,
        ),
        (
            "extensions/copilot/src/extension/chronicle/common/test/secretFilter.spec.ts",
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234",
            "token",
            SecurityEvidenceContext.MOCK_CREDENTIAL,
        ),
        (
            "src/app/settings.py",
            "live-looking-secret-value-abc123XYZ",
            "api_secret",
            SecurityEvidenceContext.PRODUCTION,
        ),
        (
            "tests/unit/test_auth.py",
            "not-a-github-expression",
            "client_secret",
            SecurityEvidenceContext.TEST,
        ),
        (
            "docs/configuration.md",
            "example-token",
            "token",
            SecurityEvidenceContext.DOCUMENTATION,
        ),
        (
            "examples/sample-app/.env",
            "demo",
            "password",
            SecurityEvidenceContext.SAMPLE,
        ),
    ],
)
def test_classify_security_context(
    path: str,
    value: str,
    key: str,
    expected: SecurityEvidenceContext,
) -> None:
    decision = classify_security_context(
        path=path,
        value=value,
        normalized_key=key,
        redacted_preview=value,
    )
    assert decision.context is expected


def test_ci_expression_demotes_to_informational() -> None:
    decision = classify_security_context(
        path=".github/workflows/ci.yml",
        value="${{ secrets.GITHUB_TOKEN }}",
        normalized_key="env_github_token",
    )
    assert adjust_rule_severity(RuleSeverity.HIGH, decision) is RuleSeverity.INFORMATIONAL
    assert adjust_rule_confidence(MatchEvidenceConfidence.HIGH, decision) is MatchEvidenceConfidence.MEDIUM
    assert adjust_phase1_severity(Severity.CRITICAL, decision) is Severity.INFO


def test_production_preserves_high_severity() -> None:
    decision = classify_security_context(
        path="src/config/secrets.yaml",
        value="sk-live-abc123def456ghi789",
        normalized_key="openai_api_key",
    )
    assert decision.context is SecurityEvidenceContext.PRODUCTION
    assert adjust_rule_severity(RuleSeverity.HIGH, decision) is RuleSeverity.HIGH
    assert adjust_rule_confidence(MatchEvidenceConfidence.HIGH, decision) is MatchEvidenceConfidence.HIGH


def test_gha_id_token_permission_with_redacted_preview() -> None:
    decision = classify_security_context(
        path=".github/workflows/css-order-scan.yml",
        value="[REDACTED]",
        normalized_key="permissions_id_token",
        redacted_preview="[REDACTED]",
    )
    assert decision.context is SecurityEvidenceContext.CI_EXPRESSION
    assert adjust_rule_severity(RuleSeverity.HIGH, decision) is RuleSeverity.INFORMATIONAL
