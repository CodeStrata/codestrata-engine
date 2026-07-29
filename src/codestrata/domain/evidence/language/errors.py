"""Domain errors for language evidence providers."""

from __future__ import annotations


class LanguageEvidenceError(Exception):
    def __init__(self, message: str, *, reason_code: str = "language_evidence_error") -> None:
        super().__init__(message)
        self.safe_message = message
        self.reason_code = reason_code


class LanguageEvidenceRegistryError(LanguageEvidenceError):
    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "provider_registry_error",
        provider_id: str | None = None,
    ) -> None:
        super().__init__(message, reason_code=reason_code)
        self.provider_id = provider_id
