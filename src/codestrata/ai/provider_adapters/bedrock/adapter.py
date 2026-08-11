"""``BedrockProvider``: the wired ``AIProvider`` implementation for AWS Bedrock.

``execute()`` never raises for an expected failure (CR-3). Every one of the
following surfaces as a ``FAILED``/``UNAVAILABLE`` :class:`AIProviderResult`
carrying a bounded ``AIProviderError`` instead:

* the optional ``bedrock`` extra (``boto3``) is not installed
  (``dependency_unavailable``);
* AWS authentication/profile resolution fails while building the client, or
  the client constructor itself fails (``missing_configuration``);
* the SDK raises during the Converse call (``authentication_failed``,
  ``authorization_failed``, ``invalid_model``, ``invalid_request``,
  ``timeout``, ``rate_limited``, ``provider_unavailable``, or
  ``internal_failure``);
* the response is not a mapping, is missing ``output``/``output.message``/
  ``output.message.content``, carries no assistant text, or cannot be read
  (``invalid_response``);
* the request cannot be mapped to a call (``invalid_request``).

A request for an undeclared capability returns ``SKIPPED`` without
constructing a client. ``UNAVAILABLE`` is reserved for "the provider could
not be used at all" (no call was attempted); ``FAILED`` means a call was
attempted and did not produce usable content.

``KeyboardInterrupt``/``SystemExit`` do not subclass ``Exception`` and always
propagate unmodified.

The adapter holds no mutable state and constructs no client until the first
``execute()`` — the AWS credential chain, the instance metadata service, and
STS are never reached before then. Per-invocation values the legacy result
contract needs (request ID, stop reason, latency, reported token totals,
sanitized exception text) are handed to the optional ``detail_sink``
callback rather than stored on the instance, so two adapters never share
state and nothing credential- or response-derived outlives one call.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from codestrata.ai.provider_adapters.bedrock import (
    capabilities,
    error_mapping,
    request_mapping,
    response_mapping,
    usage_mapping,
)
from codestrata.ai.provider_adapters.bedrock import (
    client as client_module,
)
from codestrata.ai.provider_adapters.bedrock.configuration import BedrockRuntimeConfiguration
from codestrata.ai.provider_adapters.bedrock.response_mapping import BedrockInvocationDetail
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult

DetailSink = Callable[[BedrockInvocationDetail], None]
Clock = Callable[[], float]

# Limitations every result from this adapter carries. The adapter is wired,
# but the surrounding operational envelope is deliberately conservative: the
# executor still makes exactly one attempt by default and the botocore client
# is pinned to ``max_attempts=1`` (CR-1), and the wall-clock bound is still
# owned by the SDK's own connect/read timeouts rather than by the executor.
ADAPTER_LIMITATIONS: tuple[str, ...] = (
    "single_attempt_by_default",
    "prompt_instruction_only_structured_json",
    "wall_clock_timeout_sdk_owned",
)


class BedrockProvider:
    """AWS Bedrock Converse adapter implementing the ``AIProvider`` protocol."""

    def __init__(
        self,
        configuration: BedrockRuntimeConfiguration,
        *,
        client: Any | None = None,
        detail_sink: DetailSink | None = None,
        clock: Clock = time.perf_counter,
    ) -> None:
        if not isinstance(configuration, BedrockRuntimeConfiguration):
            raise ProviderContractValidationError(
                "configuration must be a BedrockRuntimeConfiguration"
            )
        if detail_sink is not None and not callable(detail_sink):
            raise ProviderContractValidationError("detail_sink must be callable when provided")
        if not callable(clock):
            raise ProviderContractValidationError("clock must be callable")
        self._configuration = configuration
        self._client = client
        self._detail_sink = detail_sink
        self._clock = clock

    @property
    def provider_id(self) -> ProviderId:
        return capabilities.BEDROCK_PROVIDER_ID

    @property
    def configuration(self) -> BedrockRuntimeConfiguration:
        return self._configuration

    @property
    def client_injected(self) -> bool:
        """Whether a client was injected (tests/callers) rather than constructed here."""

        return self._client is not None

    def supports(self, capability: CapabilityId) -> bool:
        """Declare capability support. Never constructs a client or reaches AWS."""

        return capabilities.declares_capability(capability)

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        """Execute one Converse call. Never raises for an expected failure."""

        if not isinstance(request, AIProviderRequest):
            raise ProviderContractValidationError("request must be an AIProviderRequest")

        capability = request.capability
        if not self.supports(capability):
            return AIProviderResult(
                provider_id=self.provider_id,
                capability=capability,
                status=ProviderExecutionStatus.SKIPPED,
                limitations=ADAPTER_LIMITATIONS,
            )

        try:
            kwargs = request_mapping.build_converse_kwargs(request)
        except ProviderContractValidationError:
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.FAILED,
                failure=error_mapping.MappedFailure(
                    error=error_mapping.build_error(error_mapping.CODE_PROMPT_MAPPING_FAILED)
                ),
                latency_ms=0.0,
            )

        resolution = client_module.resolve_client(
            self._configuration.client_inputs,
            injected_client=self._client,
        )
        if resolution.handle is None:
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.UNAVAILABLE,
                failure=error_mapping.MappedFailure(
                    error=resolution.error
                    or error_mapping.build_error(error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED),
                    legacy_detail=resolution.legacy_detail,
                ),
                latency_ms=0.0,
            )

        started = self._clock()
        try:
            response = resolution.handle.client.converse(**kwargs)
        except Exception as error:  # noqa: BLE001 - provider invocation boundary
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.FAILED,
                failure=error_mapping.classify_sdk_exception(error),
                latency_ms=self._elapsed_ms(started),
            )
        measured_latency_ms = self._elapsed_ms(started)

        outcome = response_mapping.extract_converse_response(response)
        if outcome.extracted is None:
            failure = outcome.failure or error_mapping.MappedFailure(
                error=error_mapping.build_error(error_mapping.CODE_UNREADABLE_RESPONSE)
            )
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.FAILED,
                failure=failure,
                latency_ms=measured_latency_ms,
            )

        latency_ms = usage_mapping.resolve_latency_ms(
            reported_latency_ms=outcome.extracted.reported_latency_ms,
            measured_latency_ms=measured_latency_ms,
        )
        result, detail = response_mapping.build_success_result(
            provider_id=self.provider_id,
            capability=capability,
            response_expectation=request.response_expectation,
            extracted=outcome.extracted,
            latency_ms=latency_ms,
            limitations=ADAPTER_LIMITATIONS,
        )
        self._record(detail)
        return result

    def _failure(
        self,
        *,
        capability: CapabilityId,
        status: ProviderExecutionStatus,
        failure: error_mapping.MappedFailure,
        latency_ms: float,
    ) -> AIProviderResult:
        result, detail = response_mapping.build_failure_result(
            provider_id=self.provider_id,
            capability=capability,
            status=status,
            failure=failure,
            latency_ms=latency_ms,
            limitations=ADAPTER_LIMITATIONS,
        )
        self._record(detail)
        return result

    def _record(self, detail: BedrockInvocationDetail) -> None:
        if self._detail_sink is not None:
            self._detail_sink(detail)

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)


__all__ = [
    "ADAPTER_LIMITATIONS",
    "BedrockProvider",
    "Clock",
    "DetailSink",
]
