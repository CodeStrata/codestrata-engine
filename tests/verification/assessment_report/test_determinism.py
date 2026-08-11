"""Determinism helper tests."""

from __future__ import annotations

from verification.assessment_report.determinism import html_fingerprint, normalize_html


def test_html_fingerprint_stable() -> None:
    a = normalize_html("<div>2026-01-01T00:00:00Z</div>")
    b = normalize_html("<div>2026-02-02T00:00:00Z</div>")
    assert a == b
    assert html_fingerprint("<x>2026-01-01T00:00:00Z</x>") == html_fingerprint(
        "<x>2026-12-12T12:12:12Z</x>"
    )
