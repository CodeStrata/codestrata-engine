"""Safety and resource checks for SV.10."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DiskCheck:
    ok: bool
    available_gb: float
    required_gb: float
    detail: str


# Conservative estimates for working clone+assess space by tier (GB).
TIER_DISK_ESTIMATE_GB: dict[str, float] = {
    "tier1": 2.0,
    "tier2": 5.0,
    "tier3": 4.0,
    "tier4": 12.0,
}


def available_disk_gb(path: Path | None = None) -> float:
    usage = shutil.disk_usage(str(path or Path.cwd()))
    return usage.free / (1024**3)


def check_disk_for_tier(tier: str, *, path: Path | None = None) -> DiskCheck:
    required = float(TIER_DISK_ESTIMATE_GB.get(tier, 8.0))
    available = available_disk_gb(path)
    ok = available >= required
    return DiskCheck(
        ok=ok,
        available_gb=round(available, 2),
        required_gb=required,
        detail="ok" if ok else f"insufficient disk: need>={required}GiB free, have={available:.2f}GiB",
    )


def forbidden_product_touch_markers() -> tuple[str, ...]:
    return (
        ".terraform",
        "infrastructure/terraform",
        "node_modules",
        ".venv",
        "target/",
        "dist/",
        "build/",
    )
