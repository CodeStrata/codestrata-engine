"""The OpenRouter OpenAI-compatible adapter (Epic 11, Slice 11.9).

Unwired from ``codestrata assess``. No AssessAIProviderRegistry registration,
no TOML schema, no environment credential resolution, and no doctor/CLI work
in this slice. Construction tests inject a mocked client.

Importing this package never constructs a client, never imports the ``openai``
SDK, and never reads ``os.environ``.
"""

from __future__ import annotations

__all__: list[str] = []
