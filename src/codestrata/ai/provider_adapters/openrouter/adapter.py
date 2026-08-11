"""``OpenRouterProvider``: unwired ``AIProvider`` implementation for OpenRouter.

``execute()`` never raises for expected failures. Slice 11.9 requires an
injected client; without one the adapter returns ``UNAVAILABLE`` /
``missing_configuration`` (authentication deferred to Slice 11.10).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from codestrata.ai.provider_adapters.openrouter import (
    capabilities,
    error_mapping,
    request_mapping,
    response_mapping,
)
from codestrata.ai.provider_adapters.openrouter import (
    client as client_module,
)
from codestrata.ai.provider_adapters.openrouter.configuration import OpenRouterRuntimeConfiguration
from codestrata.ai.provider_adapters.openrouter.response_mapping import OpenRouterInvocationDetail
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult

DetailSink = Callable[[OpenRouterInvocationDetail], None]
Clock = Callable[[], float]

ADAPTER_LIMITATIONS: tuple[str, ...] = (
    "single_attempt_by_default",
    "runtime_unregistered",
    "configuration_deferred",
    "authentication_deferred",
)


class OpenRouterProvider:
    """OpenRouter OpenAI-compatible Chat Completions adapter."""

    def __init__(
        self,
        configuration: OpenRouterRuntimeConfiguration,
        *,
        client: Any | None = None,
        environment_reader: client_module.EnvironmentReader | None = None,
        detail_sink: DetailSink | None = None,
        clock: Clock = time.perf_counter,
    ) -> None:
        if not isinstance(configuration, OpenRouterRuntimeConfiguration):
            raise ProviderContractValidationError(
                "configuration must be an OpenRouterRuntimeConfiguration"
            )
        if detail_sink is not None and not callable(detail_sink):
            raise ProviderContractValidationError("detail_sink must be callable when provided")
        if not callable(clock):
            raise ProviderContractValidationError("clock must be callable")
        self._configuration = configuration
        self._client = client
        self._environment_reader = environment_reader or client_module.default_environment_reader
        self._detail_sink = detail_sink
        self._clock = clock

    @property
    def provider_id(self) -> ProviderId:
        return capabilities.OPENROUTER_PROVIDER_ID

    @property
    def configuration(self) -> OpenRouterRuntimeConfiguration:
        return self._configuration

    @property
    def client_injected(self) -> bool:
        return self._client is not None

    def supports(self, capability: CapabilityId) -> bool:
        return capabilities.declares_capability(capability)

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
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
            kwargs = request_mapping.build_chat_completion_kwargs(request)
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
            environment_reader=self._environment_reader,
        )
        if resolution.handle is None:
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.UNAVAILABLE,
                failure=error_mapping.MappedFailure(
                    error=resolution.error
                    or error_mapping.build_error(error_mapping.CODE_AUTHENTICATION_DEFERRED)
                ),
                latency_ms=0.0,
            )

        started = self._clock()
        try:
            response = resolution.handle.client.chat.completions.create(**kwargs)
        except Exception as error:  # noqa: BLE001
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.FAILED,
                failure=error_mapping.classify_sdk_exception(error),
                latency_ms=self._elapsed_ms(started),
            )
        latency_ms = self._elapsed_ms(started)

        outcome = response_mapping.extract_chat_response(response)
        if outcome.extracted is None:
            failure = outcome.failure or error_mapping.MappedFailure(
                error=error_mapping.build_error(error_mapping.CODE_UNREADABLE_RESPONSE)
            )
            return self._failure(
                capability=capability,
                status=ProviderExecutionStatus.FAILED,
                failure=failure,
                latency_ms=latency_ms,
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

    def _record(self, detail: OpenRouterInvocationDetail) -> None:
        if self._detail_sink is not None:
            self._detail_sink(detail)

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)


__all__ = [
    "ADAPTER_LIMITATIONS",
    "Clock",
    "DetailSink",
    "OpenRouterProvider",
]
