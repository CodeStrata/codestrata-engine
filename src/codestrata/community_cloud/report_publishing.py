"""Engine client for Community report publishing (Slice 17.16 / 18.7 journey fix)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from codestrata.community_cloud.public_api_authority import resolve_public_community_api_base
from codestrata.community_cloud.public_client_credential import (
    packaged_public_community_client_credential,
)
from codestrata.telemetry.event_identity import TelemetryTransportCredential

PUBLIC_REPORTS_BASE_URL = "https://reports.codestrata.ai"
CREDENTIAL_ENV = "CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL"
PRIVATE_REPO_WARNING = (
    "This report appears to come from a private/local repository. "
    "Anyone with the resulting link can view it."
)
PUBLIC_PUBLISH_WARNING = (
    "This will publish your current Assessment Report. "
    "Anyone with the resulting link can view it."
)


class ReportPublishError(RuntimeError):
    """Raised for explicit publish failures — never includes credentials."""


@dataclass(frozen=True, slots=True)
class ReportPublishResult:
    public_id: str
    public_url: str
    report_type: str
    status: str = "published"
    local_html_path: str = ""

    def to_stable_dict(self) -> dict[str, str]:
        return {
            "public_id": self.public_id,
            "public_url": self.public_url,
            "report_type": self.report_type,
            "status": self.status,
            "local_html_path": self.local_html_path,
        }


def telemetry_eligible_for_publish(session: object | None = None) -> bool:
    """Compatibility shim.

    Report publication is authorized by explicit publish confirmation, not
    telemetry session consent. Always returns True for callers that still check.
    """

    _ = session
    return True


def resolve_community_credential() -> TelemetryTransportCredential:
    """Resolve Community client credential for publish/telemetry transport.

    Order:
    1. ``CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL`` env override (operator/CI)
    2. Packaged public Community client credential (normal Community users)
    """

    raw = (os.environ.get(CREDENTIAL_ENV) or "").strip()
    if not raw:
        raw = packaged_public_community_client_credential().strip()
    if not raw:
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    try:
        return TelemetryTransportCredential(raw)
    except Exception as exc:  # noqa: BLE001
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        ) from exc


def user_facing_publish_error(exc: BaseException) -> str:
    """Map internal failures to Community-user messaging (no env/AWS guidance)."""

    text = str(exc).strip()
    lowered = text.lower()
    if isinstance(exc, ReportPublishError):
        if text.startswith("Publish completed but"):
            return text
        if "not found" in lowered or "no local" in lowered:
            return "No current report found. Run `codestrata assess --repo .` first."
        if "unavailable" in lowered or "api" in lowered:
            return (
                "Publishing failed. Local report remains unchanged. "
                "Community publishing may be temporarily unavailable."
            )
        if "credential" in lowered or CREDENTIAL_ENV.lower() in lowered:
            return (
                "Community publishing is temporarily unavailable. "
                "Local report remains unchanged."
            )
        if "confirm" in lowered:
            return text
        if "private" in lowered or "local-" in lowered:
            return text
        # Never leak credential env var names or AWS guidance.
        if CREDENTIAL_ENV in text or "aws" in lowered or "secret" in lowered:
            return (
                "Community publishing is temporarily unavailable. "
                "Local report remains unchanged."
            )
        return text or "Publishing failed. Local report remains unchanged."
    return "Publishing failed. Local report remains unchanged."


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi CA bundle when available (common on macOS Python builds)."""

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _api_url(path: str) -> str:
    base = resolve_public_community_api_base().rstrip("/")
    return f"{base}{path}"


def _request_json(
    *,
    method: str,
    url: str,
    credential: TelemetryTransportCredential,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": credential.authorization_header_value(),
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=_ssl_context()),
    )
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(1_000_000)
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        raw = exc.read(1_000_000)
        status = int(exc.code)
    except Exception as exc:  # noqa: BLE001
        raise ReportPublishError(
            "Publishing failed. Local report remains unchanged."
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError as exc:
        raise ReportPublishError(
            "Publishing failed. Local report remains unchanged."
        ) from exc
    if not isinstance(payload, dict):
        raise ReportPublishError("Publishing failed. Local report remains unchanged.")
    return status, payload


_PUBLIC_ID_HEADER = "X-CodeStrata-Public-Id"
_VERIFY_BODY_SCAN_BYTES = 65_536


def verify_public_report_get(
    public_url: str,
    *,
    expected_public_id: str,
    timeout_seconds: float = 30.0,
) -> int:
    """Independently GET a branded public report URL (no Authorization).

    Prevents the false-positive where publish POST returns a URL that is not
    actually routable / readable as a report (JSON API error envelopes).

    Identity proof prefers ``X-CodeStrata-Public-Id`` (works for oversized HTML
    served via Worker-followed presign without chrome meta). Falls back to a
    bounded scan of the first ~64 KiB for ``codestrata-public-id`` meta.

    Returns the HTTP status on success (always 200 when no exception).
    """

    url = (public_url or "").strip()
    expected = (expected_public_id or "").strip()
    if not expected:
        raise ReportPublishError(
            "Publish completed but the opaque report id was missing. "
            "Local report remains unchanged."
        )
    expected_url = f"{PUBLIC_REPORTS_BASE_URL}/r/{expected}"
    if url != expected_url:
        raise ReportPublishError(
            "Publish completed but the public report URL is not the branded "
            "reports.codestrata.ai/r/<id> link for the returned opaque id."
        )
    if "Authorization=" in url or "cscc_v1_" in url:
        raise ReportPublishError(
            "Publish completed but the public report URL must not embed credentials."
        )

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "User-Agent": "CodeStrata-public-report-verify/1.0",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=_ssl_context()),
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            content_type = str(response.headers.get("Content-Type") or "")
            header_id = str(response.headers.get(_PUBLIC_ID_HEADER) or "").strip()
            body = response.read(_VERIFY_BODY_SCAN_BYTES)
    except urllib.error.HTTPError as exc:
        raise ReportPublishError(
            "Publish completed but the public report URL did not return a readable "
            f"report (HTTP {int(exc.code)}). Local report remains unchanged."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ReportPublishError(
            "Publish completed but the public report URL could not be verified. "
            "Local report remains unchanged."
        ) from exc

    if status != 200:
        raise ReportPublishError(
            "Publish completed but the public report URL did not return HTTP 200. "
            "Local report remains unchanged."
        )
    if "text/html" not in content_type.lower():
        raise ReportPublishError(
            "Publish completed but the public report URL did not return HTML "
            f"(content-type={content_type!r}). Local report remains unchanged."
        )
    text = body.decode("utf-8", errors="replace")
    if '"code":"not_found"' in text or "Endpoint not found" in text or "Report not found" in text:
        raise ReportPublishError(
            "Publish completed but the public report URL returned an API error "
            "envelope instead of a report. Local report remains unchanged."
        )
    if header_id == expected:
        return status
    # Chrome wrapper uses meta name="codestrata-public-id" near document start.
    if f'codestrata-public-id" content="{expected}"' in text:
        return status
    if f'content="{expected}"' in text and "codestrata-public-id" in text:
        return status
    raise ReportPublishError(
        "Publish completed but the retrieved report identity did not match "
        "the published opaque id. Local report remains unchanged."
    )


def confirm_public_report_verification(
    *,
    public_id: str,
    credential: TelemetryTransportCredential,
    http_status: int = 200,
    verification_status: str = "verified",
) -> None:
    """Record independent GET verification into the private validation registry.

    Soft-fails: publish already succeeded; registry write must not undo local
    success or block the operator. Temporary Community validation tooling only.
    """

    pid = (public_id or "").strip()
    if not pid:
        return
    try:
        status, _payload = _request_json(
            method="POST",
            url=_api_url(f"/api/v1/reports/{pid}/verification"),
            credential=credential,
            body={
                "schema_version": "1.0",
                "verification_status": verification_status,
                "http_status": int(http_status),
            },
        )
        _ = status
    except Exception:  # noqa: BLE001 — never fail publish on registry confirm
        return


def _put_bytes(url: str, body: bytes, *, content_type: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("codestrata.ai") and host.startswith("reports."):
        raise ReportPublishError("Publishing failed. Local report remains unchanged.")

    class _PutRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            if code not in {301, 302, 303, 307, 308}:
                return None
            method = req.get_method()
            data = req.data
            headers_out = {
                k: v
                for k, v in req.headers.items()
                if k.lower() not in {"content-length", "content-type"}
                or method in {"GET", "HEAD"}
            }
            if method not in {"GET", "HEAD"} and req.headers.get("Content-type"):
                headers_out["Content-type"] = req.headers.get("Content-type")
            return urllib.request.Request(
                newurl,
                data=data,
                headers=headers_out,
                method=method,
                unverifiable=True,
            )

    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _PutRedirectHandler(),
        urllib.request.HTTPSHandler(context=_ssl_context()),
    )
    try:
        with opener.open(request, timeout=120) as response:
            _ = response.read(1024)
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        raise ReportPublishError(
            "Publishing failed. Local report remains unchanged."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ReportPublishError(
            "Publishing failed. Local report remains unchanged."
        ) from exc
    if status >= 300:
        raise ReportPublishError("Publishing failed. Local report remains unchanged.")


def publish_local_assessment(
    *,
    current_dir: Path,
    logical_repository_id: str,
    session: object | None = None,
    private_repository_acknowledged: bool,
    confirm_public_publish: bool,
    credential: TelemetryTransportCredential | None = None,
) -> ReportPublishResult:
    """Upload local CURRENT assessment HTML+JSON and return branded public URL."""

    _ = session  # publish is independent of telemetry consent
    if not confirm_public_publish:
        raise ReportPublishError("Explicit publish confirmation is required.")
    if logical_repository_id.startswith("local-") and not private_repository_acknowledged:
        raise ReportPublishError(PRIVATE_REPO_WARNING)

    html_path = current_dir / "assessment.html"
    json_path = current_dir / "assessment.json"
    if not html_path.is_file() or not json_path.is_file():
        raise ReportPublishError("No current report found. Run `codestrata assess --repo .` first.")

    active_cred = credential or resolve_community_credential()
    status, intent = _request_json(
        method="POST",
        url=_api_url("/api/v1/reports/upload-intents"),
        credential=active_cred,
        body={
            "schema_version": "1.0",
            "report_type": "assessment",
            "logical_identity_type": "repository",
            "logical_identity_key": logical_repository_id,
            "artifacts": ["assessment.html", "assessment.json"],
            "private_repository_acknowledged": private_repository_acknowledged,
            "confirm_public_publish": True,
        },
    )
    if status >= 300:
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    upload_id = str(intent.get("upload_id") or "")
    puts = intent.get("puts") or []
    if not upload_id or not isinstance(puts, list):
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )

    local_files = {
        "assessment.html": html_path.read_bytes(),
        "assessment.json": json_path.read_bytes(),
    }
    for item in puts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("artifact") or "")
        url = str(item.get("upload_url") or "")
        ctype = str(item.get("content_type") or "application/octet-stream")
        if name not in local_files or not url:
            raise ReportPublishError(
                "Community publishing is temporarily unavailable. Local report remains unchanged."
            )
        _put_bytes(url, local_files[name], content_type=ctype)

    status, published = _request_json(
        method="POST",
        url=_api_url("/api/v1/reports"),
        credential=active_cred,
        body={
            "schema_version": "1.0",
            "upload_id": upload_id,
            "confirm_public_publish": True,
            "private_repository_acknowledged": private_repository_acknowledged,
        },
    )
    if status >= 300:
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    public_url = str(published.get("public_url") or "")
    public_id = str(published.get("public_id") or "")
    if not public_url.startswith(PUBLIC_REPORTS_BASE_URL + "/r/"):
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    if "s3.amazonaws.com" in public_url or "amazonaws.com" in public_url:
        # Never return/accept raw S3 public share links.
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    verify_status = verify_public_report_get(public_url, expected_public_id=public_id)
    confirm_public_report_verification(
        public_id=public_id,
        credential=active_cred,
        http_status=verify_status,
        verification_status="verified",
    )
    return ReportPublishResult(
        public_id=public_id,
        public_url=public_url,
        report_type="assessment",
        local_html_path=str(html_path),
    )


def publish_local_eir(
    *,
    current_dir: Path,
    portfolio_id: str,
    session: object | None = None,
    confirm_public_publish: bool,
    credential: TelemetryTransportCredential | None = None,
) -> ReportPublishResult:
    _ = session
    if not confirm_public_publish:
        raise ReportPublishError("Explicit publish confirmation is required.")

    html_path = current_dir / "engineering-intelligence-report.html"
    json_path = current_dir / "engineering-intelligence-report.json"
    if not html_path.is_file() or not json_path.is_file():
        raise ReportPublishError("No current EIR found. Generate an Engineering Intelligence report first.")

    active_cred = credential or resolve_community_credential()
    status, intent = _request_json(
        method="POST",
        url=_api_url("/api/v1/reports/upload-intents"),
        credential=active_cred,
        body={
            "schema_version": "1.0",
            "report_type": "engineering_intelligence",
            "logical_identity_type": "portfolio",
            "logical_identity_key": portfolio_id,
            "artifacts": [
                "engineering-intelligence-report.html",
                "engineering-intelligence-report.json",
            ],
            "private_repository_acknowledged": True,
            "confirm_public_publish": True,
        },
    )
    if status >= 300:
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    upload_id = str(intent.get("upload_id") or "")
    puts = intent.get("puts") or []
    local_files = {
        "engineering-intelligence-report.html": html_path.read_bytes(),
        "engineering-intelligence-report.json": json_path.read_bytes(),
    }
    for item in puts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("artifact") or "")
        url = str(item.get("upload_url") or "")
        ctype = str(item.get("content_type") or "application/octet-stream")
        _put_bytes(url, local_files[name], content_type=ctype)

    status, published = _request_json(
        method="POST",
        url=_api_url("/api/v1/reports"),
        credential=active_cred,
        body={
            "schema_version": "1.0",
            "upload_id": upload_id,
            "confirm_public_publish": True,
            "private_repository_acknowledged": True,
        },
    )
    if status >= 300:
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    public_url = str(published.get("public_url") or "")
    public_id = str(published.get("public_id") or "")
    if not public_url.startswith(PUBLIC_REPORTS_BASE_URL + "/r/"):
        raise ReportPublishError(
            "Community publishing is temporarily unavailable. Local report remains unchanged."
        )
    verify_status = verify_public_report_get(public_url, expected_public_id=public_id)
    confirm_public_report_verification(
        public_id=public_id,
        credential=active_cred,
        http_status=verify_status,
        verification_status="verified",
    )
    return ReportPublishResult(
        public_id=public_id,
        public_url=public_url,
        report_type="engineering_intelligence",
        local_html_path=str(html_path),
    )


__all__ = [
    "CREDENTIAL_ENV",
    "PRIVATE_REPO_WARNING",
    "PUBLIC_PUBLISH_WARNING",
    "PUBLIC_REPORTS_BASE_URL",
    "ReportPublishError",
    "ReportPublishResult",
    "confirm_public_report_verification",
    "publish_local_assessment",
    "publish_local_eir",
    "resolve_community_credential",
    "telemetry_eligible_for_publish",
    "user_facing_publish_error",
    "verify_public_report_get",
]
