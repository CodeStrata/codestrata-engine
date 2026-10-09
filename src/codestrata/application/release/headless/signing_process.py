"""Child-process entrypoint for detached headless result signing (E14.3)."""

from __future__ import annotations

import json
import os
import sys

from codestrata.application.release.headless.detached_signing import (
    SIGNER_ENV,
    sign_manifest_in_process,
)
from codestrata.application.release.headless.models import HeadlessRunManifest
from codestrata.domain.contracts.enums import ExecutionPurpose


def main() -> int:
    pem = os.environ.get(SIGNER_ENV)
    if not pem:
        print("signer credential missing", file=sys.stderr)
        return 2
    try:
        payload = json.loads(sys.stdin.read())
        manifest = HeadlessRunManifest.model_validate(payload["manifest"])
        purpose = ExecutionPurpose(str(payload["purpose"]))
        key_id = str(payload["key_id"])
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"invalid signer input: {error}", file=sys.stderr)
        return 2
    signature = sign_manifest_in_process(
        manifest,
        private_key_pem=pem,
        key_id=key_id,
        purpose=purpose,
    )
    sys.stdout.write(json.dumps(signature.model_dump(mode="json")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
