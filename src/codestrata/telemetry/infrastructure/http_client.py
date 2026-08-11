"""Stdlib HTTP client for privacy-first telemetry (Slice 9.11).

No environment proxy discovery. No redirect following. TLS verification on.
Never logs bodies, tokens, or endpoints.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True, slots=True)
class TelemetryHttpResponse:
    """Bounded HTTP response facts — body capped; never logged by transport."""

    status_code: int
    body: bytes
    redirected: bool = False


class TelemetryHttpClient(Protocol):
    def post_json(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> TelemetryHttpResponse:
        """POST JSON bytes. Must not raise for HTTP error statuses."""


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _ = (req, fp, code, msg, headers, newurl)
        return None


class StdlibTelemetryHttpClient:
    """urllib-based client with empty proxy map and redirect rejection."""

    def __init__(self, *, max_body_bytes: int = 8192) -> None:
        self._max_body_bytes = max_body_bytes
        # Prefer certifi CA bundle — macOS/Python.org builds often lack system
        # trust roots for ssl.create_default_context() alone.
        try:
            import certifi

            context = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001 — fall back to platform defaults
            context = ssl.create_default_context()
        # Empty ProxyHandler disables environment proxy discovery.
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _RejectRedirectHandler(),
            urllib.request.HTTPSHandler(context=context),
        )

    def post_json(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> TelemetryHttpResponse:
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers=dict(headers),
        )
        # urllib uses a single timeout for the whole operation.
        timeout = max(connect_timeout_seconds, 0.001) + max(read_timeout_seconds, 0.001)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read(self._max_body_bytes + 1)
                return TelemetryHttpResponse(
                    status_code=status,
                    body=raw[: self._max_body_bytes],
                )
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            # 3xx with redirect handler returning None surfaces as HTTPError.
            redirected = 300 <= status < 400
            try:
                raw = exc.read(self._max_body_bytes + 1) if exc.fp is not None else b""
            except Exception:
                raw = b""
            return TelemetryHttpResponse(
                status_code=status,
                body=raw[: self._max_body_bytes],
                redirected=redirected,
            )
        except TimeoutError as exc:
            raise TelemetryHttpTimeout from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError) or (
                isinstance(reason, OSError) and "timed out" in str(reason).lower()
            ):
                raise TelemetryHttpTimeout from exc
            raise TelemetryHttpConnectionError from None
        except OSError as exc:
            if "timed out" in str(exc).lower():
                raise TelemetryHttpTimeout from None
            raise TelemetryHttpConnectionError from None


class TelemetryHttpTimeout(Exception):
    """Bounded timeout signal — message never includes endpoint/token."""


class TelemetryHttpConnectionError(Exception):
    """Connection failure signal — message never includes endpoint/token."""


@dataclass(frozen=True, slots=True)
class FakeTelemetryHttpResponse:
    status_code: int
    body: bytes = b"{}"
    redirected: bool = False
    raise_timeout: bool = False
    raise_connection: bool = False


class FakeTelemetryHttpClient:
    """Deterministic injectable client for tests."""

    def __init__(
        self,
        responses: list[FakeTelemetryHttpResponse] | FakeTelemetryHttpResponse | None = None,
    ) -> None:
        if responses is None:
            self._responses = [
                FakeTelemetryHttpResponse(
                    status_code=202,
                    body=json.dumps(
                        {
                            "retry_status": "first_seen",
                            "schema_version": "1.0",
                            "status": "accepted",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                )
            ]
        elif isinstance(responses, FakeTelemetryHttpResponse):
            self._responses = [responses]
        else:
            self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post_json(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> TelemetryHttpResponse:
        # Capture without Authorization value for safer test assertions.
        safe_headers = {
            key: ("Bearer [redacted]" if key.lower() == "authorization" else value)
            for key, value in headers.items()
        }
        self.calls.append(
            {
                "url": url,
                "body": body,
                "headers": safe_headers,
                "connect_timeout_seconds": connect_timeout_seconds,
                "read_timeout_seconds": read_timeout_seconds,
            }
        )
        if not self._responses:
            raise TelemetryHttpConnectionError()
        planned = self._responses.pop(0)
        if planned.raise_timeout:
            raise TelemetryHttpTimeout()
        if planned.raise_connection:
            raise TelemetryHttpConnectionError()
        return TelemetryHttpResponse(
            status_code=planned.status_code,
            body=planned.body,
            redirected=planned.redirected,
        )


__all__ = [
    "FakeTelemetryHttpClient",
    "FakeTelemetryHttpResponse",
    "StdlibTelemetryHttpClient",
    "TelemetryHttpClient",
    "TelemetryHttpConnectionError",
    "TelemetryHttpResponse",
    "TelemetryHttpTimeout",
]
