"""YAML-bound security hygiene rules (E06.1).

Canonical default severity, title, message and operator name come from bundled
YAML. Native Python only extracts facts and evaluates allowlisted operators.
Security context is attached as evidence and never rewrites YAML severity.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from codestrata.application.rules.security.helpers import (
    authentication_disabled,
    debug_enabled,
    evidence_artifact,
    evidence_configuration,
    evidence_is_usable,
    has_private_key_material,
    hostname_verification_disabled,
    is_literal_credential,
    is_placeholder_credential,
    make_metadata,
    match,
    permissive_cors_origin,
    production_context_status,
    recommendation_for,
    repository_sensitive_evidence,
    tls_verification_disabled,
)
from codestrata.application.rules.security.yaml_catalog import bundled_rule
from codestrata.domain.evidence.repository_sensitive.models import (
    ConfigurationFactEvidence,
    SensitiveArtifactEvidence,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleSeverity, RuleSkipReason
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult
from codestrata.domain.security.taxonomy import SecurityCategory

_BINDING = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_SEVERITY_BASIS = ("yaml_catalog_default",)
_EXPLOIT_CLAIM = re.compile(
    r"(?i)\b(exploitable|exploitability|rce|remote code execution|mitm attack)\b"
)

_ARTIFACT_OPERATORS = frozenset({"security.has_private_key_material"})
_CONFIG_OPERATORS: dict[str, Callable[[ConfigurationFactEvidence], bool]] = {
    "security.credential_literal": is_literal_credential,
    "security.placeholder_credential": is_placeholder_credential,
    "security.tls_verification_disabled": tls_verification_disabled,
    "security.hostname_verification_disabled": hostname_verification_disabled,
    "security.authentication_disabled": authentication_disabled,
    "security.permissive_cors_origin": permissive_cors_origin,
    "security.debug_enabled": debug_enabled,
}


def _security_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = repository_sensitive_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Repository-sensitive evidence unavailable",
        )
    if not evidence_is_usable(evidence):
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=(f"Repository-sensitive evidence status is {evidence.status.value}"),
        )
    return RuleApplicability.applicable()


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.subject_keys,
                    str(item.rule_id),
                    item.summary,
                ),
            )
        )
    )


def _render(template: str, values: Mapping[str, str]) -> str:
    rendered = _BINDING.sub(lambda match: values.get(match.group(1), ""), template)
    compact = " ".join(rendered.split())
    if _EXPLOIT_CLAIM.search(compact):
        raise ValueError("YAML finding message must not claim runtime exploitability")
    return compact


def _classify_context(
    *,
    path: str,
    value: str | None = None,
    normalized_key: str | None = None,
    redacted_preview: str | None = None,
) -> Any:
    from codestrata.application.security.context import (
        classify_security_context,
        contextual_summary_suffix,
    )

    decision = classify_security_context(
        path=path,
        value=value,
        normalized_key=normalized_key,
        redacted_preview=redacted_preview,
    )
    return decision, contextual_summary_suffix(decision)


def _artifact_extras(item: SensitiveArtifactEvidence) -> dict[str, str]:
    extras = {
        "detector_id": item.metadata.get("detector_id", "content_signature"),
        "safe_secret_type": item.metadata.get("safe_secret_type", "private_key_material"),
        "redacted_span": item.metadata.get("redacted_span", "[REDACTED]"),
        "yaml_runtime": "security.core.bundled_yaml",
        "default_severity": "",
        "effective_severity": "",
        "severity_basis": ",".join(_SEVERITY_BASIS),
    }
    return extras


def _config_extras(
    item: ConfigurationFactEvidence, *, detector_id: str, secret_type: str
) -> dict[str, str]:
    return {
        "detector_id": detector_id,
        "safe_secret_type": secret_type,
        "redacted_span": item.redacted_preview,
        "production_context_status": "",
        "yaml_runtime": "security.core.bundled_yaml",
        "severity_basis": ",".join(_SEVERITY_BASIS),
    }


class YamlBoundHygieneRule:
    """SharedRule adapter bound to one immutable bundled YAML document."""

    def __init__(self, rule_id: str) -> None:
        self._catalog = bundled_rule(rule_id)
        self._rule_id = str(self._catalog["rule_id"])
        self._severity = self._catalog["default_severity"]
        if not isinstance(self._severity, RuleSeverity):
            self._severity = RuleSeverity(str(self._severity))
        self._operator = str(self._catalog["operator"])
        self._title = str(self._catalog["title"])
        self._template = str(self._catalog["message_template"])

    @property
    def metadata(self) -> RuleMetadata:
        languages = self._catalog.get("languages") or (
            "java",
            "python",
            "javascript",
            "typescript",
            "php",
            "csharp",
        )
        return make_metadata(
            rule_id=self._rule_id,
            title=self._title,
            description=str(self._catalog["description"]),
            remediation=recommendation_for(self._rule_id),
            severity=self._severity,
            languages=tuple(str(item) for item in languages),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        if self._operator in _ARTIFACT_OPERATORS:
            return _sorted_matches(self._evaluate_artifacts(evidence.artifacts))
        predicate = _CONFIG_OPERATORS.get(self._operator)
        if predicate is None:
            return SharedRuleEvaluationResult.failed(
                f"operator {self._operator} is not bound",
                rule_id=self._rule_id,
            )
        return _sorted_matches(
            self._evaluate_configuration(evidence.configuration_facts, predicate)
        )

    def _evaluate_artifacts(
        self, artifacts: tuple[SensitiveArtifactEvidence, ...]
    ) -> list[RuleMatch]:
        matches: list[RuleMatch] = []
        for item in artifacts:
            if not has_private_key_material(item):
                continue
            decision, suffix = _classify_context(path=item.path)
            extras = _artifact_extras(item)
            extras["default_severity"] = self._severity.value
            extras["effective_severity"] = self._severity.value
            extras["security_context"] = decision.context.value
            extras["production_context_status"] = production_context_status(
                decision, value_kind=None
            )
            summary = _render(
                self._template,
                {
                    "path": item.path,
                    "classification": item.classification.value,
                },
            )
            matches.append(
                match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=f"{summary}{suffix}",
                    severity=self._severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_artifact(
                            item=item,
                            message=(
                                "content_classification=private_key_material; "
                                f"inspection_status={item.inspection_status.value}; "
                                f"security_context={decision.context.value}; "
                                "severity_source=yaml_catalog_default"
                            ),
                            security_category=SecurityCategory.PRIVATE_KEY,
                            security_context=decision.context.value,
                            security_context_reasons=",".join(decision.reasons),
                            extra_attributes=extras,
                        ),
                    ),
                    subject_keys=(
                        self._rule_id,
                        item.evidence_id,
                        item.path,
                        item.content_fingerprint or "unfingerprinted",
                    ),
                    base_severity=self._severity,
                    calibrated_severity=self._severity,
                    severity_basis=_SEVERITY_BASIS,
                )
            )
        return matches

    def _evaluate_configuration(
        self,
        facts: tuple[ConfigurationFactEvidence, ...],
        predicate: Callable[[ConfigurationFactEvidence], bool],
    ) -> list[RuleMatch]:
        matches: list[RuleMatch] = []
        detector_id = f"config.{self._operator.rsplit('.', 1)[-1]}"
        secret_type = {
            "security.credential_literal": "credential_literal",
            "security.placeholder_credential": "placeholder_credential",
            "security.tls_verification_disabled": "tls_verification_control",
            "security.hostname_verification_disabled": "hostname_verification_control",
            "security.authentication_disabled": "authentication_control",
            "security.permissive_cors_origin": "cors_origin_control",
            "security.debug_enabled": "debug_control",
        }.get(self._operator, "configuration_literal")
        category = {
            "security.credential_literal": SecurityCategory.CREDENTIAL,
            "security.placeholder_credential": SecurityCategory.CREDENTIAL,
            "security.tls_verification_disabled": SecurityCategory.TRANSPORT_SECURITY,
            "security.hostname_verification_disabled": SecurityCategory.TRANSPORT_SECURITY,
            "security.authentication_disabled": SecurityCategory.AUTHENTICATION,
            "security.permissive_cors_origin": SecurityCategory.CONFIGURATION,
            "security.debug_enabled": SecurityCategory.CONFIGURATION,
        }.get(self._operator, SecurityCategory.UNKNOWN)
        for item in facts:
            if not predicate(item):
                continue
            decision, suffix = _classify_context(
                path=item.path,
                value=item.redacted_preview,
                normalized_key=item.normalized_key,
                redacted_preview=item.redacted_preview,
            )
            status = production_context_status(decision, value_kind=item.value_kind)
            extras = _config_extras(item, detector_id=detector_id, secret_type=secret_type)
            extras["production_context_status"] = status
            extras["default_severity"] = self._severity.value
            extras["effective_severity"] = self._severity.value
            summary = _render(
                self._template,
                {
                    "path": item.path,
                    "normalized_key": item.normalized_key,
                    "classification": item.classification.value,
                    "redacted_preview": item.redacted_preview,
                },
            )
            matches.append(
                match(
                    rule_id=self._rule_id,
                    title=self._title,
                    summary=f"{summary}{suffix}",
                    severity=self._severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message=(
                                f"key_family={item.key_family.value}; "
                                f"value_kind={item.value_kind.value}; "
                                f"security_context={decision.context.value}; "
                                f"production_context_status={status}; "
                                "severity_source=yaml_catalog_default"
                            ),
                            security_category=category,
                            security_context=decision.context.value,
                            security_context_reasons=",".join(decision.reasons),
                            extra_attributes=extras,
                        ),
                    ),
                    subject_keys=(
                        self._rule_id,
                        item.evidence_id,
                        item.path,
                        item.normalized_key,
                        str(item.line_start or 0),
                        item.value_fingerprint or "unfingerprinted",
                    ),
                    base_severity=self._severity,
                    calibrated_severity=self._severity,
                    severity_basis=_SEVERITY_BASIS,
                )
            )
        return matches


class PrivateKeyMaterialRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.private-key-material")


class CredentialLiteralRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.credential-literal")


class PlaceholderCredentialRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.placeholder-credential")


class TlsVerificationDisabledRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.tls-verification-disabled")


class HostnameVerificationDisabledRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.hostname-verification-disabled")


class AuthenticationDisabledRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.authentication-disabled")


class PermissiveCorsOriginRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.permissive-cors-origin")


class DebugEnabledRule(YamlBoundHygieneRule):
    def __init__(self) -> None:
        super().__init__("security.debug-enabled")
