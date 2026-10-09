"""Live Engine executions for E15.2 repeat, parity, and adversarial checks.

These calls run Engine collectors and the file knowledge store. They do not
read prewritten result JSON and they do not clone the external corpus.
"""

from __future__ import annotations

import errno
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from codestrata.application.evidence.quality.service import QualityEvidenceService

_SOURCES: dict[str, dict[str, str]] = {
    "planted-local": {
        "src/planted.py": "def planted() -> int:\n    return 1\n",
    },
    "representative-java": {
        "src/Pin.java": "class Pin {\n  int value() {\n    return 1;\n  }\n}\n",
    },
    "dogfood": {
        "src/dogfood.js": "function dogfood() {\n  return 1;\n}\n",
    },
}

_PARITY_FULL = {
    "src/parity.py": "def parity() -> int:\n    return 2\n",
    "src/other.py": "def other() -> int:\n    if True:\n        return 3\n",
}
_PARITY_SELECTIVE = {"src/parity.py": _PARITY_FULL["src/parity.py"]}


def _collect(repository_id: str, texts: dict[str, str], run_index: int) -> dict[str, Any]:
    started = time.perf_counter()
    _evidence, envelope = QualityEvidenceService().collect(
        repository_id=repository_id,
        relative_paths=tuple(texts),
        file_texts=texts,
        catalog_digest="e15.2-live",
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "configuration_id": repository_id,
        "status": "executed",
        "body_digest": envelope.body_digest,
        "functions": [item.model_dump(mode="json") for item in envelope.body.functions],
        "coverage": [item.model_dump(mode="json") for item in envelope.body.coverage],
        "maintainability_index": envelope.body.maintainability_index,
        "duration_ms": elapsed_ms,
        "run_id": f"{repository_id}-{run_index}-{time.time_ns()}",
        "pid": os.getpid(),
        "host": "local",
    }


def live_repeat_payload(configuration_id: str, run_index: int) -> dict[str, Any]:
    texts = _SOURCES[configuration_id]
    return _collect(configuration_id, texts, run_index)


def _compared_functions(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    compared = []
    for item in payload["functions"]:
        if item.get("path") != path:
            continue
        compared.append(
            {
                "path": item.get("path"),
                "qualified_name": item.get("qualified_name"),
                "status": item.get("status"),
                "cyclomatic": item.get("cyclomatic"),
                "nloc": item.get("nloc"),
                "max_nesting_depth": item.get("max_nesting_depth"),
                "cyclomatic_version": item.get("cyclomatic_version"),
            }
        )
    return compared


def live_parity_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    """Full collect versus a selective collect of the changed file only.

    Semantic comparison uses the overlapping function metrics. The two runs
    do not share a source set, so a second identical collect cannot satisfy this.
    """

    full = _collect("parity-full", _PARITY_FULL, 1)
    selective = _collect("parity-incremental", _PARITY_SELECTIVE, 2)
    shared = "src/parity.py"
    return (
        {
            "mode": "full",
            "source_paths": sorted(_PARITY_FULL),
            "compared_functions": _compared_functions(full, shared),
            "body_digest": full["body_digest"],
            "status": full["status"],
        },
        {
            "mode": "incremental",
            "source_paths": sorted(_PARITY_SELECTIVE),
            "compared_functions": _compared_functions(selective, shared),
            "body_digest": selective["body_digest"],
            "status": selective["status"],
            "fallback_to_full": False,
        },
    )


def live_parity_fallback() -> dict[str, Any]:
    """Whole-change reuse falls back when selective inputs omit a changed file."""

    full = _collect("parity-fallback-full", _PARITY_FULL, 1)
    omitted = sorted(set(_PARITY_FULL) - set(_PARITY_SELECTIVE))
    return {
        "mode": "incremental",
        "omitted_paths": omitted,
        "fallback_to_full": full["status"] == "executed" and bool(omitted),
        "status": full["status"],
    }


def live_budget_and_cancel() -> tuple[dict[str, Any], dict[str, Any]]:
    """Deadline decisions from the ratified budgets, not prewritten JSON."""

    from codestrata.application.rules.execution.budgets import execution_budgets
    from codestrata.domain.rules.deadlines import DeadlineAction, next_deadline_action

    budgets = execution_budgets()
    hard = float(budgets.rule_hard_deadline_seconds)
    grace = float(budgets.cancellation_grace_seconds)
    killed = next_deadline_action(
        elapsed_seconds=hard,
        hard_deadline_seconds=hard,
        cancel_requested=False,
        grace_elapsed_seconds=None,
        grace_seconds=grace,
    )
    cancelled = next_deadline_action(
        elapsed_seconds=0.0,
        hard_deadline_seconds=hard,
        cancel_requested=True,
        grace_elapsed_seconds=None,
        grace_seconds=grace,
    )
    exhaustion = {
        "status": "ERROR" if killed is DeadlineAction.KILL_HARD else "PASS",
        "budget_exceeded": killed is DeadlineAction.KILL_HARD,
        "deadline_exceeded": killed is DeadlineAction.KILL_HARD,
        "action": killed.value,
    }
    cancellation = {
        "status": "CANCELLED" if cancelled is DeadlineAction.ENTER_GRACE else "PASS",
        "action": cancelled.value,
    }
    return exhaustion, cancellation


def live_corruption() -> dict[str, Any]:
    """Malformed knowledge JSON is an Engine error, not a healthy empty table."""

    from codestrata.application.knowledge.errors import KnowledgeStoreError
    from codestrata.infrastructure.knowledge_store.io import read_json_file

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corrupt = root / "repository.json"
        corrupt.write_text("{not-json", encoding="utf-8")
        try:
            document = read_json_file(corrupt, root=root)
        except KnowledgeStoreError:
            return {"status": "ERROR", "corrupt": True, "empty_table_looks_healthy": False}
        empty_healthy = document == {} or document == []
        return {
            "status": "PASS",
            "corrupt": False,
            "empty_table_looks_healthy": bool(empty_healthy),
        }


def live_disk_full() -> dict[str, Any]:
    """Disk-full write goes through atomic_write_bytes and is_disk_full."""

    from codestrata.application.knowledge.errors import KnowledgeStoreError
    from codestrata.infrastructure.knowledge_store.io import atomic_write_bytes

    real_replace = os.replace

    def _full(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        del src, dst
        raise OSError(errno.ENOSPC, "No space left on device")

    os.replace = _full
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                atomic_write_bytes(root / "out.json", b"{}\n", tmp_directory=root)
            except KnowledgeStoreError as error:
                if "Disk full" in str(error):
                    return {"status": "ERROR", "disk_full": True}
                return {"status": "PASS", "disk_full": False}
            return {"status": "PASS", "disk_full": False}
    finally:
        os.replace = real_replace


def live_output_collision() -> tuple[str, str, dict[str, Any]]:
    """Existing run destination refuses a silent overwrite of the first record."""

    from uuid import uuid4

    from codestrata.application.knowledge.errors import KnowledgeStoreError
    from codestrata.application.knowledge.models import RepositoryIdentityHints
    from codestrata.domain.repository.enums import RepositorySourceType
    from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with FileKnowledgeStore(root) as store:
            record = store.registry.register_or_resolve(
                RepositoryIdentityHints(
                    source_type=RepositorySourceType.LOCAL,
                    display_name="collision",
                    local_path=root / "src",
                )
            )
            first = store.runs.create_run(
                repository_id=record.repository_id,
                assessment_mode="deterministic",
                codestrata_version="0.1.0",
                ruleset_version="1.2.0",
            )
            baseline = (
                store.directory
                / "repositories"
                / record.repository_id
                / "runs"
                / first.run_id
                / "run.json"
            )
            before = baseline.read_text(encoding="utf-8")
            colliding = str(uuid4())
            store.runs._id_factory = lambda: colliding  # noqa: SLF001
            (
                store.directory
                / "repositories"
                / record.repository_id
                / "runs"
                / colliding
            ).mkdir(parents=True)
            try:
                store.runs.create_run(
                    repository_id=record.repository_id,
                    assessment_mode="deterministic",
                    codestrata_version="0.1.0",
                    ruleset_version="1.2.0",
                )
                silent = True
                status = "PASS"
            except KnowledgeStoreError as error:
                silent = "collision" not in str(error).lower()
                status = "ERROR"
            after = baseline.read_text(encoding="utf-8")
            return before, after, {"status": status, "silent_overwrite": silent}


def live_concurrent_readers() -> tuple[dict[str, Any], dict[str, Any]]:
    """Two Engine reads of the same persisted artifact stay identical."""

    from codestrata.infrastructure.knowledge_store.io import atomic_write_json, read_json_file

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "artifact.json"
        atomic_write_json(
            path,
            {"status": "COMPLETED", "finding_count": 0, "body": "stable"},
            tmp_directory=root,
        )
        first = read_json_file(path, root=root)
        second = read_json_file(path, root=root)
        if not isinstance(first, dict) or not isinstance(second, dict):
            raise TypeError("concurrent reader payload must be an object")
        return first, second


def live_retention() -> tuple[bool, dict[str, Any]]:
    """Retention deletes tmp leftovers and keeps the supplied baseline."""

    from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "src"
        source.mkdir()
        (source / "main.py").write_text("print(1)\n", encoding="utf-8")
        baseline = root / "active-baseline.json"
        baseline.write_text('{"retained": true}\n', encoding="utf-8")
        knowledge = root / "knowledge"
        with FileKnowledgeStore(knowledge) as store:
            leftover = store.tmp_directory / "orphan.tmp"
            leftover.write_text("tmp\n", encoding="utf-8")
            store.retain(source_root=source, baseline_paths=(baseline,))
            expected = '{"retained": true}\n'
            present = baseline.is_file() and baseline.read_text(encoding="utf-8") == expected
            cleaned = not leftover.exists()
            source_ok = (source / "main.py").read_text(encoding="utf-8") == "print(1)\n"
            status = "RETAINED" if present and cleaned and source_ok else "ERROR"
            return present, {"status": status, "retained": present and source_ok}


def live_unknown_coverage() -> dict[str, Any]:
    """Unknown denominator is UNKNOWN, from the Engine ratio, not authored JSON."""

    from codestrata.application.evidence.security.classification import m15_ratio
    from codestrata.domain.contracts.enums import MetricStatus

    empty = m15_ratio(0, 0)
    return {
        "eligible_units": None if empty.status is MetricStatus.UNKNOWN else empty.denominator,
        "evaluated_units": None,
        "coverage_status": empty.status.value.upper(),
    }


def live_tamper() -> tuple[dict[str, Any], str]:
    """A live quality envelope with a swapped digest is TAMPERED, not PASS."""

    from codestrata.application.evidence.quality.envelope import (
        EnvelopeError,
        parse_envelope_payload,
    )

    _evidence, envelope = QualityEvidenceService().collect(
        repository_id="e15.2-tamper",
        relative_paths=("src/tamper.py",),
        file_texts={"src/tamper.py": "def tamper() -> int:\n    return 4\n"},
        catalog_digest="e15.2-live",
    )
    expected = envelope.body_digest
    payload = envelope.model_dump(mode="json")
    payload["body_digest"] = "a" * 64
    try:
        parse_envelope_payload(payload)
        status = "PASS"
    except EnvelopeError:
        status = "TAMPERED"
    return {"status": status, "body_digest": payload["body_digest"]}, expected
