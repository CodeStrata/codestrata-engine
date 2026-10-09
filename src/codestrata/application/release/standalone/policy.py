"""Load packaged E14.2 release policy resources."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml

from codestrata.application.release.standalone.digest import sha256_bytes
from codestrata.domain.contracts.models import BudgetLimits

RESOURCE_PACKAGE = "codestrata.resources.release"

RUNTIME_LIMITS_NAME = "headless-runtime-limits-v1.yaml"
RUNTIME_LOCK_NAME = "runtime-lock-v1.txt"
PACKAGING_INVENTORY_NAME = "packaging-inventory-v1.yaml"


def _read_text(name: str) -> str:
    return files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def runtime_lock_text() -> str:
    return _read_text(RUNTIME_LOCK_NAME)


def runtime_lock_digest() -> str:
    return sha256_bytes(runtime_lock_text().encode("utf-8"))


def load_headless_runtime_limits() -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(RUNTIME_LIMITS_NAME))
    if not isinstance(payload, dict):
        raise ValueError(f"{RUNTIME_LIMITS_NAME} must be a mapping")
    return payload


def headless_runtime_limits_digest() -> str:
    return sha256_bytes(_read_text(RUNTIME_LIMITS_NAME).encode("utf-8"))


def load_packaging_inventory() -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(PACKAGING_INVENTORY_NAME))
    if not isinstance(payload, dict):
        raise ValueError(f"{PACKAGING_INVENTORY_NAME} must be a mapping")
    return payload


def operational_profile_id() -> str:
    profile = load_headless_runtime_limits()
    return str(profile.get("profile_id") or "")


def budgets_from_packaged_limits() -> BudgetLimits:
    raw = load_headless_runtime_limits().get("budgets")
    if not isinstance(raw, dict):
        raise ValueError("headless runtime limits must include budgets mapping")
    return BudgetLimits.model_validate(raw)
