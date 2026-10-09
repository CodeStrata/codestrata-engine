"""Publish the launch outcome-driver manifest from E01.1 ratification."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from codestrata.domain.contracts.catalog import (
    PACKAGE_REVISION,
    dump_yaml_bytes,
    load_launch_ratification,
    sha256_bytes,
)
from codestrata.domain.contracts.models import OutcomeDriver
from codestrata.domain.contracts.serialization import digest_canonical

MANIFEST_ID = "e01.2-outcome-driver-manifest"
MANIFEST_VERSION = "1.0.0"


class OutcomeDriverManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = MANIFEST_ID
    manifest_version: str = MANIFEST_VERSION
    package_revision: str = PACKAGE_REVISION
    source_ratification: str = "e01.1-launch-ratification"
    no_opaque_score: bool = True
    drivers: tuple[OutcomeDriver, ...]


def build_outcome_driver_manifest() -> OutcomeDriverManifest:
    ratification = load_launch_ratification()
    return OutcomeDriverManifest(
        package_revision=ratification.package_revision,
        drivers=ratification.outcome_drivers,
        no_opaque_score=ratification.no_opaque_score.canonical_health_score is False,
    )


def dump_outcome_driver_yaml() -> bytes:
    payload = build_outcome_driver_manifest().model_dump(mode="json")
    return yaml.safe_dump(payload, sort_keys=True, allow_unicode=False).encode("utf-8")


def outcome_driver_manifest_digest() -> str:
    return digest_canonical(build_outcome_driver_manifest().model_dump(mode="json"))


def ratification_yaml_digest() -> str:
    return sha256_bytes(dump_yaml_bytes())
