"""GitHub Actions entrypoint for the hosted Engine worker release.

AWS commands use the role assumed by the job. This file does not read or write
long-lived credentials.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import ssl
from pathlib import Path

from verification.hosted_worker.qualify import qualification_script
from verification.hosted_worker.release import (
    ACCOUNT,
    QUALIFIED_IMAGE,
    REGION,
    REPOSITORY,
    WHEEL_HOST,
    canary_errors,
    confirmed_digest,
    decide,
    download_wheel,
    engine_image_uri,
    listed_versions,
    provenance_record,
    restored_dispatch,
    revise_task_definition,
    select_wheel_file,
    with_task_definition,
)

PARAMETER_VERSION = "/codestrata/launch/hosted/engine-release-version"
PARAMETER_WHEEL = "/codestrata/launch/hosted/engine-wheel-sha256"
PARAMETER_IMAGE = "/codestrata/launch/hosted/engine-image-uri"
PARAMETER_TASK = "/codestrata/launch/hosted/engine-task-definition-arn"
PARAMETER_VERSION_PREVIOUS = "/codestrata/launch/hosted/engine-release-version-previous"
PARAMETER_WHEEL_PREVIOUS = "/codestrata/launch/hosted/engine-wheel-sha256-previous"
PARAMETER_IMAGE_PREVIOUS = "/codestrata/launch/hosted/engine-image-uri-previous"
PARAMETER_TASK_PREVIOUS = "/codestrata/launch/hosted/engine-task-definition-arn-previous"
PARAMETER_ROLLOUT = "/codestrata/launch/hosted/worker-rollout"
CANARY_QUEUE_URL = (
    "https://sqs.us-west-2.amazonaws.com/373220260833/codestrata-launch-worker-canary"
)
REPORT_BUCKET = "codestrata-launch-report-artifacts-373220260833"
DISPATCHER = "codestrata-launch-dispatcher"
CLUSTER = "codestrata-launch-trial"


def _aws(*args: str) -> str:
    completed = subprocess.run(
        ["aws", *args, "--region", REGION, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _parameter(name: str) -> str:
    try:
        payload = json.loads(_aws("ssm", "get-parameter", "--name", name))
    except subprocess.CalledProcessError as exc:
        if "ParameterNotFound" not in (exc.stderr or ""):
            raise
        return "unset"
    return str(payload["Parameter"]["Value"])


def _put_parameter(name: str, value: str) -> None:
    _aws("ssm", "put-parameter", "--name", name, "--type", "String", "--overwrite", "--value", value)


def _pypi(version: str = "") -> dict:
    url = "https://pypi.org/pypi/codestrata/json" if not version else f"https://pypi.org/pypi/codestrata/{version}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "codestrata-hosted-worker"})
    with urllib.request.urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
        if not response.geturl().startswith("https://pypi.org/"):
            raise ValueError("package index redirect is not PyPI")
        return json.loads(response.read().decode("utf-8"))


def _output(**values: str) -> None:
    path = Path(os.environ["GITHUB_OUTPUT"])
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def decide_release() -> None:
    event = os.environ["EVENT_NAME"]
    if event == "workflow_dispatch":
        requested_version = os.environ["INPUT_VERSION"]
        requested_sha = os.environ["INPUT_SHA"]
    elif event == "repository_dispatch":
        requested_version = os.environ["DISPATCH_VERSION"]
        requested_sha = os.environ["DISPATCH_SHA"]
    else:
        requested_version = ""
        requested_sha = ""
    document = _pypi()
    versions = listed_versions(document)
    if event == "schedule":
        preview = decide(
            event=event,
            requested_version="",
            requested_sha256="",
            deployed_version="unset",
            deployed_image="",
            rollout_enabled=False,
            pypi_versions=versions,
            pypi_sha256="0" * 64,
        )
        version = str(preview["version"])
        requested_sha = ""
    else:
        version = requested_version
    files = _pypi(version).get("urls") or []
    selected = select_wheel_file(files)
    digest = confirmed_digest(requested_sha, str(selected["digests"]["sha256"]))
    if not str(selected["url"]).startswith(WHEEL_HOST):
        raise ValueError("wheel URL is not the package file host")
    decision = decide(
        event=event,
        requested_version=version,
        requested_sha256=digest,
        deployed_version=_parameter(PARAMETER_VERSION),
        deployed_image=_parameter(PARAMETER_IMAGE),
        rollout_enabled=_parameter(PARAMETER_ROLLOUT) == "enabled",
        pypi_versions=versions,
        pypi_sha256=digest,
    )
    _output(
        action=decision["action"],
        version=decision.get("version", version),
        wheel_sha256=decision.get("wheel_sha256", digest),
        image=decision.get("image", ""),
    )
    print(json.dumps(decision, sort_keys=True))
    if decision["action"] == "reject":
        raise SystemExit(1)


def retain_image() -> None:
    expected = os.environ["EXPECTED_IMAGE"]
    if expected != QUALIFIED_IMAGE:
        raise SystemExit("retain only applies to the qualified 0.3.0 image")
    digest = expected.rsplit("sha256:", 1)[1]
    described = json.loads(
        _aws(
            "ecr",
            "describe-images",
            "--repository-name",
            REPOSITORY,
            "--image-ids",
            f"imageDigest=sha256:{digest}",
        )
    )
    details = described.get("imageDetails") or []
    if not details or details[0].get("imageDigest") != f"sha256:{digest}":
        raise SystemExit("qualified Engine image is not in the registry")
    print("retained", expected)


def build_image() -> None:
    version = os.environ["RELEASE_VERSION"]
    expected = os.environ["RELEASE_SHA"]
    if version == "0.3.0":
        raise SystemExit("the published 0.3.0 image is not rebuilt")
    selected = select_wheel_file(_pypi(version).get("urls") or [])
    digest = confirmed_digest(expected, str(selected["digests"]["sha256"]))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        wheel = root / str(selected["filename"])
        download_wheel(str(selected["url"]), wheel, digest)
        context = root / "context"
        context.mkdir()
        wheel.replace(context / wheel.name)
        dockerfile = Path("examples/hosted-worker/Dockerfile")
        (context / "Dockerfile").write_text(dockerfile.read_text(encoding="utf-8"), encoding="utf-8")
        script = root / "qualify.py"
        script.write_text(qualification_script(), encoding="utf-8")
        script.chmod(0o644)
        subprocess.run(
            ["docker", "build", "--platform", "linux/arm64", "-t", "codestrata-engine-candidate", str(context)],
            check=True,
        )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--read-only",
                "--user",
                "10001:10001",
                "--mount",
                "type=tmpfs,destination=/tmp",
                "--env",
                f"CODESTRATA_EXPECTED_VERSION={version}",
                "--entrypoint",
                "python",
                "codestrata-engine-candidate",
                "-c",
                script.read_text(encoding="utf-8"),
            ],
            check=True,
        )
    account_uri = engine_image_uri("0" * 64).split("@", 1)[0]
    tag = f"{account_uri}:{version}"
    subprocess.run(["docker", "tag", "codestrata-engine-candidate", tag], check=True)
    password = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", REGION],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", f"{account_uri.split('/')[0]}"],
        input=password,
        text=True,
        check=True,
    )
    subprocess.run(["docker", "push", tag], check=True)
    described = json.loads(
        _aws("ecr", "describe-images", "--repository-name", REPOSITORY, "--image-ids", f"imageTag={version}")
    )
    image_digest = str(described["imageDetails"][0]["imageDigest"])
    image = engine_image_uri(image_digest.removeprefix("sha256:"))
    record = provenance_record(
        version=version,
        wheel_sha256=digest,
        image=image,
        build_identity={
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        },
    )
    Path("provenance.json").write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    _output(image=image, wheel_sha256=digest, version=version)


def _lambda_environment() -> dict[str, str]:
    payload = json.loads(_aws("lambda", "get-function-configuration", "--function-name", DISPATCHER))
    return dict(payload.get("Environment", {}).get("Variables") or {})


def _publish_release(image: str, version: str, wheel: str, task_arn: str, previous: dict[str, str]) -> None:
    _put_parameter(PARAMETER_IMAGE_PREVIOUS, previous["image"])
    _put_parameter(PARAMETER_TASK_PREVIOUS, previous["task"])
    _put_parameter(PARAMETER_VERSION_PREVIOUS, previous["version"])
    _put_parameter(PARAMETER_WHEEL_PREVIOUS, previous["wheel"])
    _put_parameter(PARAMETER_IMAGE, image)
    _put_parameter(PARAMETER_TASK, task_arn)
    _put_parameter(PARAMETER_VERSION, version)
    _put_parameter(PARAMETER_WHEEL, wheel)


def _restore(previous: dict[str, str], failed_arn: str) -> None:
    environment = with_task_definition(_lambda_environment(), restored_dispatch(previous["task"], failed_arn))
    _aws(
        "lambda",
        "update-function-configuration",
        "--function-name",
        DISPATCHER,
        "--environment",
        json.dumps({"Variables": environment}),
    )
    _put_parameter(PARAMETER_IMAGE, previous["image"])
    _put_parameter(PARAMETER_TASK, previous["task"])
    _put_parameter(PARAMETER_VERSION, previous["version"])
    _put_parameter(PARAMETER_WHEEL, previous["wheel"])


def deploy_release() -> None:
    if _parameter(PARAMETER_ROLLOUT) != "enabled":
        raise SystemExit("production rollout is disabled")
    image = os.environ["RELEASE_IMAGE"]
    version = os.environ["RELEASE_VERSION"]
    wheel = os.environ["RELEASE_SHA"]
    environment = _lambda_environment()
    previous = {
        "task": environment.get("CODESTRATA_HOSTED_TASK_DEFINITION", ""),
        "image": _parameter(PARAMETER_IMAGE),
        "version": _parameter(PARAMETER_VERSION),
        "wheel": _parameter(PARAMETER_WHEEL),
    }
    if not previous["task"].startswith(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/codestrata-launch-worker:"):
        raise SystemExit("dispatcher has no task definition; the runtime deployment is not complete")
    current = json.loads(
        _aws("ecs", "describe-task-definition", "--task-definition", previous["task"])
    )["taskDefinition"]
    revised = revise_task_definition(current, image=image, version=version, wheel_sha256=wheel)
    registered = json.loads(
        _aws("ecs", "register-task-definition", "--cli-input-json", json.dumps(revised))
    )["taskDefinition"]["taskDefinitionArn"]
    updated = with_task_definition(environment, registered)
    _aws(
        "lambda",
        "update-function-configuration",
        "--function-name",
        DISPATCHER,
        "--environment",
        json.dumps({"Variables": updated}),
    )
    _publish_release(image, version, wheel, registered, previous)
    job_id = f"canary-{os.environ['GITHUB_RUN_ID']}"
    try:
        _run_canary(registered, environment, job_id)
    except SystemExit:
        _restore(previous, registered)
        raise
    print("deployed", registered)


def _run_canary(task_arn: str, environment: dict[str, str], job_id: str) -> None:
    overrides = {
        "containerOverrides": [
            {
                "name": "setup",
                "environment": [
                    {"name": "CODESTRATA_JOB_ID", "value": job_id},
                    {"name": "CODESTRATA_ATTEMPT", "value": "1"},
                    {"name": "CODESTRATA_REPO_URL", "value": "https://github.com/octocat/Hello-World.git"},
                ],
            },
            {
                "name": "engine",
                "environment": [
                    {"name": "CODESTRATA_JOB_ID", "value": job_id},
                    {"name": "CODESTRATA_ATTEMPT", "value": "1"},
                    {"name": "CODESTRATA_REPO_URL", "value": "https://github.com/octocat/Hello-World.git"},
                ],
            },
            {
                "name": "cleanup",
                "environment": [
                    {"name": "CODESTRATA_JOB_ID", "value": job_id},
                    {"name": "CODESTRATA_ATTEMPT", "value": "1"},
                    {"name": "CODESTRATA_HOSTED_COMPLETION_QUEUE_URL", "value": CANARY_QUEUE_URL},
                ],
            },
        ]
    }
    started = json.loads(
        _aws(
            "ecs",
            "run-task",
            "--cluster",
            environment.get("CODESTRATA_HOSTED_ECS_CLUSTER", CLUSTER),
            "--task-definition",
            task_arn,
            "--launch-type",
            "FARGATE",
            "--client-token",
            job_id,
            "--network-configuration",
            json.dumps(
                {
                    "awsvpcConfiguration": {
                        "subnets": [environment["CODESTRATA_HOSTED_SUBNET_ID"]],
                        "securityGroups": [environment["CODESTRATA_HOSTED_SECURITY_GROUP_ID"]],
                        "assignPublicIp": "ENABLED",
                    }
                }
            ),
            "--overrides",
            json.dumps(overrides),
            "--tags",
            "key=codestrata-canary,value=true",
        )
    )
    tasks = started.get("tasks") or []
    if started.get("failures") or not tasks:
        raise SystemExit("canary did not start")
    task_id = str(tasks[0]["taskArn"])
    described = {}
    for _ in range(48):
        described = json.loads(
            _aws("ecs", "describe-tasks", "--cluster", CLUSTER, "--tasks", task_id)
        )["tasks"][0]
        if described.get("lastStatus") == "STOPPED":
            break
        subprocess.run(["sleep", "15"], check=True)
    else:
        _aws("ecs", "stop-task", "--cluster", CLUSTER, "--task", task_id, "--reason", "canary-bound")
        raise SystemExit("canary exceeded its bound")
    key = f"staging/{job_id}/attempt-1/canonical-report.json"
    artifact = subprocess.run(
        ["aws", "s3api", "head-object", "--bucket", REPORT_BUCKET, "--key", key, "--region", REGION],
        check=False,
    )
    message = None
    received = json.loads(
        _aws(
            "sqs",
            "receive-message",
            "--queue-url",
            CANARY_QUEUE_URL,
            "--max-number-of-messages",
            "1",
            "--wait-time-seconds",
            "10",
        )
    )
    messages = received.get("Messages") or []
    if messages:
        message = json.loads(messages[0]["Body"])
        if str(message.get("job_id")) == job_id:
            _aws(
                "sqs",
                "delete-message",
                "--queue-url",
                CANARY_QUEUE_URL,
                "--receipt-handle",
                messages[0]["ReceiptHandle"],
            )
    errors = canary_errors(task=described, message=message, artifact_present=artifact.returncode == 0)
    if errors:
        raise SystemExit("canary failed: " + ",".join(errors))


def main() -> None:
    command = sys.argv[1]
    if command == "decide":
        decide_release()
    elif command == "retain":
        retain_image()
    elif command == "build":
        build_image()
    elif command == "deploy":
        deploy_release()
    else:
        raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
