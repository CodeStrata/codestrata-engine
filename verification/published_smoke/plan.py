"""Smoke plan: five E15.1 representatives and release targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verification.published_smoke.models import RepresentativeSmokePin, SmokeTargets
from verification.validation.loader import load_bundle

TARGETS_FILENAME = "targets.yaml"


def default_targets_path() -> Path:
    return Path(__file__).resolve().parent / TARGETS_FILENAME


def load_targets(path: Path | None = None) -> SmokeTargets:
    target_path = path or default_targets_path()
    raw: Any = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{target_path.name} must be a mapping")
    return SmokeTargets(
        schema_version=int(raw["schema_version"]),
        story=str(raw["story"]),
        package_revision=str(raw["package_revision"]),
        pypi_project=str(raw["pypi_project"]),
        candidate_semver=str(raw["candidate_semver"]),
        rollback_semver=str(raw["rollback_semver"]),
        rollback_wheel_sha256=str(raw["rollback_wheel_sha256"]).lower(),
        candidate_wheel_sha256=str(raw.get("candidate_wheel_sha256") or "").lower(),
        observation_business_days=int(raw["observation_business_days"]),
        release_support_owner=str(raw["release_support_owner"]),
        platform_webapp_owners_after_smoke=str(raw["platform_webapp_owners_after_smoke"]),
    )


def build_five_repository_plan() -> tuple[RepresentativeSmokePin, ...]:
    bundle = load_bundle()
    by_id = {pin.id: pin for pin in bundle.external_large}
    pins: list[RepresentativeSmokePin] = []
    for rep in bundle.representatives:
        pin = by_id.get(rep.repository_id)
        if pin is None:
            raise ValueError(
                f"representative {rep.repository_id} missing from external-large corpus"
            )
        pins.append(
            RepresentativeSmokePin(
                role=rep.role.value,
                repository_id=rep.repository_id,
                github_repository=pin.github_repository,
                github_url=pin.github_url,
                pin_sha=pin.sha,
                depth_class=pin.depth_class,
                language=pin.language,
            )
        )
    if len(pins) != 5:
        raise ValueError(f"expected five representatives, got {len(pins)}")
    return tuple(pins)
