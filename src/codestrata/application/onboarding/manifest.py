"""Persist and load repository onboarding manifests (Phase 5.11)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.domain.onboarding.identifiers import ONBOARDING_MANIFEST_FILENAME
from codestrata.domain.onboarding.models import RepositoryOnboardingManifest
from codestrata.services.artifact_serialization import dumps_stable_json


def write_onboarding_manifest(
    manifest: RepositoryOnboardingManifest,
    destination: Path,
) -> Path:
    """Write repository-onboarding.json atomically."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    path = (
        destination
        if destination.name.endswith(".json")
        else destination / ONBOARDING_MANIFEST_FILENAME
    )
    text = dumps_stable_json(manifest.model_dump(mode="json"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path


def load_onboarding_manifest(path: Path) -> RepositoryOnboardingManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RepositoryOnboardingManifest.model_validate(payload)
