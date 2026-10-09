"""Neutral local headless invocation, detached result signing, and consumer fixtures (E14.3)."""

from codestrata.application.release.headless.consumer import consume_headless_bundle
from codestrata.application.release.headless.detached_signing import (
    assert_analysis_has_no_signer_access,
    sign_manifest_in_isolated_process,
)
from codestrata.application.release.headless.models import (
    DetachedResultSignature,
    HeadlessRunError,
    HeadlessRunManifest,
    HeadlessRunOutcome,
)
from codestrata.application.release.headless.runner import run_headless_invocation

__all__ = [
    "DetachedResultSignature",
    "HeadlessRunError",
    "HeadlessRunManifest",
    "HeadlessRunOutcome",
    "assert_analysis_has_no_signer_access",
    "consume_headless_bundle",
    "run_headless_invocation",
    "sign_manifest_in_isolated_process",
]
