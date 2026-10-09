"""Detached result signing in an isolated process (E14.3).

The analysis runner must never load private signer material. Signing runs in a
child process that reads ``CODESTRATA_HEADLESS_SIGNER_PEM`` from its own env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.process_launch import child_process_env
from codestrata.application.release.headless.models import (
    DetachedResultSignature,
    HeadlessRunError,
    HeadlessRunManifest,
)
from codestrata.application.release.verification.crypto import encode_b64, sign_ed25519
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.serialization import digest_canonical, dumps_canonical

SIGNER_ENV = "CODESTRATA_HEADLESS_SIGNER_PEM"
SIGNER_KEY_ID_ENV = "CODESTRATA_HEADLESS_SIGNER_KEY_ID"


def assert_analysis_has_no_signer_access(env: dict[str, str] | None = None) -> None:
    """Analysis processes must not carry signer credentials."""

    active = env if env is not None else dict(os.environ)
    if active.get(SIGNER_ENV) or active.get(SIGNER_KEY_ID_ENV):
        raise HeadlessRunError("analysis process must not access signer credentials")


def scrub_analysis_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a copy of ``base`` with signer variables removed."""

    source = dict(base if base is not None else os.environ)
    for key in (SIGNER_ENV, SIGNER_KEY_ID_ENV):
        source.pop(key, None)
    return source


def canonical_manifest_bytes(manifest: HeadlessRunManifest) -> bytes:
    return dumps_canonical(manifest.model_dump(mode="json")).encode("utf-8")


def sign_manifest_in_process(
    manifest: HeadlessRunManifest,
    *,
    private_key_pem: str,
    key_id: str,
    purpose: ExecutionPurpose,
    signed_at: str | None = None,
) -> DetachedResultSignature:
    """Sign manifest bytes. Only call from the isolated signer process or tests."""

    body = canonical_manifest_bytes(manifest)
    manifest_digest = digest_canonical(manifest.model_dump(mode="json"))
    signature = sign_ed25519(private_key_pem, body)
    when = signed_at or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return DetachedResultSignature(
        manifest_digest=manifest_digest,
        key_id=key_id,
        purpose=purpose.value,
        signature_b64=encode_b64(signature),
        signed_at=when,
    )


def sign_manifest_in_isolated_process(
    manifest: HeadlessRunManifest,
    *,
    private_key_pem: str,
    key_id: str,
    purpose: ExecutionPurpose,
    python_executable: str | None = None,
) -> DetachedResultSignature:
    """Spawn a signer child. Parent never imports private key bytes into analysis."""

    assert_analysis_has_no_signer_access()
    exe = python_executable or sys.executable
    payload = {
        "manifest": manifest.model_dump(mode="json"),
        "key_id": key_id,
        "purpose": purpose.value,
    }
    env = child_process_env()
    env[SIGNER_ENV] = private_key_pem
    env[SIGNER_KEY_ID_ENV] = key_id
    proc = subprocess.run(  # noqa: S603
        [
            exe,
            "-m",
            "codestrata.application.release.headless.signing_process",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "signer failed").strip()
        raise HeadlessRunError(f"detached signing failed: {detail}")
    try:
        raw = json.loads(proc.stdout)
        return DetachedResultSignature.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise HeadlessRunError("detached signing returned invalid signature envelope") from error


def write_detached_signature(path: Path, signature: DetachedResultSignature) -> None:
    path.write_text(
        json.dumps(signature.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
