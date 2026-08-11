"""SV.11.4 — Standardized Execution, Errors, Timeouts, and Retries verification (Epic 11, 11.4).

Verifies the new, unwired ``codestrata.ai.provider_contracts.execution_*``
(plus ``timeout_policy.py``/``retry_policy.py``/``retry_decision.py``/
``backoff.py``/``error_classification.py``/``executor.py``) modules: their
dependency boundary (no product-path imports either direction, no
``os``/``pathlib``/``subprocess``/``threading``/``asyncio``/``signal`` in
domain logic), their bounded value objects, their compatibility with the
Slice 11.1 baseline (CR-1..CR-6, loaded for real from
``verification.ai_provider_baseline``), timeout/retry/backoff policy
correctness against ground truth, fail-soft executor behavior (never raises
for an expected failure; never swallows ``KeyboardInterrupt``/``SystemExit``),
privacy, and determinism. Not shipped in the ``codestrata`` wheel.
"""

from __future__ import annotations
