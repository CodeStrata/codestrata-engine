"""Canonical serialization profile for Engine contract envelopes and schemas."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from codestrata.domain.contracts.formulas import serialize_ratio

PROFILE_ID = "codestrata.canonical-json.v1"
PROFILE_VERSION = "1.0.0"
SUPPORTED_MAJOR_VERSIONS = frozenset({1})

FORBIDDEN_BODY_TOKENS = frozenset(
    {
        "tenant",
        "tenant_id",
        "workspace",
        "workspace_id",
        "portfolio",
        "portfolio_id",
        "job_id",
        "jobid",
        "platform_tenant",
        "org_id",
        "organization_id",
    }
)

FORBIDDEN_CREDENTIAL_AND_APPROVAL_TOKENS = frozenset(
    {
        "platform_token",
        "platform_credentials",
        "platform_api_key",
        "api_key",
        "access_token",
        "refresh_token",
        "oauth_token",
        "bearer_token",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "password",
        "secret_key",
        "hosted_endpoint",
        "s3_uri",
        "approval_id",
        "approver",
        "approver_id",
        "approval_identity",
        "reviewer_identity",
        "github_token",
        "oidc_token",
    }
)

FLOATING_VERSION_TOKENS = frozenset({"latest", "*", "main", "head", "floating", "next"})
DIGEST_PATTERN = re.compile(r"^(?:sha256:)?[a-f0-9]{64}$")
PINNED_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[.-][0-9A-Za-z]+)*$")


class CanonicalProfile:
    """UTF-8 JSON with sorted keys, compact separators, and six-place ratios."""

    profile_id = PROFILE_ID
    version = PROFILE_VERSION
    encoding = "utf-8"
    sort_keys = True
    separators = (",", ":")
    ratio_fractional_places = 6
    array_order = "stable_id_ascending"


def dumps_canonical(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=CanonicalProfile.sort_keys,
        separators=CanonicalProfile.separators,
        ensure_ascii=True,
        allow_nan=False,
    )


def digest_canonical(payload: object) -> str:
    return hashlib.sha256(dumps_canonical(payload).encode("utf-8")).hexdigest()


def serialize_decimal_ratio(value: Decimal) -> str:
    return serialize_ratio(value)


def parse_major_version(version: str) -> int:
    compact = version.strip()
    if not compact:
        raise ValueError("schema_version must not be blank")
    head = compact.split(".", 1)[0]
    if not head.isdigit():
        raise ValueError(f"unsupported schema_version {version!r}")
    return int(head)


def require_supported_major(version: str, *, label: str = "schema_version") -> int:
    major = parse_major_version(version)
    if major not in SUPPORTED_MAJOR_VERSIONS:
        raise ValueError(f"unsupported {label} major {major}")
    return major


def walk_forbidden_identity(payload: object, *, path: str = "$") -> None:
    """Reject tenant/workspace/portfolio/job identity anywhere in analysis body."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            token = str(key).strip().lower().replace("-", "_")
            if token in FORBIDDEN_BODY_TOKENS:
                raise ValueError(f"forbidden identity field {key!r} at {path}")
            walk_forbidden_identity(value, path=f"{path}.{key}")
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            walk_forbidden_identity(item, path=f"{path}[{index}]")
        return
    if isinstance(payload, str):
        lowered = payload.lower()
        if "tenant_id=" in lowered or "workspace_id=" in lowered:
            raise ValueError(f"forbidden identity token at {path}")


def reject_unknown_fields(model_fields: set[str], payload: dict[str, Any]) -> None:
    extra = set(payload) - model_fields
    if extra:
        raise ValueError(f"unknown fields rejected: {sorted(extra)}")


def walk_forbidden_credentials(payload: object, *, path: str = "$") -> None:
    """Reject Platform credentials and approval identities from Engine contracts."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            token = str(key).strip().lower().replace("-", "_")
            if token in FORBIDDEN_CREDENTIAL_AND_APPROVAL_TOKENS:
                raise ValueError(f"forbidden credential or approval field {key!r} at {path}")
            walk_forbidden_credentials(value, path=f"{path}.{key}")
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            walk_forbidden_credentials(item, path=f"{path}[{index}]")


def require_content_digest(value: object, *, label: str = "digest") -> str:
    compact = str(value).strip().lower()
    if compact.startswith("sha256:"):
        compact = compact[7:]
    if not DIGEST_PATTERN.fullmatch(compact):
        raise ValueError(f"{label} must be a pinned sha256 hex digest")
    return compact


def require_pinned_version(value: object, *, label: str = "version") -> str:
    compact = str(value).strip()
    if not compact:
        raise ValueError(f"{label} must not be blank")
    if compact.lower() in FLOATING_VERSION_TOKENS:
        raise ValueError(f"{label} must be pinned; floating token {compact!r} rejected")
    if not PINNED_VERSION_PATTERN.fullmatch(compact):
        raise ValueError(f"{label} must be a pinned dotted version, not {compact!r}")
    return compact


PLACEHOLDER_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def omit_key(payload: dict[str, Any], key: str) -> dict[str, Any]:
    omitted = dict(payload)
    omitted.pop(key, None)
    return omitted


BINDING_DIGEST_CONTEXT = "codestrata.binding_digest"


def is_binding_digest(info: Any) -> bool:
    context = getattr(info, "context", None) or {}
    return bool(context.get(BINDING_DIGEST_CONTEXT))


def bind_content_digest[T: BaseModel](
    model_cls: type[T],
    payload: dict[str, Any],
    key: str = "digest",
) -> T:
    """Construct a frozen model, then bind the canonical content digest."""

    data = dict(payload)
    data[key] = PLACEHOLDER_DIGEST
    normalized = model_cls.model_validate(
        data,
        context={BINDING_DIGEST_CONTEXT: True},
    )
    dumped = normalized.model_dump(mode="json")
    data[key] = digest_canonical(omit_key(dumped, key))
    return model_cls.model_validate(data)
