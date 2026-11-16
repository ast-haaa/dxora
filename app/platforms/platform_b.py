"""
platform_b.py — Mastodon integration.

Official API docs: https://docs.joinmastodon.org/methods/statuses/
Authentication: User access token (OAuth2 scope: write:statuses)

HOW IT WORKS
POST {instance_url}/api/v1/statuses
  with Authorization: Bearer <access_token>
  and status=<message text>

The endpoint returns the newly created status object, which contains
the `url` field — the actual public URL of the toot.

PERMISSIONS REQUIRED
• A Mastodon account on any public instance (default: mastodon.social)
• An "Application" created in Preferences → Development
• Access token with the "write:statuses" scope

KNOWN LIMITATIONS
• Maximum toot length is typically 500 characters (instance-specific).
  Our validator already caps at 200 chars so this is never an issue.
• mastodon.social has anti-spam measures; brand-new apps may be throttled.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import PlatformResult
from app.platforms.base import BasePlatform


class MastodonPlatform(BasePlatform):
    name = "Mastodon"

    async def post(self, message: str) -> PlatformResult:
        # ── Mock mode ─────────────────────────────────────────────────────────
        if settings.mock_mode:
            return self.mock_result(self.name)

        # ── Credential check ─────────────────────────────────────────────────
        cfg = settings
        if not cfg.mastodon_access_token:
            return self.failure_result(
                self.name,
                "Mastodon credentials not configured. Set MASTODON_ACCESS_TOKEN "
                "and MASTODON_INSTANCE_URL in .env",
            )

        status_url = f"{cfg.mastodon_instance_url.rstrip('/')}/api/v1/statuses"

        try:
            async with self._client() as client:
                response = await client.post(
                    status_url,
                    json={"status": message},
                    headers={
                        "Authorization": f"Bearer {cfg.mastodon_access_token}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 401:
                    return self.failure_result(
                        self.name,
                        "Mastodon auth failed: invalid or expired access token",
                    )

                if response.status_code == 422:
                    return self.failure_result(
                        self.name,
                        f"Mastodon validation error: {response.text[:200]}",
                    )

                if response.status_code not in (200, 201):
                    return self.failure_result(
                        self.name,
                        f"Mastodon API error: HTTP {response.status_code} — "
                        f"{response.text[:200]}",
                    )

                data = response.json()
                # `url` in the response is the canonical public URL of the toot
                posted_url = data.get("url")
                # Mastodon statuses are public unless visibility is set otherwise
                visibility = data.get("visibility", "public")
                public_access = visibility == "public"

                return self.success_result(
                    self.name, posted_url, public_access=public_access
                )

        except httpx.TimeoutException:
            return self.failure_result(self.name, "Request timed out")
        except httpx.RequestError as exc:
            return self.failure_result(self.name, f"Network error: {exc}")
        except Exception as exc:
            return self.failure_result(self.name, f"Unexpected error: {exc}")

