"""Reject Platform authority models from Engine override inputs."""

from __future__ import annotations

from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.domain.contracts.serialization import (
    walk_forbidden_credentials,
    walk_forbidden_identity,
)

OPAQUE_POLICY_PREFIX = "policy:opaque:"
OPAQUE_EXCEPTION_PREFIX = "exception:opaque:"

_REF_FORBIDDEN = (
    "approver",
    "approval",
    "mailto:",
    "organization",
    "workspace",
    "tenant",
    "org_id",
    "accountable_owner",
)

_AUTHORITY_KEYS = frozenset(
    {
        "approver",
        "approver_id",
        "approval",
        "approval_id",
        "approval_identity",
        "organization",
        "organization_id",
        "org_id",
        "workspace",
        "workspace_id",
        "tenant",
        "tenant_id",
        "accountable_owner",
        "owner_email",
    }
)


def assert_engine_local_payload(payload: object, *, path: str = "$") -> None:
    try:
        walk_forbidden_identity(payload, path=path)
        walk_forbidden_credentials(payload, path=path)
    except ValueError as error:
        raise OverrideError("forbidden_authority", str(error)) from error
    _scan_authority(payload, path=path)


def require_opaque_policy_ref(value: object) -> str:
    return _require_opaque(value, prefix=OPAQUE_POLICY_PREFIX, label="policy_ref")


def require_opaque_exception_ref(value: object) -> str:
    return _require_opaque(value, prefix=OPAQUE_EXCEPTION_PREFIX, label="exception_ref")


def _require_opaque(value: object, *, prefix: str, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise OverrideError("forbidden_authority", f"{label} must not be blank")
    lowered = text.lower()
    for marker in _REF_FORBIDDEN:
        if marker in lowered:
            raise OverrideError(
                "forbidden_authority",
                f"{label} cannot carry {marker} authority identity",
            )
    if not text.startswith(prefix):
        raise OverrideError(
            "forbidden_authority",
            f"{label} must be an opaque Engine reference starting with {prefix}",
        )
    remainder = text[len(prefix) :]
    if not remainder or "/" in remainder or remainder.startswith("@"):
        raise OverrideError("forbidden_authority", f"{label} remainder is empty or path-like")
    return text


def _scan_authority(payload: object, *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            token = str(key).strip().lower().replace("-", "_")
            if token in _AUTHORITY_KEYS:
                raise OverrideError(
                    "forbidden_authority",
                    f"authority field {key!r} cannot reach Engine at {path}",
                )
            _scan_authority(value, path=f"{path}.{key}")
        return
    if isinstance(payload, list | tuple):
        for index, item in enumerate(payload):
            _scan_authority(item, path=f"{path}[{index}]")
        return
    if isinstance(payload, str):
        lowered = payload.lower()
        for marker in ("approver:", "approval:", "mailto:"):
            if marker in lowered:
                raise OverrideError(
                    "forbidden_authority",
                    f"authority token {marker!r} cannot reach Engine at {path}",
                )
