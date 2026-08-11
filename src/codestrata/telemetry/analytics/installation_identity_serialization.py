"""Deterministic serialization for anonymous installation identity (Slice 10.2)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    CommunityAnonymousInstallationIdentityPolicy,
)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def identity_to_stable_json(record: AnonymousInstallationIdentity) -> str:
    return _stable_json(record.to_stable_dict())


def identity_policy_to_stable_json(
    policy: CommunityAnonymousInstallationIdentityPolicy,
) -> str:
    return _stable_json(policy.to_stable_dict())


__all__ = [
    "identity_policy_to_stable_json",
    "identity_to_stable_json",
]
