"""Optional Commercial Platform integration for the Community Engine.

Engine depends only on ``PlatformClient``. No ``codestrata_platform`` imports.
"""

from __future__ import annotations

from codestrata.integration.commercial.client import (
    MockPlatformClient,
    OfflinePlatformClient,
    PlatformClient,
    RestPlatformClient,
)
from codestrata.integration.commercial.configuration import (
    PlatformClientConfig,
    platform_client_from_settings,
)
from codestrata.integration.commercial.publisher import (
    PlatformPublishResult,
    publish_assessment_to_platform,
)

__all__ = [
    "MockPlatformClient",
    "OfflinePlatformClient",
    "PlatformClient",
    "PlatformClientConfig",
    "PlatformPublishResult",
    "RestPlatformClient",
    "platform_client_from_settings",
    "publish_assessment_to_platform",
]
