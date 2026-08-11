"""Concrete AI provider adapters built on ``codestrata.ai.provider_contracts``.

CodeStrata v0.2.0 Epic 11, Slice 11.6 — OpenAI Provider Migration.

Unlike ``codestrata.ai.provider_contracts`` (Slices 11.2-11.5), which is a
deliberately unwired, SDK-free foundation, this package hosts **wired**
adapters: real SDK integrations that implement the
:class:`~codestrata.ai.provider_contracts.provider.AIProvider` protocol and
are reached by ``codestrata assess --with-ai``.

## Mixed-mode provider architecture

Only OpenAI is migrated by Slice 11.6. Bedrock deliberately stays on the
legacy ``codestrata.ai.providers.bedrock`` path, untouched. Both providers
continue to be selected through the same registry
(``codestrata.extensions.assess_ai``) and continue to expose the same legacy
``codestrata.ai.providers.base.AIModelProvider`` interface to
``codestrata.ai.enrichment.service.AiEnrichmentService``:

| Provider | Wire path | Contract path |
| --- | --- | --- |
| ``bedrock`` (default) | ``ai/providers/bedrock.py`` | none (legacy) |
| ``openai`` | ``ai/provider_adapters/openai/`` | ``AIProvider`` + executor |

Both providers are still selected through the same ``AssessAIProviderRegistry``.

``codestrata.ai.providers.openai_provider.OpenAIAIModelProvider`` remains the
public assess-path class and keeps its constructor signature; internally it
is now a thin compatibility wrapper that builds this package's adapter, runs
it through ``AIProviderExecutor``, and translates the resulting
``AIProviderResult`` back into the legacy ``ModelInvocationResult`` /
legacy raise-based exceptions the enrichment fail-soft path expects.

## Dependency boundary

Modules in this package may import ``codestrata.ai.provider_contracts``, the
``openai`` SDK (lazily, inside a function), the stdlib,
``codestrata.ai.providers`` legacy contract types (for the compatibility
bridge only), and ``codestrata.config.settings`` types. They must never
import ``codestrata.platform``, ``codestrata.datalake``,
``codestrata.telemetry``, ``codestrata.analytics``, ``codestrata.reporting``,
or ``codestrata.cli``.

See [`engine/docs/ai-provider-openai.md`](../../../docs/ai-provider-openai.md)
for the full design writeup.
"""

from __future__ import annotations

__all__: list[str] = []
