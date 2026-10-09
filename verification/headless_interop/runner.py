"""Evaluate committed E14.3 headless interop scenarios (maintainer-only)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tests.application.release.support.headless_fixtures import (
    PRODUCTION_KEY_ID,
    generate_ed25519_pem_pair,
    preview_invocation_for_package,
    production_invocation,
    trust_entry,
    write_customer_production_package,
    write_preview_package,
)

from codestrata.application.release.headless import consume_headless_bundle, run_headless_invocation
from codestrata.domain.contracts.enums import ExecutionPurpose


def main() -> int:
    private_pem, public_pem = generate_ed25519_pem_pair()
    key_id = PRODUCTION_KEY_ID
    trust = (
        trust_entry(
            key_id=key_id,
            public_pem=public_pem,
            purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    with tempfile.TemporaryDirectory(prefix="codestrata-e143-") as tmp:
        root = Path(tmp)
        production_pkg = root / "production"
        write_customer_production_package(production_pkg)
        production_out = root / "out-production"
        production = run_headless_invocation(
            production_invocation(),
            package_dir=production_pkg,
            output_dir=production_out,
            signer_private_pem=private_pem,
            signer_key_id=key_id,
        )
        if not production.ok:
            print(f"FAIL production run: {production.reason}")
            return 1
        consume_headless_bundle(production_out, trust_store=trust)
        print("PASS production customer package + consumer")

        preview_pkg = root / "preview"
        write_preview_package(preview_pkg)
        preview_out = root / "out-preview"
        preview_private, preview_public = generate_ed25519_pem_pair()
        preview_key = "headless-result-signer-preview-run"
        preview = run_headless_invocation(
            preview_invocation_for_package(preview_pkg),
            package_dir=preview_pkg,
            output_dir=preview_out,
            signer_private_pem=preview_private,
            signer_key_id=preview_key,
        )
        if not preview.ok:
            print(f"FAIL preview run: {preview.reason}")
            return 1
        preview_trust = (
            trust_entry(
                key_id=preview_key,
                public_pem=preview_public,
                purpose=ExecutionPurpose.PREVIEW,
            ),
        )
        consume_headless_bundle(preview_out, trust_store=preview_trust)
        print("PASS preview purpose run + consumer")

    return 0
