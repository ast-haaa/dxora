
"""
config.py — Application configuration using pydantic-settings.

All secrets are loaded from environment variables or .env.
No credentials are hardcoded.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    # ── Mastodon ─────────────────────────────────────────
    mastodon_instance_url: str = Field(
        default="https://mastodon.social",
        alias="MASTODON_INSTANCE_URL"
    )
    mastodon_access_token: str = Field(
        default="",
        alias="MASTODON_ACCESS_TOKEN"
    )

    # ── Telegram ─────────────────────────────────────────
    telegram_bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_chat_id: str = Field(
        default="",
        alias="TELEGRAM_CHAT_ID"
    )

    # ── Pastebin ─────────────────────────────────────────
    pastebin_api_key: str = Field(
        default="",
        alias="PASTEBIN_API_KEY"
    )
    pastebin_username: str = Field(
        default="",
        alias="PASTEBIN_USERNAME"
    )
    pastebin_password: str = Field(
        default="",
        alias="PASTEBIN_PASSWORD"
    )

    # ── Discord ──────────────────────────────────────────
    discord_webhook_url: str = Field(
        default="",
        alias="DISCORD_WEBHOOK_URL"
    )

    # ── Bluesky ──────────────────────────────────────────
    bluesky_handle: str = Field(
        default="",
        alias="BLUESKY_HANDLE"
    )
    bluesky_app_password: str = Field(
        default="",
        alias="BLUESKY_APP_PASSWORD"
    )

    # ── Global behaviour ─────────────────────────────────
    mock_mode: bool = Field(
        default=False,
        alias="MOCK_MODE"
    )

    request_timeout: int = Field(
        default=15,
        alias="REQUEST_TIMEOUT"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }


settings = Settings()
