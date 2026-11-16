
"""
platform_e.py — Discord Webhook integration.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import PlatformResult
from app.platforms.base import BasePlatform


class DiscordPlatform(BasePlatform):
    name = "Discord"

    async def post(self, message: str) -> PlatformResult:

        if settings.mock_mode:
            return self.mock_result(self.name)

        cfg = settings

        if not cfg.discord_webhook_url:
            return self.failure_result(
                self.name,
                "Discord webhook URL not configured."
            )

        try:
            async with self._client() as client:

                # Step 1: Get webhook details
                webhook_response = await client.get(
                    cfg.discord_webhook_url
                )

                if webhook_response.status_code != 200:
                    return self.failure_result(
                        self.name,
                        f"Discord webhook check failed: "
                        f"HTTP {webhook_response.status_code}"
                    )

                webhook_data = webhook_response.json()

                guild_id = webhook_data.get("guild_id")
                channel_id = webhook_data.get("channel_id")

                # Step 2: Send the message
                response = await client.post(
                    cfg.discord_webhook_url,
                    params={"wait": "true"},
                    json={
                        "content": message,
                        "allowed_mentions": {"parse": []}
                    }
                )

                if response.status_code != 200:
                    return self.failure_result(
                        self.name,
                        f"Discord posting failed: "
                        f"HTTP {response.status_code} — "
                        f"{response.text[:200]}"
                    )

                data = response.json()

                message_id = data.get("id")
                channel_id = data.get("channel_id") or channel_id
                guild_id = data.get("guild_id") or guild_id

                if not message_id or not channel_id:
                    return self.failure_result(
                        self.name,
                        "Discord message was created but its "
                        "message or channel ID was missing."
                    )

                posted_url = None

                if guild_id:
                    posted_url = (
                        f"https://discord.com/channels/"
                        f"{guild_id}/{channel_id}/{message_id}"
                    )

                return self.success_result(
                    self.name,
                    posted_url,
                    public_access=False
                )

        except httpx.TimeoutException:
            return self.failure_result(
                self.name, "Discord request timed out"
            )

        except httpx.RequestError as exc:
            return self.failure_result(
                self.name, f"Discord network error: {exc}"
            )

        except Exception as exc:
            return self.failure_result(
                self.name, f"Unexpected Discord error: {exc}"
            )
