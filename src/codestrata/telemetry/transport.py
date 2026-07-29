"""Optional telemetry transport — failures never raise to callers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from codestrata.telemetry.constants import ENDPOINT_ENV


def configured_endpoint() -> str | None:
    value = os.environ.get(ENDPOINT_ENV, "").strip()
    return value or None


def send_payload(
    payload: dict[str, Any],
    *,
    endpoint: str | None = None,
    timeout: float = 2.0,
) -> bool:
    """POST JSON payload. Return True on HTTP success; False otherwise."""

    url = endpoint if endpoint is not None else configured_endpoint()
    if not url:
        return False
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "codestrata-telemetry/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return 200 <= int(getattr(response, "status", 200)) < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False
