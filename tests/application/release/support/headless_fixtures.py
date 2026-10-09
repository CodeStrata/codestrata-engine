"""Real Ed25519 test keys and prepared packages for E14.3 (not product secrets)."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from codestrata.application.release.verification.models import OfflineTrustEntry, SignerRole
from codestrata.application.rules.effective import seal_bundled_community
from codestrata.domain.contracts.enums import ExecutionPurpose, InvocationKind
from codestrata.domain.contracts.examples_e01_3 import example_invocation, example_pinned
from codestrata.domain.contracts.rules import EffectiveRuleSet
from codestrata.domain.contracts.serialization import dumps_canonical

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
CUSTOMER_EXPECTED = FIXTURE_ROOT / "e04.3" / "expected-customer-production.json"
PRODUCTION_KEY_ID = "headless-result-signer-production"
PREVIEW_KEY_ID = "headless-result-signer-preview"


def generate_ed25519_pem_pair() -> tuple[str, str]:
    key = ed25519.Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def trust_entry(*, key_id: str, public_pem: str, purpose: ExecutionPurpose) -> OfflineTrustEntry:
    return OfflineTrustEntry(
        key_id=key_id,
        public_key_pem=public_pem,
        purpose=purpose,
        role=SignerRole.PRIVATE_RESULT,
        not_after="2027-09-15T00:00:00Z",
    )


def write_customer_production_package(target: Path) -> dict[str, object]:
    target.mkdir(parents=True, exist_ok=True)
    payload = json.loads(CUSTOMER_EXPECTED.read_text(encoding="utf-8"))
    (target / "EffectiveRuleSet.json").write_text(
        dumps_canonical(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def write_preview_package(target: Path) -> dict[str, object]:
    target.mkdir(parents=True, exist_ok=True)
    effective, _catalog = seal_bundled_community(purpose=ExecutionPurpose.PREVIEW)
    payload = effective.model_dump(mode="json")
    (target / "EffectiveRuleSet.json").write_text(
        dumps_canonical(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def production_invocation() -> dict[str, object]:
    customer = json.loads(CUSTOMER_EXPECTED.read_text(encoding="utf-8"))
    effective = EffectiveRuleSet.model_validate(customer)
    invocation = example_invocation(purpose=ExecutionPurpose.PRODUCTION)
    return invocation.model_copy(
        update={"pinned_inputs": example_pinned(effective)},
    ).model_dump(mode="json")


def preview_invocation_for_package(package_dir: Path) -> dict[str, object]:
    effective = EffectiveRuleSet.model_validate(
        json.loads((package_dir / "EffectiveRuleSet.json").read_text(encoding="utf-8")),
    )
    invocation = example_invocation(
        kind=InvocationKind.PREVIEW,
        purpose=ExecutionPurpose.PREVIEW,
    )
    return invocation.model_copy(
        update={"pinned_inputs": example_pinned(effective)},
    ).model_dump(mode="json")
