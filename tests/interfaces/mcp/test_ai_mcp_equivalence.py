"""E12.3: artifact MCP returns the pinned canonical evidence without an AI provider."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from codestrata.application.knowledge.artifact_evidence import LocalArtifactEvidenceService
from codestrata.interfaces.mcp import create_artifact_mcp_server

_FIXTURES = Path(__file__).resolve().parents[2] / "ai" / "explanation" / "fixtures" / "e12.3"


def _load(name: str) -> dict[str, object]:
    loaded = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{name} must be an object")
    return loaded


async def _call(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    result = await server.call_tool(name, arguments)
    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    if isinstance(result, list) and result:
        return json.loads(result[0].text)
    return result


def test_artifact_mcp_matches_canonical_evidence_without_a_provider(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("artifact MCP must not construct an AI provider")

    monkeypatch.setattr(
        "codestrata.ai.provider_adapters.openai.factory.build_openai_provider",
        _boom,
    )
    report = _load("pinned-report.json")
    expected = _load("expected-canonical.json")
    (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "explanation.json").write_text(
        json.dumps(
            {
                "schema_version": "codestrata-local-byo-explanation:1.0.0",
                "health_score": 100,
                "severity": "low",
                "narrative": "unsupported sidecar claim",
            }
        ),
        encoding="utf-8",
    )

    service = LocalArtifactEvidenceService(allowed_root=tmp_path)
    server = create_artifact_mcp_server(tmp_path, evidence_service=service)

    async def _check() -> tuple[dict[str, Any], dict[str, Any]]:
        tool_names = {tool.name for tool in await server.list_tools()}
        assert "explain_local_evidence" not in tool_names
        assert "list_findings" in tool_names
        assert "list_metrics" in tool_names

        findings = await _call(server, "list_findings", {"local_root": str(tmp_path)})
        metrics = await _call(server, "list_metrics", {"local_root": str(tmp_path)})
        if not isinstance(findings, dict) or not isinstance(metrics, dict):
            raise AssertionError("MCP findings and metrics must be objects")
        return findings, metrics

    findings, metrics = asyncio.run(_check())
    finding_rows = findings["items"]
    metric_rows = metrics["items"]

    assert [(item["finding_id"], item["severity"]) for item in finding_rows] == [
        (item["finding_id"], item["severity"]) for item in expected["findings"]
    ]
    assert [(item["metric_id"], item["value"], item["coverage"]) for item in metric_rows] == [
        (item["metric_id"], item["value"], item["coverage"]) for item in expected["metrics"]
    ]
    assert all(item["metric_id"] != "health_score" for item in metric_rows)
    assert all(item["value"] != 100 for item in metric_rows)

    view = service.canonical_equivalence_view(tmp_path)
    assert view["findings"] == expected["findings"]
    assert view["metrics"] == expected["metrics"]
    assert view["coverage"] == expected["coverage"]
    assert view["verdicts"] == expected["verdicts"]
    assert view["coverage"][0]["coverage_ratio"] is None
    assert view["verdicts"][0]["verdict"] == "deteriorated"
    assert view["findings"][0]["severity"] == "high"
