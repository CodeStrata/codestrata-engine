"""Typed YAML compiler failures (E03.1). Domain code never loads YAML itself."""

from __future__ import annotations

from typing import Any

from codestrata.domain.rules.errors import RuleDomainError


class YamlCompileError(RuleDomainError):
    """Safe-loader, schema, or selector-binding rejection."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        rule_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, reason_code=reason_code, rule_id=rule_id)
        self.details = dict(details or {})

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ERROR",
            "kind": "compile",
            "reason": self.reason_code,
            "message": self.safe_message,
        }
        if self.rule_id is not None:
            payload["rule_id"] = self.rule_id
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class CapabilityError(YamlCompileError):
    """Unsupported fact or operator. Distinct from a parse/schema failure."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        capability_kind: str,
        token: str,
        supported: tuple[str, ...],
        capability_version: str,
        rule_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            reason_code=reason_code,
            rule_id=rule_id,
            details={
                "capability_kind": capability_kind,
                "token": token,
                "supported": list(supported),
                "capability_version": capability_version,
            },
        )
        self.capability_kind = capability_kind
        self.token = token
        self.supported = supported
        self.capability_version = capability_version

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["kind"] = "capability"
        payload["capability_kind"] = self.capability_kind
        payload["token"] = self.token
        payload["capability_version"] = self.capability_version
        payload["supported"] = list(self.supported)
        return payload
