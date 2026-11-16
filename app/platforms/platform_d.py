"""
platform_d.py — Pastebin integration.

Official API docs: https://pastebin.com/doc_api
Authentication: API developer key + optional user session key

HOW IT WORKS
POST https://pastebin.com/api/api_post.php
  with form fields: api_dev_key, api_option=paste, api_paste_code, etc.

On success Pastebin returns a plain-text URL like:
  https://pastebin.com/AbCd1234

PERMISSIONS REQUIRED
• A Pastebin account (free tier is sufficient)
• API developer key: https://pastebin.com/doc_api#1
• Optional: user session key for posting as a logged-in user (not anonymous)
  — obtained via POST /api/api_login.php

KNOWN LIMITATIONS
• Free Pastebin accounts are limited to 10 pastes/day via the API.
• The paste URL is always public (paste visibility set to "public").
• Rate-limit errors return HTTP 200 with an error string in the body
  (not a proper status code), so we detect them by inspecting the body.
• Pastebin pastes are not social-media posts; they serve as a shareable
  content archive endpoint in this integration.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import PlatformResult
from app.platforms.base import BasePlatform

_PASTE_URL = "https://pastebin.com/api/api_post.php"
_LOGIN_URL = "https://pastebin.com/api/api_login.php"


class PastebinPlatform(BasePlatform):
    name = "Pastebin"

    async def _get_user_key(self, client: httpx.AsyncClient) -> str | None:
        """
        Obtain a user session key.
        Returns None if credentials are absent or the login fails.
        This is optional — anonymous pastes work without it.
        """
        cfg = settings
        if not cfg.pastebin_username or not cfg.pastebin_password:
            return None
        try:
            resp = await client.post(
                _LOGIN_URL,
                data={
                    "api_dev_key": cfg.pastebin_api_key,
                    "api_user_name": cfg.pastebin_username,
                    "api_user_password": cfg.pastebin_password,
                },
            )
            if resp.status_code == 200 and not resp.text.startswith("Bad API request"):
                return resp.text.strip()
        except Exception:
            pass
        return None

    async def post(self, message: str) -> PlatformResult:
        # ── Mock mode ─────────────────────────────────────────────────────────
        if settings.mock_mode:
            return self.mock_result(self.name)

        # ── Credential check ─────────────────────────────────────────────────
        if not settings.pastebin_api_key:
            return self.failure_result(
                self.name,
                "Pastebin credentials not configured. Set PASTEBIN_API_KEY in .env",
            )

        try:
            async with self._client() as client:
                user_key = await self._get_user_key(client)

                payload: dict[str, str] = {
                    "api_dev_key": settings.pastebin_api_key,
                    "api_option": "paste",
                    "api_paste_code": message,
                    "api_paste_name": "Automated Post",
                    "api_paste_expire_date": "1M",   # expires in 1 month
                    "api_paste_private": "0",         # 0=public, 1=unlisted, 2=private
                }
                if user_key:
                    payload["api_user_key"] = user_key

                response = await client.post(_PASTE_URL, data=payload)

                body = response.text.strip()

                # Pastebin always returns HTTP 200 even on errors;
                # error responses begin with "Bad API request"
                if body.startswith("Bad API request"):
                    return self.failure_result(self.name, f"Pastebin error: {body}")

                if not body.startswith("https://pastebin.com/"):
                    return self.failure_result(
                        self.name, f"Unexpected Pastebin response: {body[:200]}"
                    )

                # body IS the URL on success
                posted_url = body
                return self.success_result(
                    self.name, posted_url, public_access=True
                )

        except httpx.TimeoutException:
            return self.failure_result(self.name, "Request timed out")
        except httpx.RequestError as exc:
            return self.failure_result(self.name, f"Network error: {exc}")
        except Exception as exc:
            return self.failure_result(self.name, f"Unexpected error: {exc}")

