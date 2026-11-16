
"""
platform_a.py — Bluesky integration.

Authentication: Bluesky App Password
SDK: atproto

HOW IT WORKS
1. Login using Bluesky handle and app password.
2. Publish the message using the Bluesky API.
3. Return the public post URL.
"""

from __future__ import annotations

import asyncio

from atproto import Client

from app.config import settings
from app.schemas import PlatformResult
from app.platforms.base import BasePlatform


class BlueskyPlatform(BasePlatform):
    name = "Bluesky"

    async def post(self, message: str) -> PlatformResult:

        # Mock mode
        if settings.mock_mode:
            return self.mock_result(self.name)

        cfg = settings

        # Check credentials
        if not cfg.bluesky_handle or not cfg.bluesky_app_password:
            return self.failure_result(
                self.name,
                "Bluesky credentials not configured. "
                "Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD in .env"
            )

        try:
            # Run synchronous SDK calls in a separate thread
            def publish():
                client = Client()

                # Login
                client.login(
                    cfg.bluesky_handle,
                    cfg.bluesky_app_password
                )

                # Publish post
                response = client.send_post(message)

                return response.uri

            post_uri = await asyncio.to_thread(publish)

            # Extract post ID from AT Protocol URI
            post_id = post_uri.split("/")[-1]

            # Construct public post URL
            posted_url = (
                f"https://bsky.app/profile/"
                f"{cfg.bluesky_handle}/post/{post_id}"
            )

            return self.success_result(
                self.name,
                posted_url,
                public_access=True
            )

        except Exception as exc:
            return self.failure_result(
                self.name,
                f"Bluesky posting failed: {exc}"
            )
