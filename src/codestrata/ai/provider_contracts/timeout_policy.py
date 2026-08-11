"""``TimeoutPolicy``: a declarative, unwired timeout representation.

This is a pure value object: it declares *what a timeout would be* (a bound,
a scope, optionally where the value came from) without ever enforcing it.
See ``executor.py``'s module docstring for why ``AIProviderExecutor`` does
not itself implement wall-clock timeout enforcement (no threads, no
signals, no ``asyncio``) — real enforcement is deferred to a future
provider-adapter-level client timeout (e.g. an ``httpx``/``boto3`` client
constructed with this value), which is out of scope for this slice.

``source_category`` reuses ``configuration_sources.SourceCategory`` (Slice
11.3) rather than duplicating a parallel "where did this come from" enum —
consistent with this package's "reuse, do not duplicate" convention (see
``errors.ErrorCategory`` for the same pattern applied to failure categories).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_policy import (
    ALLOWED_TIMEOUT_SCOPES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
)


class TimeoutScope(StrEnum):
    """Where a declared timeout bound would apply."""

    PROVIDER_REQUEST = "provider_request"
    TOTAL_EXECUTION = "total_execution"


assert tuple(s.value for s in TimeoutScope) == ALLOWED_TIMEOUT_SCOPES, (
    "TimeoutScope enum values must exactly match execution_policy.ALLOWED_TIMEOUT_SCOPES"
)


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """A bounded, unwired timeout declaration. Never enforced by this package itself."""

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    scope: TimeoutScope = TimeoutScope.PROVIDER_REQUEST
    source_category: SourceCategory | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            raise ProviderContractValidationError("timeout_seconds must be a number")
        value = float(self.timeout_seconds)
        if not math.isfinite(value):
            raise ProviderContractValidationError("timeout_seconds must be finite")
        if not (0 < value <= MAX_TIMEOUT_SECONDS):
            raise ProviderContractValidationError(
                f"timeout_seconds must be within (0, {MAX_TIMEOUT_SECONDS}]"
            )
        if not isinstance(self.scope, TimeoutScope):
            raise ProviderContractValidationError(
                f"scope must be a TimeoutScope, got {type(self.scope).__name__}"
            )
        if self.source_category is not None and not isinstance(
            self.source_category, SourceCategory
        ):
            raise ProviderContractValidationError(
                "source_category must be a SourceCategory or None, got "
                f"{type(self.source_category).__name__}"
            )
        if not isinstance(self.enabled, bool):
            raise ProviderContractValidationError("enabled must be a bool")


DEFAULT_TIMEOUT_POLICY = TimeoutPolicy()


__all__ = [
    "DEFAULT_TIMEOUT_POLICY",
    "TimeoutPolicy",
    "TimeoutScope",
]
