"""The OpenAI Chat Completions adapter (Epic 11, Slice 11.6).

| Module | Contents |
| --- | --- |
| ``capabilities.py`` | Re-exposes the static ``OPENAI_CAPABILITY_PROFILE`` |
| ``configuration.py`` | Settings -> ``OpenAIAdapterConfiguration`` + client inputs |
| ``client.py`` | Lazy client construction at the one credential boundary |
| ``request_mapping.py`` | ``AIProviderRequest`` -> Chat Completions kwargs |
| ``response_mapping.py`` | SDK response -> ``AIProviderResult`` |
| ``usage_mapping.py`` | SDK usage -> ``ProviderUsageMetadata`` |
| ``error_mapping.py`` | SDK exceptions -> ``ErrorCategory``/``AIProviderError`` |
| ``diagnostics.py`` | Redacted diagnostic views |
| ``adapter.py`` | ``OpenAIProvider`` — the ``AIProvider`` implementation |
| ``factory.py`` | Construction without any import-time client or env read |
| ``legacy_bridge.py`` | Legacy ``AIModelProvider`` <-> contract translation |

Importing this package never constructs an OpenAI client, never imports the
``openai`` SDK, and never reads ``os.environ``.
"""

from __future__ import annotations

__all__: list[str] = []
