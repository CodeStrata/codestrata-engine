"""SV.11.7 AWS Bedrock Provider Migration verification (Epic 11, Slice 11.7).

Verifies that ``codestrata.ai.provider_adapters.bedrock`` implements the
``AIProvider`` contract, that ``BedrockAIModelProvider`` is now a
compatibility wrapper over it plus ``AIProviderExecutor``, and that
everything observable from ``codestrata assess`` is unchanged — including the
default provider (bedrock), the ``[ai.bedrock]``/``[aws]`` config keys, the
``amazon.nova-lite-v1:0`` default, the AWS credential/profile/region
precedence, the Converse wire shape, the prompt bytes, assessment report
schema 1.2, and the raise-based fail-soft path.

With Slice 11.6's OpenAI migration, both providers now run on the contracts;
this suite also proves that Slice 11.7 did not regress the OpenAI side.

No real AWS call, credential, instance metadata lookup, STS call, network
access, or wall-clock wait occurs anywhere: every execution goes through an
injected in-memory client.
"""

from __future__ import annotations

__all__: list[str] = []
