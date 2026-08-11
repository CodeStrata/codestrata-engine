"""Security hygiene SharedRules (Phase 4.5.3).

Rules consume AggregatedRepositorySensitiveEvidence only. They never re-read
repository files, reparse configuration, or invent vulnerability conclusions.
"""

from __future__ import annotations

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
    repository_sensitive_evidence,
    tls_verification_disabled,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleSeverity, RuleSkipReason
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult
from codestrata.domain.security.ids import (
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.domain.security.taxonomy import SecurityCategory


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
            message=(
                f"Repository-sensitive evidence status is {evidence.status.value}"
            ),
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


class PrivateKeyMaterialRule:
    """Flags inspected artifacts with private-key content signatures."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_PRIVATE_KEY_MATERIAL,
            title="Private key material in repository",
            description=(
                "Detects repository artifacts whose inspected content contains a "
                "supported private-key structural signature. Filename-only "
                "candidates, public certificates, and binary keystores do not match."
            ),
            remediation=(
                "Remove private-key material from the repository and rotate exposed keys."
            ),
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        from codestrata.application.security.context import (
            adjust_rule_confidence,
            adjust_rule_severity,
            classify_security_context,
            contextual_summary_suffix,
        )

        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.artifacts:
            if not has_private_key_material(item):
                continue
            decision = classify_security_context(path=item.path)
            severity = adjust_rule_severity(RuleSeverity.HIGH, decision)
            confidence = adjust_rule_confidence(MatchEvidenceConfidence.HIGH, decision)
            subject = (
                RULE_PRIVATE_KEY_MATERIAL,
                item.evidence_id,
                item.path,
                item.classification.value,
                decision.context.value,
            )
            matches.append(
                match(
                    rule_id=RULE_PRIVATE_KEY_MATERIAL,
                    title="Private key material in repository",
                    summary=(
                        f"Inspected artifact '{item.path}' "
                        f"({item.classification.value}) contains a supported "
                        "private-key content signature. No key body is retained."
                        f"{contextual_summary_suffix(decision)}"
                    ),
                    severity=severity,
                    confidence=confidence,
                    evidence=(
                        evidence_artifact(
                            item=item,
                            message=(
                                "content_classification=private_key_material; "
                                f"inspection_status={item.inspection_status.value}; "
                                f"security_context={decision.context.value}"
                            ),
                            security_category=SecurityCategory.PRIVATE_KEY,
                            security_context=decision.context.value,
                            security_context_reasons=",".join(decision.reasons),
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class CredentialLiteralRule:
    """Flags non-empty literal credential/secret configuration values."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CREDENTIAL_LITERAL,
            title="Credential literal in configuration",
            description=(
                "Detects typed credential/secret configuration facts whose value "
                "is a non-empty literal (not environment reference, empty, or "
                "recognized placeholder)."
            ),
            remediation=(
                "Replace committed credential literals with environment references "
                "or a secrets manager and rotate exposed credentials."
            ),
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        from codestrata.application.security.context import (
            adjust_rule_confidence,
            adjust_rule_severity,
            classify_security_context,
            contextual_summary_suffix,
        )

        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not is_literal_credential(item):
                continue
            decision = classify_security_context(
                path=item.path,
                value=item.redacted_preview,
                normalized_key=item.normalized_key,
                redacted_preview=item.redacted_preview,
            )
            severity = adjust_rule_severity(RuleSeverity.HIGH, decision)
            confidence = adjust_rule_confidence(MatchEvidenceConfidence.HIGH, decision)
            subject = (
                RULE_CREDENTIAL_LITERAL,
                item.evidence_id,
                item.path,
                item.normalized_key,
                item.classification.value,
                decision.context.value,
            )
            summary = (
                f"Configuration key '{item.normalized_key}' in '{item.path}' "
                f"({item.classification.value}) holds a non-empty literal "
                f"credential/secret value (redacted={item.redacted_preview})."
                f"{contextual_summary_suffix(decision)}"
            )
            matches.append(
                match(
                    rule_id=RULE_CREDENTIAL_LITERAL,
                    title="Credential literal in configuration",
                    summary=summary,
                    severity=severity,
                    confidence=confidence,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message=(
                                f"key_family={item.key_family.value}; "
                                f"value_kind={item.value_kind.value}; "
                                f"security_context={decision.context.value}"
                            ),
                            security_category=SecurityCategory.CREDENTIAL,
                            security_context=decision.context.value,
                            security_context_reasons=",".join(decision.reasons),
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class PlaceholderCredentialRule:
    """Flags recognized placeholder credential values (hygiene signal only)."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_PLACEHOLDER_CREDENTIAL,
            title="Placeholder credential in configuration",
            description=(
                "Detects typed credential/secret keys with an explicit recognized "
                "placeholder value. This is a hygiene signal, not proof of an "
                "active secret."
            ),
            remediation=(
                "Replace placeholder credentials with environment references "
                "before deployment."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        from codestrata.application.security.context import (
            adjust_rule_confidence,
            adjust_rule_severity,
            classify_security_context,
            contextual_summary_suffix,
        )

        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not is_placeholder_credential(item):
                continue
            decision = classify_security_context(
                path=item.path,
                value=item.redacted_preview,
                normalized_key=item.normalized_key,
                redacted_preview=item.redacted_preview,
            )
            severity = adjust_rule_severity(RuleSeverity.LOW, decision)
            confidence = adjust_rule_confidence(MatchEvidenceConfidence.HIGH, decision)
            subject = (
                RULE_PLACEHOLDER_CREDENTIAL,
                item.evidence_id,
                item.path,
                item.normalized_key,
                item.classification.value,
                decision.context.value,
            )
            matches.append(
                match(
                    rule_id=RULE_PLACEHOLDER_CREDENTIAL,
                    title="Placeholder credential in configuration",
                    summary=(
                        f"Configuration key '{item.normalized_key}' in '{item.path}' "
                        f"({item.classification.value}) uses a recognized placeholder "
                        "credential value. This is not classified as an active secret."
                        f"{contextual_summary_suffix(decision)}"
                    ),
                    severity=severity,
                    confidence=confidence,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message=(
                                f"placeholder_status={item.placeholder_status.value}; "
                                f"security_context={decision.context.value}"
                            ),
                            security_category=SecurityCategory.CREDENTIAL,
                            security_context=decision.context.value,
                            security_context_reasons=",".join(decision.reasons),
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class TlsVerificationDisabledRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_TLS_VERIFICATION_DISABLED,
            title="TLS verification disabled",
            description=(
                "Detects typed TLS-verification controls whose literal boolean "
                "explicitly disables verification."
            ),
            remediation="Enable TLS certificate verification.",
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not tls_verification_disabled(item):
                continue
            subject = (
                RULE_TLS_VERIFICATION_DISABLED,
                item.evidence_id,
                item.path,
                item.normalized_key,
            )
            matches.append(
                match(
                    rule_id=RULE_TLS_VERIFICATION_DISABLED,
                    title="TLS verification disabled",
                    summary=(
                        f"TLS verification control '{item.normalized_key}' in "
                        f"'{item.path}' is explicitly disabled."
                    ),
                    severity=RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message="tls_verification disabled by typed literal",
                            security_category=SecurityCategory.TRANSPORT_SECURITY,
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class HostnameVerificationDisabledRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_HOSTNAME_VERIFICATION_DISABLED,
            title="Hostname verification disabled",
            description=(
                "Detects typed hostname-verification controls whose literal "
                "boolean explicitly disables verification."
            ),
            remediation="Enable TLS hostname verification.",
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not hostname_verification_disabled(item):
                continue
            subject = (
                RULE_HOSTNAME_VERIFICATION_DISABLED,
                item.evidence_id,
                item.path,
                item.normalized_key,
            )
            matches.append(
                match(
                    rule_id=RULE_HOSTNAME_VERIFICATION_DISABLED,
                    title="Hostname verification disabled",
                    summary=(
                        f"Hostname verification control '{item.normalized_key}' in "
                        f"'{item.path}' is explicitly disabled."
                    ),
                    severity=RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message="hostname_verification disabled by typed literal",
                            security_category=SecurityCategory.TRANSPORT_SECURITY,
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class AuthenticationDisabledRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_AUTHENTICATION_DISABLED,
            title="Authentication disabled",
            description=(
                "Detects typed authentication controls whose literal boolean "
                "explicitly disables authentication. Does not infer framework-wide "
                "security posture."
            ),
            remediation="Enable the configured authentication control.",
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not authentication_disabled(item):
                continue
            subject = (
                RULE_AUTHENTICATION_DISABLED,
                item.evidence_id,
                item.path,
                item.normalized_key,
            )
            matches.append(
                match(
                    rule_id=RULE_AUTHENTICATION_DISABLED,
                    title="Authentication disabled",
                    summary=(
                        f"Authentication control '{item.normalized_key}' in "
                        f"'{item.path}' is explicitly disabled."
                    ),
                    severity=RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message="authentication disabled by typed literal",
                            security_category=SecurityCategory.AUTHENTICATION,
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class PermissiveCorsOriginRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_PERMISSIVE_CORS_ORIGIN,
            title="Permissive CORS origin",
            description=(
                "Detects typed CORS allowed-origin controls whose literal value "
                "is an explicit wildcard (*)."
            ),
            remediation="Replace wildcard CORS origins with an explicit allow-list.",
            severity=RuleSeverity.MEDIUM,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not permissive_cors_origin(item):
                continue
            subject = (
                RULE_PERMISSIVE_CORS_ORIGIN,
                item.evidence_id,
                item.path,
                item.normalized_key,
            )
            matches.append(
                match(
                    rule_id=RULE_PERMISSIVE_CORS_ORIGIN,
                    title="Permissive CORS origin",
                    summary=(
                        f"CORS origin control '{item.normalized_key}' in "
                        f"'{item.path}' is set to an explicit wildcard."
                    ),
                    severity=RuleSeverity.MEDIUM,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message="cors allowed-origin is explicit wildcard",
                            security_category=SecurityCategory.CONFIGURATION,
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)


class DebugEnabledRule:
    """Flags explicitly enabled debug controls for all source roles."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DEBUG_ENABLED,
            title="Debug enabled",
            description=(
                "Detects typed debug controls whose literal boolean explicitly "
                "enables debug. Findings are emitted for all source roles; "
                "assessment inventory may separate production vs test later."
            ),
            remediation="Disable debug mode for production-facing configuration.",
            severity=RuleSeverity.MEDIUM,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _security_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_sensitive_evidence(context)
        assert evidence is not None
        matches: list[RuleMatch] = []
        for item in evidence.configuration_facts:
            if not debug_enabled(item):
                continue
            subject = (
                RULE_DEBUG_ENABLED,
                item.evidence_id,
                item.path,
                item.normalized_key,
                item.classification.value,
            )
            matches.append(
                match(
                    rule_id=RULE_DEBUG_ENABLED,
                    title="Debug enabled",
                    summary=(
                        f"Debug control '{item.normalized_key}' in '{item.path}' "
                        f"({item.classification.value}) is explicitly enabled."
                    ),
                    severity=RuleSeverity.MEDIUM,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_configuration(
                            item=item,
                            message="debug enabled by typed literal",
                            security_category=SecurityCategory.CONFIGURATION,
                        ),
                    ),
                    subject_keys=subject,
                )
            )
        return _sorted_matches(matches)
