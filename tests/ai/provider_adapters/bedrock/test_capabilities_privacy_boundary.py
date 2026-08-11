"""Capabilities, privacy, and dependency-boundary smoke tests."""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.ai.provider_adapters.bedrock.capabilities import bedrock_capability_profile
from codestrata.ai.provider_adapters.bedrock.diagnostics import diagnostic_view_of_adapter
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.identifiers import ProviderId
from tests.ai.provider_adapters.bedrock import fakes


def test_capability_profile_matches_slice_11_5_bedrock_baseline() -> None:
    profile = bedrock_capability_profile()
    assert profile.provider_id is ProviderId.BEDROCK
    assert profile.supports_structured_json is False
    assert profile.supports_streaming is False
    assert profile.reports_usage_metadata is True


def test_diagnostics_omit_profile_region_and_prompts() -> None:
    adapter = build_bedrock_provider(client=fakes.Client())
    view = diagnostic_view_of_adapter(adapter)
    rendered = str(view)
    assert "AKIA" not in rendered
    assert "us-east-1" not in rendered
    assert "Synthetic instruction" not in rendered
    assert "profile_configured" in view


def test_only_client_module_imports_boto_or_aws_config_for_sdk() -> None:
    package = Path(__file__).resolve().parents[4] / "src/codestrata/ai/provider_adapters/bedrock"
    offenders: list[str] = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name in {"boto3", "botocore"} or name.startswith("botocore."):
                    if path.name != "client.py":
                        offenders.append(f"{path.name}:{name}")
                if name.startswith("codestrata.ai.aws_config") and path.name not in {
                    "client.py",
                    "legacy_bridge.py",
                }:
                    offenders.append(f"{path.name}:{name}")
    assert offenders == []
