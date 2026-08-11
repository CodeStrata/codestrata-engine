"""SV.11.3 — Standardized Provider and Model Configuration verification (Epic 11, Slice 11.3).

Verifies the new, unwired ``codestrata.ai.provider_contracts.configuration_*``
modules: their dependency boundary (no product-path imports either
direction, no ``os.environ``/filesystem reads in domain logic), their
bounded value objects, their compatibility with the Slice 11.1 baseline
(CR-1..CR-6, loaded for real from ``verification.ai_provider_baseline``),
provider selection and model resolution correctness against ground truth,
credential-requirement shape, adapter-configuration type safety, privacy,
and determinism. Not shipped in the ``codestrata`` wheel.
"""

from __future__ import annotations
