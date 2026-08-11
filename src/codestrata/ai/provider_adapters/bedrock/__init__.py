"""The AWS Bedrock Converse adapter (Epic 11, Slice 11.7).

| Module | Contents |
| --- | --- |
| ``capabilities.py`` | Re-exposes the static ``BEDROCK_CAPABILITY_PROFILE`` |
| ``configuration.py`` | Settings -> ``BedrockAdapterConfiguration`` + client inputs |
| ``client.py`` | Lazy client construction at the one AWS boundary |
| ``request_mapping.py`` | ``AIProviderRequest`` -> Converse kwargs |
| ``response_mapping.py`` | Converse response -> ``AIProviderResult`` |
| ``usage_mapping.py`` | Converse usage -> ``ProviderUsageMetadata`` |
| ``error_mapping.py`` | AWS SDK exceptions -> ``ErrorCategory``/``AIProviderError`` |
| ``diagnostics.py`` | Redacted diagnostic views |
| ``adapter.py`` | ``BedrockProvider`` — the ``AIProvider`` implementation |
| ``factory.py`` | Construction without any import-time client or AWS call |
| ``legacy_bridge.py`` | Legacy ``AIModelProvider`` <-> contract translation |

Importing this package never constructs a Bedrock Runtime client, never
imports ``boto3``/``botocore``, never reads ``os.environ``, and never touches
the AWS credential chain, the instance metadata service, or STS.
"""

from __future__ import annotations

__all__: list[str] = []
