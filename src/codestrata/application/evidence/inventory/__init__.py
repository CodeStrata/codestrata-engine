"""E05 inventory: classification, depth pin, fact emission and projections."""

from codestrata.application.evidence.inventory.capability import (
    CAPABILITY_MANIFEST_VERSION,
    capability_manifests,
)
from codestrata.application.evidence.inventory.catalog import build_extractor_depth_pin
from codestrata.application.evidence.inventory.classification import InventoryPrimaryClassifier
from codestrata.application.evidence.inventory.consumer import consume_envelope
from codestrata.application.evidence.inventory.emission import InventoryFactEmitter
from codestrata.application.evidence.inventory.envelope import (
    InventoryEnvelope,
    seal_inventory_envelope,
)
from codestrata.application.evidence.inventory.facts import (
    INVENTORY_EMITTER_VERSION,
    INVENTORY_FACT_SCHEMA_VERSION,
    InventoryFactBundle,
)
from codestrata.application.evidence.inventory.fixture_map import INVENTORY_FIXTURE_MAP
from codestrata.application.evidence.inventory.models import (
    CLASSIFIER_VERSION,
    EXTRACTOR_DEPTH_PIN_VERSION,
    ExtractorDepthPin,
    RepositoryInventorySnapshot,
)
from codestrata.application.evidence.inventory.projections import (
    project_inventory_html,
    project_inventory_json,
    project_inventory_sarif,
)
from codestrata.application.evidence.inventory.service import ExtractorInventoryService
from codestrata.application.evidence.inventory.walk import walk_repository

__all__ = [
    "CAPABILITY_MANIFEST_VERSION",
    "CLASSIFIER_VERSION",
    "EXTRACTOR_DEPTH_PIN_VERSION",
    "INVENTORY_EMITTER_VERSION",
    "INVENTORY_FACT_SCHEMA_VERSION",
    "ExtractorDepthPin",
    "ExtractorInventoryService",
    "INVENTORY_FIXTURE_MAP",
    "InventoryEnvelope",
    "InventoryFactBundle",
    "InventoryFactEmitter",
    "InventoryPrimaryClassifier",
    "RepositoryInventorySnapshot",
    "build_extractor_depth_pin",
    "capability_manifests",
    "consume_envelope",
    "project_inventory_html",
    "project_inventory_json",
    "project_inventory_sarif",
    "seal_inventory_envelope",
    "walk_repository",
]
