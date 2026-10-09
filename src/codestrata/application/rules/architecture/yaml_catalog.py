"""Load architecture launch YAML through the E03.1 compiler."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from codestrata.application.rules.compiler import (
    CapabilityError,
    YamlCompileError,
    compile_rule_yaml,
)
from codestrata.application.rules.execution.planner import CatalogEntry
from codestrata.domain.rules.compiler_models import CompilationPlan

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
ARCHITECTURE_LAUNCH_RULE_IDS: tuple[str, ...] = (
    "architecture.cycles",
    "architecture.fan-out",
    "architecture.boundary",
    "architecture.concentration",
    "architecture.invalid-dependency-direction",
    "architecture.framework-leakage",
)
BOUNDARY_RULE_ID = "architecture.boundary"
CONCENTRATION_RULE_ID = "architecture.concentration"
DIRECTION_RULE_ID = "architecture.invalid-dependency-direction"
LEAKAGE_RULE_ID = "architecture.framework-leakage"
SPECIAL_CASE_RULE_IDS: frozenset[str] = frozenset(
    {BOUNDARY_RULE_ID, DIRECTION_RULE_ID, LEAKAGE_RULE_ID}
)
FAN_OUT_THRESHOLD_DEFAULT = 10


class ArchitectureYamlCatalogError(ValueError):
    """Bundled architecture launch YAML failed to compile or match its id."""


@lru_cache(maxsize=1)
def load_architecture_launch_plans() -> dict[str, CompilationPlan]:
    loaded: dict[str, CompilationPlan] = {}
    for rule_id in ARCHITECTURE_LAUNCH_RULE_IDS:
        path = CATALOG_DIR / f"{rule_id}.yaml"
        if not path.is_file():
            raise ArchitectureYamlCatalogError(f"missing bundled rule YAML: {path.name}")
        try:
            plan = compile_rule_yaml(path.read_bytes(), label=path.name)
        except (YamlCompileError, CapabilityError, ValueError) as error:
            raise ArchitectureYamlCatalogError(f"{path.name} failed to compile: {error}") from error
        if plan.rule is None or plan.condition is None:
            raise ArchitectureYamlCatalogError(f"{path.name} did not compile to a Rule")
        if plan.rule.metadata.id != rule_id:
            raise ArchitectureYamlCatalogError(
                f"YAML id {plan.rule.metadata.id} does not match {rule_id}"
            )
        loaded[rule_id] = plan
    return loaded


@lru_cache(maxsize=1)
def architecture_catalog_entries() -> tuple[CatalogEntry, ...]:
    entries: list[CatalogEntry] = []
    for rule_id in ARCHITECTURE_LAUNCH_RULE_IDS:
        path = CATALOG_DIR / f"{rule_id}.yaml"
        if not path.is_file():
            raise ArchitectureYamlCatalogError(f"missing bundled rule YAML: {path.name}")
        entries.append(
            CatalogEntry(
                rule_id=rule_id,
                yaml_text=path.read_text(encoding="utf-8"),
                enabled=True,
                rule_revision="1.0.0",
            )
        )
    load_architecture_launch_plans()
    return tuple(entries)


def architecture_catalog_digests() -> dict[str, str]:
    pack = CATALOG_DIR / "pack.yaml"
    plans = load_architecture_launch_plans()
    digests = {
        rule_id: sha256((CATALOG_DIR / f"{rule_id}.yaml").read_bytes()).hexdigest()
        for rule_id in ARCHITECTURE_LAUNCH_RULE_IDS
    }
    if pack.is_file():
        digests["pack"] = sha256(pack.read_bytes()).hexdigest()
    for rule_id, plan in plans.items():
        digests[f"{rule_id}.plan"] = plan.plan_digest
    return digests


__all__ = [
    "ARCHITECTURE_LAUNCH_RULE_IDS",
    "BOUNDARY_RULE_ID",
    "CATALOG_DIR",
    "CONCENTRATION_RULE_ID",
    "DIRECTION_RULE_ID",
    "LEAKAGE_RULE_ID",
    "SPECIAL_CASE_RULE_IDS",
    "FAN_OUT_THRESHOLD_DEFAULT",
    "ArchitectureYamlCatalogError",
    "architecture_catalog_digests",
    "architecture_catalog_entries",
    "load_architecture_launch_plans",
]
