"""Decide, verify, and shape an Engine worker release without trusting the trigger.

The published 0.3.0 wheel and its existing registry image are retained. A later
stable version is downloaded from PyPI and checked before any image is built.
An unverified git commit is never recorded as package provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

ACCOUNT = "373220260833"
REGION = "us-west-2"
REPOSITORY = "codestrata-launch-trial-engine"
ENGINE_REPOSITORY = "CodeStrata/codestrata-engine"
PYPI_PROJECT = "codestrata"
WHEEL_HOST = "https://files.pythonhosted.org/"
QUALIFIED_WHEEL = "c4f0ea0f38aef2075e060a5c2bae3fa9a32a0277f336087dc0c03ab71fdd357d"
QUALIFIED_IMAGE = (
    "373220260833.dkr.ecr.us-west-2.amazonaws.com/"
    "codestrata-launch-trial-engine@sha256:"
    "ed95672fbcd1e6708ee179f9858577e652180781587499c2d1f9836ed08e6b44"
)
_STABLE = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")
_REGISTER_DROP = {
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "compatibilities",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
}
_VERSION_ENV = "CODESTRATA_ENGINE_VERSION"
_WHEEL_ENV = "CODESTRATA_ENGINE_WHEEL_SHA256"
_DISPATCH_ENV = "CODESTRATA_HOSTED_TASK_DEFINITION"


def is_stable(version: str) -> bool:
    return bool(_STABLE.fullmatch(version))


def version_key(version: str) -> tuple[int, ...]:
    if not is_stable(version):
        raise ValueError(f"not a stable version: {version}")
    return tuple(int(part) for part in version.split("."))


IMAGE_REPOSITORY = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}"


def engine_image_uri(digest: str) -> str:
    token = digest.removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ValueError("engine digest must be 64 hex characters")
    return f"{IMAGE_REPOSITORY}@sha256:{token}"


def decide(
    *,
    event: str,
    requested_version: str,
    requested_sha256: str,
    deployed_version: str,
    deployed_image: str,
    rollout_enabled: bool,
    pypi_versions: list[str],
    pypi_sha256: str = "",
) -> dict[str, str]:
    """Return the only action the workflow may take for this trigger."""

    if event not in {"workflow_dispatch", "repository_dispatch", "schedule"}:
        raise ValueError("release trigger is not a package publication path")
    deployed = "" if deployed_version in {"", "unset"} else deployed_version
    if event == "schedule":
        version = _newest_stable(pypi_versions)
        wheel = pypi_sha256
    else:
        version = requested_version
        wheel = requested_sha256.lower()
        if not is_stable(version):
            return {"action": "reject", "reason": "prerelease", "version": version}
    if version == "0.3.0":
        if wheel != QUALIFIED_WHEEL:
            return {"action": "reject", "reason": "qualified-wheel-mismatch", "version": version}
        if deployed and version_key(deployed) > version_key("0.3.0"):
            return {"action": "reject", "reason": "downgrade", "version": version}
        return {
            "action": "retain",
            "reason": "qualified-0.3.0",
            "version": "0.3.0",
            "wheel_sha256": QUALIFIED_WHEEL,
            "image": QUALIFIED_IMAGE,
        }
    if not is_stable(version):
        return {"action": "reject", "reason": "prerelease", "version": version}
    if deployed and version_key(version) < version_key(deployed):
        return {"action": "reject", "reason": "downgrade", "version": version}
    if deployed == version:
        return {"action": "skip", "reason": "already-deployed", "version": version}
    if not rollout_enabled:
        return {"action": "observe", "reason": "rollout-disabled", "version": version, "wheel_sha256": wheel}
    return {"action": "release", "reason": "stable-upgrade", "version": version, "wheel_sha256": wheel}


def _newest_stable(versions: list[str]) -> str:
    stable = [version for version in versions if is_stable(version)]
    if not stable:
        raise ValueError("PyPI has no stable codestrata version")
    return max(stable, key=version_key)


def listed_versions(document: dict[str, Any]) -> list[str]:
    versions: list[str] = []
    for version, files in (document.get("releases") or {}).items():
        if files and not all(item.get("yanked") for item in files):
            versions.append(str(version))
    return versions


def confirmed_digest(requested: str, published: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", published):
        raise ValueError("package index digest is missing")
    if requested and requested.lower() != published.lower():
        raise ValueError("trigger digest does not match the package index")
    return published.lower()


def select_wheel_file(files: list[dict[str, Any]]) -> dict[str, Any]:
    wheels = [
        item
        for item in files
        if str(item.get("packagetype")) == "bdist_wheel"
        and str(item.get("filename", "")).endswith("-py3-none-any.whl")
        and str(item.get("url", "")).startswith(WHEEL_HOST)
    ]
    if len(wheels) != 1:
        raise ValueError("expected one py3-none-any wheel on the Python package index")
    digest = str((wheels[0].get("digests") or {}).get("sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("package index did not publish a sha256 digest")
    return wheels[0]


def download_wheel(url: str, destination: Path, expected_sha256: str) -> str:
    if not url.startswith(WHEEL_HOST) or not expected_sha256:
        raise ValueError("wheel download must use the Python package index and a digest")
    request = urllib.request.Request(url, headers={"User-Agent": "codestrata-hosted-worker"})
    with urllib.request.urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
        final = response.geturl()
        if not final.startswith(WHEEL_HOST):
            raise ValueError("wheel download left the Python package index")
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("downloaded wheel digest does not match the published digest")
    destination.write_bytes(payload)
    return digest


def provenance_record(
    *,
    version: str,
    wheel_sha256: str,
    image: str,
    build_identity: dict[str, str],
    source_commit: str = "",
    source_verified: bool = False,
) -> dict[str, Any]:
    if source_commit and not source_verified:
        raise ValueError("an unverified source commit is not package provenance")
    if not image.startswith(f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}@sha256:"):
        raise ValueError("image is not the hosted Engine repository digest")
    source = None
    if source_verified and source_commit:
        source = {"repository": ENGINE_REPOSITORY, "commit": source_commit}
    return {
        "package": PYPI_PROJECT,
        "version": version,
        "wheel_sha256": wheel_sha256,
        "source_identity": source,
        "build_identity": build_identity,
        "ecr_manifest_digest": image,
    }


def revise_task_definition(
    current: dict[str, Any],
    *,
    image: str,
    version: str,
    wheel_sha256: str,
) -> dict[str, Any]:
    """Copy a task definition and change only the Engine image and version metadata."""

    engine_image_uri(image.rsplit("sha256:", 1)[-1])
    if not image.startswith(f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}@sha256:"):
        raise ValueError("replacement image is outside the Engine repository")
    payload = {key: value for key, value in current.items() if key not in _REGISTER_DROP}
    containers = payload.get("containerDefinitions")
    if not isinstance(containers, list):
        raise ValueError("task definition has no containers")
    originals = json.loads(json.dumps(containers))
    engine = next((item for item in containers if item.get("name") == "engine"), None)
    if engine is None:
        raise ValueError("task definition has no engine container")
    if engine.get("user") != "10001:10001" or engine.get("readonlyRootFilesystem") is not True:
        raise ValueError("engine container no longer matches the read-only contract")
    engine["image"] = image
    environment = [
        item
        for item in engine.get("environment") or []
        if item.get("name") not in {_VERSION_ENV, _WHEEL_ENV}
    ]
    environment.extend(
        [
            {"name": _VERSION_ENV, "value": version},
            {"name": _WHEEL_ENV, "value": wheel_sha256},
        ]
    )
    engine["environment"] = environment
    for original, updated in zip(originals, containers, strict=True):
        if original.get("name") == "engine":
            continue
        if original != updated:
            raise ValueError("a non-engine container changed")
    rendered = json.dumps(payload)
    if "tmpfs" in rendered or '"privileged": true' in rendered or "efsVolumeConfiguration" in rendered:
        raise ValueError("unsupported Fargate parameter")
    return payload


def with_task_definition(environment: dict[str, str], task_arn: str) -> dict[str, str]:
    if not task_arn.startswith(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/codestrata-launch-worker:"):
        raise ValueError("dispatch ARN is not a hosted worker revision")
    updated = dict(environment)
    updated[_DISPATCH_ENV] = task_arn
    for key, value in environment.items():
        if key != _DISPATCH_ENV and updated[key] != value:
            raise ValueError("dispatcher environment changed beyond the task definition")
    return updated


def restored_dispatch(previous_arn: str, failed_arn: str) -> str:
    if previous_arn in {"", "unset"} or previous_arn == failed_arn:
        raise ValueError("there is no previous dispatch revision to restore")
    if not previous_arn.startswith(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/codestrata-launch-worker:"):
        raise ValueError("previous dispatch ARN is not a hosted worker revision")
    return previous_arn


PRODUCTION_COMPLETION_QUEUE = (
    "https://sqs.us-west-2.amazonaws.com/373220260833/codestrata-launch-completion"
)
CANARY_COMPLETION_QUEUE = (
    "https://sqs.us-west-2.amazonaws.com/373220260833/codestrata-launch-worker-canary"
)


def isolated_canary_job(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("canary run id is not isolated")
    return f"canary-{run_id}"


def is_canary_payload(payload: Mapping[str, Any]) -> bool:
    job_id = str(payload.get("job_id", ""))
    staging_key = str(payload.get("staging_key", ""))
    return job_id.startswith("canary-") or staging_key.startswith("staging/canary-")


def canary_container_overrides(job_id: str) -> dict[str, Any]:
    """Canary completion stays on the canary queue and cannot start production delivery."""

    if not job_id.startswith("canary-") or job_id == "canary-":
        raise ValueError("canary job is not isolated")
    identity = [
        {"name": "CODESTRATA_JOB_ID", "value": job_id},
        {"name": "CODESTRATA_ATTEMPT", "value": "1"},
    ]
    repository = {"name": "CODESTRATA_REPO_URL", "value": "https://github.com/octocat/Hello-World"}
    completion = {"name": "CODESTRATA_HOSTED_COMPLETION_QUEUE_URL", "value": CANARY_COMPLETION_QUEUE}
    overrides = {
        "containerOverrides": [
            {"name": "setup", "environment": [*identity, repository]},
            {"name": "engine", "environment": [*identity, repository]},
            {"name": "cleanup", "environment": [*identity, completion]},
        ]
    }
    rendered = json.dumps(overrides)
    if PRODUCTION_COMPLETION_QUEUE in rendered or "codestrata-launch-delivery" in rendered:
        raise ValueError("canary targets production delivery")
    return overrides


def guarded_release(
    *,
    rollout_enabled: bool,
    production: Callable[[], Mapping[str, str]],
    register: Callable[[], str],
    canary: Callable[[str], None],
    promote: Callable[[str], None],
    verify_promotion: Callable[[str], None],
    restore: Callable[[Mapping[str, str]], None],
) -> str:
    """Register and canary first. Production dispatch changes only after the canary passes."""

    if not rollout_enabled:
        raise RuntimeError("production rollout is disabled")
    before = dict(production())
    revision = register()
    try:
        canary(revision)
    except Exception:
        _restore_if_changed(before, production, restore)
        raise
    _require_unchanged(before, production(), restore)
    promote(revision)
    try:
        verify_promotion(revision)
    except Exception:
        restore(before)
        _require_unchanged(before, production(), restore)
        raise
    return revision


def guarded_drill(
    *,
    explicit: bool,
    image: str,
    qualified_image: str,
    production: Callable[[], Mapping[str, str]],
    register: Callable[[], str],
    canary: Callable[[str], None],
    promote: Callable[[str], None],
    verify_promotion: Callable[[str], None],
    restore: Callable[[Mapping[str, str]], None],
) -> str:
    """Exercise deploy permissions, then put the recorded production snapshot back."""

    if not explicit:
        raise RuntimeError("deploy-role drill requires explicit verification mode")
    if image != qualified_image:
        raise RuntimeError("drill uses only the qualified 0.3.0 image")
    before = dict(production())
    if before.get("rollout") != "disabled":
        raise RuntimeError("drill does not run while production rollout is enabled")
    revision = register()
    try:
        canary(revision)
    except Exception:
        _restore_if_changed(before, production, restore)
        raise
    _require_unchanged(before, production(), restore)
    promote(revision)
    try:
        verify_promotion(revision)
    except Exception:
        restore(before)
        _require_unchanged(before, production(), restore)
        raise
    restore(before)
    _require_unchanged(before, production(), restore)
    return revision


def _require_unchanged(
    before: Mapping[str, str],
    after: Mapping[str, str],
    restore: Callable[[Mapping[str, str]], None],
) -> None:
    if dict(after) != dict(before):
        restore(before)
        raise RuntimeError("production dispatch changed")


def _restore_if_changed(
    before: Mapping[str, str],
    production: Callable[[], Mapping[str, str]],
    restore: Callable[[Mapping[str, str]], None],
) -> None:
    if dict(production()) != dict(before):
        restore(before)
        if dict(production()) != dict(before):
            raise RuntimeError("production dispatch changed")


def canary_errors(*, task: dict[str, Any], message: dict[str, Any] | None, artifact_present: bool) -> list[str]:
    errors: list[str] = []
    if str(task.get("lastStatus", "")).upper() != "STOPPED":
        errors.append("not-stopped")
    containers = {item.get("name"): item for item in task.get("containers") or []}
    for name in ("setup", "engine", "cleanup"):
        container = containers.get(name) or {}
        if container.get("exitCode") != 0:
            errors.append(name)
    if not artifact_present:
        errors.append("artifact")
    if not message or message.get("engine_ok") is not True or not message.get("canonical_sha256"):
        errors.append("completion")
    elif not str(message.get("job_id", "")).startswith("canary-"):
        errors.append("job")
    return errors
