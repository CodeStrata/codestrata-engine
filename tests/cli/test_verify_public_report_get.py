"""Regression coverage for public report GET identity verification (Slice 19.5)."""

from __future__ import annotations

from email.message import Message
from io import BytesIO

import pytest

from codestrata.community_cloud.report_publishing import (
    ReportPublishError,
    verify_public_report_get,
)


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        body: bytes = b"<html><body>ok</body></html>",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self._body = BytesIO(body)

    def read(self, n: int = -1) -> bytes:
        return self._body.read(n)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _patch_opener(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    class _Opener:
        def open(self, request, timeout=None):  # noqa: ANN001
            _ = request, timeout
            return response

    monkeypatch.setattr(
        "codestrata.community_cloud.report_publishing.urllib.request.build_opener",
        lambda *args, **kwargs: _Opener(),
    )


def test_verify_prefers_public_id_header(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = "A" * 32
    _patch_opener(
        monkeypatch,
        _FakeResponse(
            body=b"<html><body>oversized without meta</body></html>",
            headers={"X-CodeStrata-Public-Id": pid},
        ),
    )
    assert (
        verify_public_report_get(
            f"https://reports.codestrata.ai/r/{pid}",
            expected_public_id=pid,
        )
        == 200
    )


def test_verify_falls_back_to_early_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = "B" * 32
    html = (
        f'<html><head><meta name="codestrata-public-id" content="{pid}"></head>'
        "<body>report</body></html>"
    ).encode("utf-8")
    _patch_opener(monkeypatch, _FakeResponse(body=html))
    assert (
        verify_public_report_get(
            f"https://reports.codestrata.ai/r/{pid}",
            expected_public_id=pid,
        )
        == 200
    )


def test_verify_rejects_wrong_header_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = "C" * 32
    _patch_opener(
        monkeypatch,
        _FakeResponse(headers={"X-CodeStrata-Public-Id": "D" * 32}),
    )
    with pytest.raises(ReportPublishError, match="identity did not match"):
        verify_public_report_get(
            f"https://reports.codestrata.ai/r/{pid}",
            expected_public_id=pid,
        )


def test_verify_rejects_missing_report(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    class _Opener:
        def open(self, request, timeout=None):  # noqa: ANN001
            raise urllib.error.HTTPError(
                url=request.full_url,
                code=404,
                msg="not found",
                hdrs=Message(),
                fp=BytesIO(b'{"error":{"code":"not_found"}}'),
            )

    monkeypatch.setattr(
        "codestrata.community_cloud.report_publishing.urllib.request.build_opener",
        lambda *args, **kwargs: _Opener(),
    )
    with pytest.raises(ReportPublishError, match="HTTP 404"):
        verify_public_report_get(
            f"https://reports.codestrata.ai/r/{'E' * 32}",
            expected_public_id="E" * 32,
        )


def test_verify_rejects_malformed_json_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = "F" * 32
    _patch_opener(
        monkeypatch,
        _FakeResponse(
            body=b'{"error":{"code":"not_found","message":"Report not found"}}',
            headers={"X-CodeStrata-Public-Id": pid},
        ),
    )
    with pytest.raises(ReportPublishError, match="API error"):
        verify_public_report_get(
            f"https://reports.codestrata.ai/r/{pid}",
            expected_public_id=pid,
        )
