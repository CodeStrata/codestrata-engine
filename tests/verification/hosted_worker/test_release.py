"""Hosted worker release decisions. No image is built and no AWS call is made."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification.hosted_worker.release import (
    QUALIFIED_IMAGE,
    QUALIFIED_WHEEL,
    canary_errors,
    confirmed_digest,
    decide,
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
    assert "aws_access_key" not in text.lower()
    assert "AKIA" not in text
    publisher = PUBLISHER.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in publisher
    assert "\n  push:" not in publisher
    assert "engine-package-published" in publisher
    assert "ENGINE_WORKER_DISPATCH_TOKEN" in publisher
    workflows = list((ENGINE / ".github" / "workflows").glob("*.yml"))
    assert [path.name for path in workflows] == ["hosted-worker-release.yml"]
