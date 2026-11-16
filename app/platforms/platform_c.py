"""
platform_c.py — Telegram integration.

Official Bot API docs: https://core.telegram.org/bots/api#sendmessage
Authentication: Bot token (issued by @BotFather on Telegram)

HOW IT WORKS
POST https://api.telegram.org/bot{TOKEN}/sendMessage
  with chat_id and text

The Bot API returns the full Message object on success, including
message_id. We construct the deep-link URL using that ID.

PERMISSIONS REQUIRED
1. Create a bot via @BotFather → get the token
2. Add the bot to a channel or group as administrator WITH permission to post
3. Obtain the chat_id of the channel/group
   • For public channels: use @channelname (e.g. "@mychannel")
   • For private chats/groups: forward a message to @userinfobot

KNOWN LIMITATIONS
• Deep-link message URLs only work for public channels; private chat URLs
  require the user to be a member.
• Telegram does not expose a canonical "post URL" for private chats —
  we return None in that case.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import PlatformResult
from app.platforms.base import BasePlatform

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramPlatform(BasePlatform):
    name = "Telegram"

    async def post(self, message: str) -> PlatformResult:
        # ── Mock mode ─────────────────────────────────────────────────────────
        if settings.mock_mode:
            return self.mock_result(self.name)

        # ── Credential check ─────────────────────────────────────────────────
        cfg = settings
        if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
            return self.failure_result(
                self.name,
                "Telegram credentials not configured. Set TELEGRAM_BOT_TOKEN "
                "and TELEGRAM_CHAT_ID in .env",
            )

        api_url = _API_BASE.format(token=cfg.telegram_bot_token)
        chat_id = cfg.telegram_chat_id

        try:
            async with self._client() as client:
                response = await client.post(
                    api_url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        # parse_mode left unset so raw text is preserved exactly
                    },
                )

                if response.status_code == 401:
                    return self.failure_result(
                        self.name, "Telegram auth failed: invalid bot token"
                    )

                if response.status_code == 400:
                    err = response.json().get("description", response.text[:200])
                    return self.failure_result(
                        self.name, f"Telegram bad request: {err}"
                    )

                if response.status_code != 200:
                    return self.failure_result(
                        self.name,
                        f"Telegram API error: HTTP {response.status_code} — "
                        f"{response.text[:200]}",
                    )

                data = response.json()
                if not data.get("ok"):
                    return self.failure_result(
                        self.name,
                        f"Telegram returned ok=false: {data.get('description')}",
                    )

                result = data.get("result", {})
                message_id = result.get("message_id")
                chat_info = result.get("chat", {})

                # Inspect chat username from official Telegram response
                # Supports public channels whether configured by @username or numeric chat ID
                chat_username = chat_info.get("username")
                if not chat_username and isinstance(chat_id, str) and chat_id.startswith("@"):
                    chat_username = chat_id.lstrip("@")

                if chat_username and message_id:
                    posted_url = f"https://t.me/{chat_username}/{message_id}"
                    public_access = True
                else:
                    # Private group, direct chat, or channel without public username — no public URL
                    posted_url = None
                    public_access = False

                return self.success_result(
                    self.name, posted_url, public_access=public_access
                )

        except httpx.TimeoutException:
            return self.failure_result(self.name, "Request timed out")
        except httpx.RequestError as exc:
            return self.failure_result(self.name, f"Network error: {exc}")
        except Exception as exc:
            return self.failure_result(self.name, f"Unexpected error: {exc}")

