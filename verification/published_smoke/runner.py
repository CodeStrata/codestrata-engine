"""Readiness checks and optional fixture smoke for published artifacts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict

from verification.live_release_baseline.models import InferenceError
from verification.published_smoke.models import SmokeDecision, SmokeReadiness, SmokeTargets
from verification.published_smoke.plan import build_five_repository_plan, load_targets
from verification.published_smoke.pypi_client import fetch_pypi_project, wheel_sha256_for_version


def evaluate_readiness(
    targets: SmokeTargets | None = None,
    *,
    timeout_seconds: float = 30.0,
) -> SmokeReadiness:
    cfg = targets or load_targets()
    notes: list[str] = []
    try:
        project = fetch_pypi_project(cfg.pypi_project, timeout_seconds=timeout_seconds)
    except InferenceError as exc:
        return SmokeReadiness(
            decision=SmokeDecision.BLOCKED,
            pypi_versions=(),
            candidate_on_pypi=False,
            candidate_digest_recorded=bool(cfg.candidate_wheel_sha256),
            notes=(str(exc),),
        )
    versions = project.versions
    candidate_on_pypi = cfg.candidate_semver in versions
    digest_recorded = bool(cfg.candidate_wheel_sha256.strip())
    if not candidate_on_pypi:
        notes.append(
            f"PyPI lists {project.live_version} only; "
            f"candidate {cfg.candidate_semver} not published"
        )
        return SmokeReadiness(
            decision=SmokeDecision.BLOCKED,
            pypi_versions=versions,
            candidate_on_pypi=False,
            candidate_digest_recorded=digest_recorded,
            notes=tuple(notes),
        )
    try:
        live_sha = wheel_sha256_for_version(
            cfg.pypi_project,
            cfg.candidate_semver,
            timeout_seconds=timeout_seconds,
        )
    except InferenceError as exc:
        notes.append(str(exc))
        return SmokeReadiness(
            decision=SmokeDecision.BLOCKED,
            pypi_versions=versions,
            candidate_on_pypi=True,
            candidate_digest_recorded=digest_recorded,
            notes=tuple(notes),
        )
    if digest_recorded and live_sha != cfg.candidate_wheel_sha256:
        notes.append("Published wheel digest does not match candidate_wheel_sha256 in targets.yaml")
        return SmokeReadiness(
            decision=SmokeDecision.FAIL,
            pypi_versions=versions,
            candidate_on_pypi=True,
            candidate_digest_recorded=True,
            notes=tuple(notes),
        )
    if not digest_recorded:
        notes.append(
            "Candidate is on PyPI but candidate_wheel_sha256 is empty; "
            "record release-owner approval digest before G52 PASS"
        )
        return SmokeReadiness(
            decision=SmokeDecision.BLOCKED,
            pypi_versions=versions,
            candidate_on_pypi=True,
            candidate_digest_recorded=False,
            notes=tuple(notes),
        )
    notes.append("Candidate semver and wheel digest match targets.yaml")
    return SmokeReadiness(
        decision=SmokeDecision.PASS,
        pypi_versions=versions,
        candidate_on_pypi=True,
        candidate_digest_recorded=True,
        notes=tuple(notes),
    )


def readiness_json(targets: SmokeTargets | None = None) -> str:
    readiness = evaluate_readiness(targets)
    payload = {
        "decision": readiness.decision.value,
        "pypi_versions": list(readiness.pypi_versions),
        "candidate_on_pypi": readiness.candidate_on_pypi,
        "candidate_digest_recorded": readiness.candidate_digest_recorded,
        "notes": list(readiness.notes),
        "five_repository_plan": [asdict(item) for item in build_five_repository_plan()],
    }
    if targets is not None:
        payload["candidate_semver"] = targets.candidate_semver
        payload["rollback_semver"] = targets.rollback_semver
    return json.dumps(payload, indent=2, sort_keys=True)


def run_cli_smoke(installed_codestrata: str, *, cwd: str) -> dict[str, int]:
    """Minimal CLI/MCP/no-consent checks on an already-installed published engine."""
    from codestrata.application.release.standalone.install_verify import scrubbed_environ

    env = scrubbed_environ()
    env["CI"] = "1"
    env["TERM"] = "dumb"
    steps = {
        "version": [installed_codestrata, "--version"],
        "telemetry_status": [installed_codestrata, "telemetry", "status", "--json"],
        "mcp_help": [installed_codestrata, "mcp", "--help"],
    }
    exits: dict[str, int] = {}
    for name, argv in steps.items():
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        exits[name] = completed.returncode
    return exits
