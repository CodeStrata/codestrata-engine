"""SV.11.6 OpenAI Provider Migration verification (Epic 11, Slice 11.6).

Verifies that ``codestrata.ai.provider_adapters.openai`` implements the
``AIProvider`` contract, that ``OpenAIAIModelProvider`` is now a compatibility
wrapper over it plus ``AIProviderExecutor``, and that everything observable
from ``codestrata assess`` is unchanged — including the default provider
(bedrock), the OpenAI config keys, the ``gpt-4o-mini`` default, the prompt
bytes, assessment report schema 1.2, and the raise-based fail-soft path.

Bedrock stays on the legacy path; this suite proves that too. No real network
access, credentials, or waiting is involved anywhere.
"""

from __future__ import annotations

__all__: list[str] = []
