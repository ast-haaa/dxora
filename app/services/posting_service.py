
"""
posting_service.py — Orchestrates concurrent posting across all platforms.

All platform calls run concurrently.
If one platform fails, the others continue independently.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from app.schemas import PlatformResult, PostingResponse
from app.platforms.base import BasePlatform
from app.config import settings

# Import all five platform connectors
from app.platforms.platform_a import BlueskyPlatform
from app.platforms.platform_b import MastodonPlatform
from app.platforms.platform_c import TelegramPlatform
from app.platforms.platform_d import PastebinPlatform
from app.platforms.platform_e import DiscordPlatform


logger = logging.getLogger(__name__)


# Registry of active platform connectors
PLATFORMS: list[BasePlatform] = [
    BlueskyPlatform(),
    MastodonPlatform(),
    TelegramPlatform(),
    PastebinPlatform(),
    DiscordPlatform(),
]


async def publish_to_all(message: str) -> PostingResponse:
    """
    Send message to all registered platforms concurrently.

    Overall success is True if at least one platform succeeds.
    """

    logger.info(
        "Starting concurrent post to %d platforms",
        len(PLATFORMS)
    )

    # Execute all platform calls simultaneously
    raw_results: Sequence[PlatformResult | BaseException] = (
        await asyncio.gather(
            *[platform.post(message) for platform in PLATFORMS],
            return_exceptions=True
        )
    )

    results: list[PlatformResult] = []

    for platform, outcome in zip(PLATFORMS, raw_results):

        if isinstance(outcome, BaseException):

            logger.error(
                "Platform %s raised an unhandled exception: %s",
                platform.name,
                outcome
            )

            result = BasePlatform.failure_result(
                platform.name,
                f"Unhandled exception: {outcome}"
            )

        else:
            result = outcome

            logger.info(
                "Platform %s → %s",
                platform.name,
                result.status
            )

        results.append(result)

    # Calculate overall success
    if settings.mock_mode:
        any_success = any(
            r.status in ("success", "mock")
            for r in results
        )
    else:
        any_success = any(
            r.status == "success"
            for r in results
        )

    return PostingResponse(
        success=any_success,
        results=results
    )
