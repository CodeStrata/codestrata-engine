"""Verification adapter: real Platform ingestion safety authority for SV.11.

Engine product packages must not import Platform. This harness-only adapter
loads ``codestrata_platform`` from the monorepo when present and invokes the
production ``validate_report_document`` gate used by EI ingestion.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _monorepo_root() -> Path:
    # engine/verification/assessment_consistency/this_file → repo root
    return Path(__file__).resolve().parents[3]


def ensure_platform_importable() -> None:
    """Put ``platform/src`` on ``sys.path`` when running in the monorepo."""

    platform_src = _monorepo_root() / "platform" / "src"
    if not platform_src.is_dir():
        raise RuntimeError(
            "Platform package not found; EI readiness requires monorepo layout "
            f"with {platform_src}"
        )
    text = str(platform_src)
    if text not in sys.path:
        sys.path.insert(0, text)


def validate_with_platform_ingestion_safety(
    document: dict[str, Any],
) -> tuple[bool, str | None]:
    """Return ``(ok, reason_code)`` using production Platform validation.

    Diagnostics never include rejected field values.
    """

    ensure_platform_importable()
    from codestrata_platform.intelligence_reporting.application.errors import (
        MalformedAssessmentReportError,
        UnsafeAssessmentMetadataError,
    )
    from codestrata_platform.intelligence_reporting.application.validation import (
        validate_report_document,
    )

    try:
        validate_report_document(document)
    except UnsafeAssessmentMetadataError:
        return False, "unsafe_metadata"
    except MalformedAssessmentReportError:
        return False, "malformed_report"
    except Exception:  # noqa: BLE001 - fail closed without echoing payloads
        return False, "platform_validation_error"
    return True, None
