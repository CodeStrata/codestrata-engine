"""Fetch live PyPI metadata (never pyproject or git tags)."""

from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from verification.live_release_baseline.models import InferenceError, PyPIProject
from verification.live_release_baseline.record import parse_pypi_project


def _verified_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_pypi_payload(name: str, *, timeout_seconds: float) -> dict[str, object]:
    url = f"https://pypi.org/pypi/{name}/json"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds, context=_verified_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise InferenceError(f"PyPI HTTP {exc.code} for {name}") from exc
    except URLError as exc:
        raise InferenceError(f"PyPI fetch failed for {name}: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise InferenceError("PyPI payload is not a JSON object")
    return payload


def fetch_pypi_project(name: str, *, timeout_seconds: float = 30.0) -> PyPIProject:
    return parse_pypi_project(_fetch_pypi_payload(name, timeout_seconds=timeout_seconds))


def wheel_sha256_for_version(
    name: str,
    version: str,
    *,
    timeout_seconds: float = 30.0,
) -> str:
    payload = _fetch_pypi_payload(name, timeout_seconds=timeout_seconds)
    releases = payload.get("releases")
    if not isinstance(releases, dict):
        raise InferenceError("PyPI payload missing releases")
    files_raw = releases.get(version)
    if not isinstance(files_raw, list) or not files_raw:
        raise InferenceError(f"PyPI has no files for {name}=={version}")
    for entry in files_raw:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("packagetype") or "") != "bdist_wheel":
            continue
        if bool(entry.get("yanked")):
            continue
        digests = entry.get("digests")
        if isinstance(digests, dict):
            sha256 = str(digests.get("sha256") or "")
            if sha256:
                return sha256
    raise InferenceError(f"No wheel digest for {name}=={version}")
