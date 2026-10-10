"""Hosted worker release decisions. No image is built and no AWS call is made."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from verification.hosted_worker.release import (
    CANARY_COMPLETION_QUEUE,
    PRODUCTION_COMPLETION_QUEUE,
    QUALIFIED_IMAGE,
    QUALIFIED_WHEEL,
    canary_container_overrides,
    canary_errors,
    confirmed_digest,
    decide,
    guarded_drill,
    guarded_release,
    isolated_canary_job,
    listed_versions,
    provenance_record,
    restored_dispatch,
    revise_task_definition,
    select_wheel_file,
    with_task_definition,
)

ENGINE = Path(__file__).resolve().parents[3]
WORKFLOW = ENGINE / ".github" / "workflows" / "hosted-worker-release.yml"
PUBLISHER = ENGINE.parents[0] / ".github" / "workflows" / "engine-pypi-release.yml"


def _decide(**overrides: object) -> dict[str, str]:
    payload = {
        "event": "schedule",
        "requested_version": "",
        "requested_sha256": "",
        "deployed_version": "0.3.0",
        "deployed_image": QUALIFIED_IMAGE,
        "rollout_enabled": True,
        "pypi_versions": ["0.3.0"],
        "pypi_sha256": QUALIFIED_WHEEL,
    }
    payload.update(overrides)
    return decide(**payload)  # type: ignore[arg-type]


def test_published_030_is_retained_and_not_rebuilt() -> None:
    decision = _decide(event="workflow_dispatch", requested_version="0.3.0", requested_sha256=QUALIFIED_WHEEL)
    assert decision["action"] == "retain"
    assert decision["image"] == QUALIFIED_IMAGE
    assert "docker build" not in (ENGINE / "verification" / "hosted_worker" / "workflow.py").read_text().split("def retain_image", 1)[1].split("def build_image", 1)[0]


def test_prerelease_downgrade_and_repeat_do_not_deploy() -> None:
    assert _decide(event="workflow_dispatch", requested_version="0.4.0rc1", requested_sha256="a" * 64)["reason"] == "prerelease"
    assert _decide(event="workflow_dispatch", requested_version="0.3.0", requested_sha256=QUALIFIED_WHEEL, deployed_version="0.4.0")["reason"] == "downgrade"
    assert _decide(event="workflow_dispatch", requested_version="0.4.0", requested_sha256="b" * 64, deployed_version="0.4.0")["action"] == "skip"
    observed = _decide(pypi_versions=["0.4.0", "0.4.0a1"], pypi_sha256="b" * 64, rollout_enabled=False, deployed_version="0.3.0")
    assert observed["action"] == "observe"
    assert observed["version"] == "0.4.0"


def test_schedule_selects_the_newest_stable_version() -> None:
    document = {"releases": {"0.3.0": [{"yanked": False}], "0.9.0rc1": [{"yanked": False}], "0.2.1": [{"yanked": True}]}}
    assert listed_versions(document) == ["0.3.0", "0.9.0rc1"]
    decision = _decide(pypi_versions=listed_versions(document), pypi_sha256=QUALIFIED_WHEEL, deployed_version="0.3.0")
    assert decision["action"] == "retain"
    assert decision["version"] == "0.3.0"
    released = _decide(pypi_versions=["0.3.0", "0.4.0", "0.4.0b1"], pypi_sha256="c" * 64, deployed_version="0.3.0")
    assert released == {"action": "release", "reason": "stable-upgrade", "version": "0.4.0", "wheel_sha256": "c" * 64}


def test_trigger_digest_must_match_the_package_index() -> None:
    assert confirmed_digest("", "ab" * 32) == "ab" * 32
    with pytest.raises(ValueError, match="package index"):
        confirmed_digest("cd" * 32, "ab" * 32)


def test_wheel_selection_accepts_only_the_package_index() -> None:
    selected = select_wheel_file(
        [
            {
                "packagetype": "bdist_wheel",
                "filename": "codestrata-0.4.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/ab/codestrata-0.4.0-py3-none-any.whl",
                "digests": {"sha256": "d" * 64},
            }
        ]
    )
    assert selected["digests"]["sha256"] == "d" * 64
    with pytest.raises(ValueError):
        select_wheel_file(
            [
                {
                    "packagetype": "bdist_wheel",
                    "filename": "codestrata-0.4.0-py3-none-any.whl",
                    "url": "https://example.test/codestrata.whl",
                    "digests": {"sha256": "d" * 64},
                }
            ]
        )


def test_unverified_source_commit_is_not_provenance() -> None:
    with pytest.raises(ValueError, match="unverified"):
        provenance_record(
            version="0.4.0",
            wheel_sha256="d" * 64,
            image=QUALIFIED_IMAGE.replace("ed95672fbcd1e6708ee179f9858577e652180781587499c2d1f9836ed08e6b44", "d" * 64),
            build_identity={"run_id": "1"},
            source_commit="abc",
            source_verified=False,
        )
    record = provenance_record(
        version="0.4.0",
        wheel_sha256="d" * 64,
        image=QUALIFIED_IMAGE.replace("ed95672fbcd1e6708ee179f9858577e652180781587499c2d1f9836ed08e6b44", "d" * 64),
        build_identity={"run_id": "1"},
    )
    assert record["source_identity"] is None
    assert record["wheel_sha256"] == "d" * 64


def _task() -> dict:
    mount = [
        {"sourceVolume": "tmp", "containerPath": "/tmp", "readOnly": False},
        {"sourceVolume": "workspace", "containerPath": "/workspace", "readOnly": False},
    ]
    return {
        "family": "codestrata-launch-worker",
        "revision": 3,
        "taskDefinitionArn": "arn:aws:ecs:us-west-2:373220260833:task-definition/codestrata-launch-worker:3",
        "containerDefinitions": [
            {"name": "setup", "image": "wrapper", "readonlyRootFilesystem": True, "mountPoints": mount},
            {
                "name": "engine",
                "image": QUALIFIED_IMAGE,
                "user": "10001:10001",
                "readonlyRootFilesystem": True,
                "environment": [{"name": "HOME", "value": "/tmp"}],
                "mountPoints": mount,
            },
            {"name": "cleanup", "image": "wrapper", "readonlyRootFilesystem": True, "mountPoints": mount},
        ],
    }


def test_revision_changes_only_the_engine_digest_and_version_metadata() -> None:
    image = QUALIFIED_IMAGE.replace("ed95672fbcd1e6708ee179f9858577e652180781587499c2d1f9836ed08e6b44", "e" * 64)
    revised = revise_task_definition(_task(), image=image, version="0.4.0", wheel_sha256="e" * 64)
    assert "revision" not in revised
    containers = {item["name"]: item for item in revised["containerDefinitions"]}
    assert containers["engine"]["image"] == image
    assert containers["engine"]["user"] == "10001:10001"
    assert containers["setup"]["image"] == "wrapper"
    assert containers["cleanup"]["image"] == "wrapper"
    names = {item["name"] for item in containers["engine"]["environment"]}
    assert names == {"HOME", "CODESTRATA_ENGINE_VERSION", "CODESTRATA_ENGINE_WHEEL_SHA256"}
    poisoned = _task()
    poisoned["containerDefinitions"][1]["linuxParameters"] = {"tmpfs": [{"containerPath": "/tmp"}]}
    with pytest.raises(ValueError, match="Fargate"):
        revise_task_definition(poisoned, image=image, version="0.4.0", wheel_sha256="e" * 64)


def test_dispatcher_update_and_rollback_keep_the_previous_revision() -> None:
    previous = "arn:aws:ecs:us-west-2:373220260833:task-definition/codestrata-launch-worker:3"
    failed = "arn:aws:ecs:us-west-2:373220260833:task-definition/codestrata-launch-worker:4"
    environment = {"CODESTRATA_HOSTED_TASK_DEFINITION": previous, "CODESTRATA_HOSTED_ECS_CLUSTER": "codestrata-launch-trial"}
    updated = with_task_definition(environment, failed)
    assert updated["CODESTRATA_HOSTED_ECS_CLUSTER"] == "codestrata-launch-trial"
    assert updated["CODESTRATA_HOSTED_TASK_DEFINITION"] == failed
    assert restored_dispatch(previous, failed) == previous
    with pytest.raises(ValueError):
        restored_dispatch("unset", failed)


def test_canary_requires_artifacts_and_completion() -> None:
    task = {
        "lastStatus": "STOPPED",
        "containers": [
            {"name": "setup", "exitCode": 0},
            {"name": "engine", "exitCode": 0},
            {"name": "cleanup", "exitCode": 0},
        ],
    }
    assert canary_errors(task=task, message={"job_id": "canary-7", "engine_ok": True, "canonical_sha256": "a" * 64}, artifact_present=True) == []
    assert "completion" in canary_errors(task=task, message=None, artifact_present=True)
    assert "engine" in canary_errors(
        task={"lastStatus": "STOPPED", "containers": [{"name": "engine", "exitCode": 1}]},
        message={"job_id": "canary-7", "engine_ok": True, "canonical_sha256": "a" * 64},
        artifact_present=True,
    )


def test_workflow_is_not_a_source_push_and_keeps_roles_separate() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "repository_dispatch:" in text
    assert "engine-package-published" in text
    assert "schedule:" in text
    assert "\n  push:" not in text
    assert "codestrata-launch-github-foundation" not in text
    assert "codestrata-launch-engine-image-push" in text
    assert "codestrata-launch-engine-deploy" in text
    assert "cancel-in-progress: false" in text
    assert "python -m verification.hosted_worker.workflow decide" in text
    assert "python -m verification.hosted_worker.workflow retain" in text
    assert "python -m verification.hosted_worker.workflow build" in text
    assert "python -m verification.hosted_worker.workflow deploy" in text
    assert "python -m verification.hosted_worker.workflow drill" in text
    assert "CODESTRATA_HOSTED_DRILL" in text
    assert "codestrata-launch-engine-deploy" in text.split("verify-deploy-role", 1)[1]
    assert "aws_access_key" not in text.lower()
    assert "AKIA" not in text
    publisher = PUBLISHER.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in publisher
    assert "\n  push:" not in publisher
    assert "engine-package-published" in publisher
    assert "ENGINE_WORKER_DISPATCH_TOKEN" in publisher
    workflows = list((ENGINE / ".github" / "workflows").glob("*.yml"))
    assert [path.name for path in workflows] == ["hosted-worker-release.yml"]


def test_actions_module_command_reaches_every_entrypoint(tmp_path: Path) -> None:
    shutil.copytree(ENGINE / "verification", tmp_path / "verification", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    aws = tmp_path / "bin"
    aws.mkdir()
    executable = aws / "aws"
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    executable.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "AWS_PROFILE",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_DEFAULT_PROFILE",
            "CODESTRATA_HOSTED_DRILL",
        }
    }
    env["PATH"] = f"{aws}{os.pathsep}{env.get('PATH', '')}"
    env["AWS_REGION"] = "us-west-2"
    command = [sys.executable, "-m", "verification.hosted_worker.workflow"]
    markers = {
        "decide": "decide_release",
        "retain": "retain_image",
        "build": "build_image",
        "deploy": "deploy_release",
        "drill": "explicit verification mode",
    }
    for name, marker in markers.items():
        completed = subprocess.run(
            [*command, name],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode != 0
        assert "No module named 'verification'" not in completed.stderr
        assert marker in completed.stderr
    assert "working-directory:" not in WORKFLOW.read_text(encoding="utf-8")


def test_failed_canary_does_not_change_production_dispatch() -> None:
    calls: list[str] = []
    production = {"dispatcher": "arn:old", "rollout": "enabled"}

    def fail_canary(_revision: str) -> None:
        calls.append("canary")
        raise RuntimeError("canary failed")

    with pytest.raises(RuntimeError, match="canary failed"):
        guarded_release(
            rollout_enabled=True,
            production=lambda: production,
            register=lambda: calls.append("register") or "arn:new",
            canary=fail_canary,
            promote=lambda _revision: calls.append("promote"),
            verify_promotion=lambda _revision: calls.append("verify"),
            restore=lambda _snapshot: calls.append("restore"),
        )
    assert calls == ["register", "canary"]
    with pytest.raises(RuntimeError, match="production rollout is disabled"):
        guarded_release(
            rollout_enabled=False,
            production=lambda: production,
            register=lambda: calls.append("register-blocked") or "arn:new",
            canary=fail_canary,
            promote=lambda _revision: calls.append("promote"),
            verify_promotion=lambda _revision: None,
            restore=lambda _snapshot: calls.append("restore"),
        )
    assert "register-blocked" not in calls


def test_failed_promotion_restores_the_recorded_snapshot() -> None:
    snapshot = {"dispatcher": "arn:old", "rollout": "enabled"}
    seen: list[dict[str, str]] = []

    def verify(_revision: str) -> None:
        raise RuntimeError("promotion mismatch")

    with pytest.raises(RuntimeError, match="promotion mismatch"):
        guarded_release(
            rollout_enabled=True,
            production=lambda: snapshot,
            register=lambda: "arn:new",
            canary=lambda _revision: None,
            promote=lambda _revision: None,
            verify_promotion=verify,
            restore=lambda recorded: seen.append(dict(recorded)),
        )
    assert seen == [snapshot]


def test_drill_promotes_only_the_qualified_image_and_restores_it() -> None:
    snapshot = {"dispatcher": "arn:old", "rollout": "disabled"}
    restored: list[dict[str, str]] = []
    promoted: list[str] = []

    revision = guarded_drill(
        explicit=True,
        image=QUALIFIED_IMAGE,
        qualified_image=QUALIFIED_IMAGE,
        production=lambda: snapshot,
        register=lambda: "arn:new",
        canary=lambda _revision: None,
        promote=lambda registered: promoted.append(registered),
        verify_promotion=lambda _revision: None,
        restore=lambda recorded: restored.append(dict(recorded)),
    )
    assert revision == "arn:new"
    assert promoted == ["arn:new"]
    assert restored == [snapshot]
    with pytest.raises(RuntimeError, match="explicit verification mode"):
        guarded_drill(
            explicit=False,
            image=QUALIFIED_IMAGE,
            qualified_image=QUALIFIED_IMAGE,
            production=lambda: snapshot,
            register=lambda: "arn:other",
            canary=lambda _revision: None,
            promote=lambda _revision: None,
            verify_promotion=lambda _revision: None,
            restore=lambda _recorded: None,
        )
    with pytest.raises(RuntimeError, match="production rollout is enabled"):
        guarded_drill(
            explicit=True,
            image=QUALIFIED_IMAGE,
            qualified_image=QUALIFIED_IMAGE,
            production=lambda: {"dispatcher": "arn:old", "rollout": "enabled"},
            register=lambda: "arn:other",
            canary=lambda _revision: None,
            promote=lambda _revision: None,
            verify_promotion=lambda _revision: None,
            restore=lambda _recorded: None,
        )


def test_canary_completion_cannot_use_the_production_queue() -> None:
    job_id = isolated_canary_job("run-7")
    overrides = canary_container_overrides(job_id)
    rendered = str(overrides)
    assert CANARY_COMPLETION_QUEUE in rendered
    assert PRODUCTION_COMPLETION_QUEUE not in rendered
    assert "codestrata-launch-delivery" not in rendered
    with pytest.raises(ValueError):
        canary_container_overrides("storage-smoke")
