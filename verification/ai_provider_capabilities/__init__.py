"""SV.11.5 — Provider Usage Metadata and Capability Discovery verification (Epic 11, Slice 11.5).

Verifies the 12 new, unwired ``codestrata.ai.provider_contracts.
capability_*``/``usage_*`` modules (plus the in-place extension of
``usage.py``): their dependency boundary, their bounded value objects, the
two static baseline capability catalogs, their compatibility with the Slice
11.1 baseline (CR-1..CR-6) and with Slices 11.2/11.3/11.4, their privacy
properties, and their determinism. Not shipped in the ``codestrata`` wheel.
"""

from __future__ import annotations
