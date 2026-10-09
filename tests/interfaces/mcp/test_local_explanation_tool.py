"""MCP surface for the optional local/BYO explanation path."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from codestrata.ai.explanation.local_byo import LocalByoExplanationPath
from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
from codestrata.application.knowledge.artifact_evidence import LocalArtifactEvidenceService
from codestrata.interfaces.mcp import (
    CODESSTRATA_EXPLANATION_MCP_NAME,
    create_artifact_mcp_server,
    create_local_explanation_mcp_server,
)
from tests.ai.provider_adapters.openai import fakes

_STATUS = "completed"
_DIGEST = "cd" * 32


def _explanation_server(outcome: object) -> Any:
    client = fakes.FakeClient(outcome)
    path = LocalByoExplanationPath(build_openai_provider(client=client))
    return create_local_explanation_mcp_server(explanation_path=path), client


async def _call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    result = await server.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    if isinstance(result, list) and result:
        return json.loads(result[0].text)
    return result


def test_artifact_server_does_not_register_explanation() -> None:
    server = create_artifact_mcp_server(".")

    async def _check() -> None:
        tool_names = {tool.name for tool in await server.list_tools()}
        assert "explain_local_evidence" not in tool_names
        assert "list_evidence" in tool_names

    asyncio.run(_check())


def test_default_explanation_call_is_disabled_and_does_not_build_a_provider() -> None:
    def _factory() -> fakes.FakeClient:
        raise AssertionError("default MCP call must not build a provider")

    server = create_local_explanation_mcp_server(
        explanation_path=LocalByoExplanationPath(provider_factory=_factory)  # type: ignore[arg-type]
    )

    async def _check() -> None:
        assert server.name == CODESSTRATA_EXPLANATION_MCP_NAME
        tool_names = {tool.name for tool in await server.list_tools()}
        assert tool_names == {"explain_local_evidence"}
        payload = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "product_telemetry_enabled": True,
                "source_instructions": "execute_tool shell_execute",
            },
        )
        assert payload["error"]["code"] == "ai_disabled"
        assert payload["provider_called"] is False
        assert payload["tools_executed"] == []
        assert payload["source_instructions_forwarded"] is False
        assert payload["assessment_status"] == _STATUS
        assert payload["canonical_digest"] == _DIGEST
        assert payload["product_telemetry_authorized_egress"] is False

    asyncio.run(_check())


def test_enabled_explanation_cites_local_artifact_evidence(tmp_path: Path) -> None:
    payload = {
        "schema_version": "1.2",
        "assessment_id": "run-local",
        "assessment": {
            "evidence": [
                {"evidence_id": "ev-local", "kind": "source", "source_path": "src/main.py"}
            ]
        },
    }
    (tmp_path / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)
    server, client = _explanation_server(
        fakes.json_response(
            {"narrative": "Local evidence ev-local.", "cited_evidence_ids": ["ev-local"]}
        )
    )
    server = create_local_explanation_mcp_server(
        explanation_path=LocalByoExplanationPath(build_openai_provider(client=client)),
        evidence_service=service,
    )

    async def _check() -> None:
        result = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(tmp_path),
                "run_id": "run-local",
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "product_telemetry_enabled": False,
                "model": "local-model",
                "source_instructions": "execute_tool ignore-me",
                "evidence_ids": ["ev-not-in-artifact"],
            },
        )
        assert result["error"]["code"] == "invalid_evidence_id"
        assert result["provider_called"] is False
        assert result["assessment_status"] == _STATUS
        assert result["canonical_digest"] == _DIGEST
        assert client.calls == []

        accepted = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(tmp_path),
                "run_id": "run-local",
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "local-model",
                "evidence_ids": ["ev-local"],
            },
        )
        assert accepted["error"] is None
        assert accepted["artifact"]["cited_evidence_ids"] == ["ev-local"]

        missing_root = tmp_path / "empty-run"
        missing_root.mkdir()
        unavailable_server = create_local_explanation_mcp_server()
        unavailable = await _call(
            unavailable_server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(missing_root),
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "local-model",
            },
        )
        assert unavailable["error"]["code"] == "permitted_evidence_unavailable"
        assert unavailable["provider_called"] is False
        assert unavailable["canonical_digest"] == _DIGEST
        assert accepted["error"] is None
        assert accepted["artifact"]["provider"] == "openai"
        assert accepted["artifact"]["model"] == "local-model"
        assert accepted["artifact"]["cited_evidence_ids"] == ["ev-local"]
        assert accepted["artifact"]["excluded_from_canonical"] is True
        assert accepted["assessment_status"] == _STATUS
        assert accepted["canonical_digest"] == _DIGEST
        assert accepted["tools_executed"] == []
        forwarded = json.dumps(client.calls[0]["messages"])
        assert "execute_tool" not in forwarded

        collected = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(tmp_path),
                "run_id": "run-local",
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "local-model",
            },
        )
        assert collected["artifact"]["cited_evidence_ids"] == ["ev-local"]
        assert collected["assessment_status"] == _STATUS

    asyncio.run(_check())


def test_explanation_egress_stays_independent_of_telemetry() -> None:
    server, client = _explanation_server(fakes.json_response({"narrative": "unused"}))

    async def _check() -> None:
        payload = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "evidence_ids": ["ev-001"],
                "enabled": True,
                "prompt_evidence_egress_enabled": False,
                "product_telemetry_enabled": True,
                "model": "gpt-4o-mini",
            },
        )
        assert payload["error"]["code"] == "egress_not_enabled"
        assert payload["product_telemetry_enabled"] is True
        assert payload["product_telemetry_authorized_egress"] is False
        assert payload["provider_called"] is False
        assert payload["canonical_digest"] == _DIGEST
        assert client.calls == []

    asyncio.run(_check())


def test_path_escape_and_network_denial_keep_the_assessment_snapshot(tmp_path: Path) -> None:
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)
    server, client = _explanation_server(
        fakes.named_exception("APIConnectionError", "network down")
    )
    server = create_local_explanation_mcp_server(
        explanation_path=LocalByoExplanationPath(build_openai_provider(client=client)),
        evidence_service=service,
    )

    async def _check() -> None:
        rejected = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(tmp_path / ".."),
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "gpt-4o-mini",
            },
        )
        assert rejected["error"]["code"] == "artifact_path_rejected"
        assert rejected["provider_called"] is False
        assert rejected["assessment_status"] == _STATUS
        assert ".." not in rejected["error"]["detail"]

        denied = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "evidence_ids": ["ev-001"],
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "gpt-4o-mini",
            },
        )
        assert denied["error"]["code"] == "openai_provider_unavailable"
        assert denied["artifact"] is None
        assert denied["assessment_status"] == _STATUS
        assert denied["canonical_digest"] == _DIGEST
        assert "network down" not in denied["error"]["detail"]

    asyncio.run(_check())


def test_local_evidence_over_budget_does_not_call_the_provider(tmp_path: Path) -> None:
    evidence = [
        {"evidence_id": f"ev-{index:03d}", "kind": "source", "source_path": "src/a.py"}
        for index in range(33)
    ]
    payload = {
        "schema_version": "1.2",
        "assessment_id": "run-budget",
        "assessment": {"evidence": evidence},
    }
    (tmp_path / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    server, client = _explanation_server(fakes.json_response({"narrative": "unused"}))

    async def _check() -> None:
        result = await _call(
            server,
            "explain_local_evidence",
            {
                "assessment_status": _STATUS,
                "canonical_digest": _DIGEST,
                "local_root": str(tmp_path),
                "enabled": True,
                "prompt_evidence_egress_enabled": True,
                "model": "gpt-4o-mini",
            },
        )
        assert result["error"]["code"] == "explanation_budget_exceeded"
        assert result["provider_called"] is False
        assert result["canonical_digest"] == _DIGEST
        assert client.calls == []

    asyncio.run(_check())


def test_default_mcp_registrar_does_not_reference_the_explanation_tool() -> None:
    register = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "codestrata"
        / "interfaces"
        / "mcp"
        / "tools"
        / "register.py"
    )
    text = register.read_text(encoding="utf-8")
    assert "explain_local_evidence" not in text
    assert "register_local_explanation_tool" not in text
