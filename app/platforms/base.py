"""
base.py — Abstract base class for every platform integration.

Each concrete platform module must subclass BasePlatform and implement
the `post` coroutine.  This keeps the posting service agnostic of
platform-specific details while enforcing a uniform interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from app.schemas import PlatformResult
from app.config import settings


class BasePlatform(ABC):
    """
    Every platform connector inherits from this class.

    Subclasses must override:
        name        — human-readable platform label used in API responses
        post()      — coroutine that calls the external API and returns a PlatformResult
    """

    name: str = "Unknown"

    # Shared async HTTPX client settings; each platform creates its own client
    # inside `post` so connection pools are not shared across platforms.

    @abstractmethod
    async def post(self, message: str) -> PlatformResult:
        """
        Publish *message* to the platform.

        Must never raise an exception — catch all errors and return a
        PlatformResult with status="failed" so other platforms are unaffected.
        """
        ...

    # ── Convenience helpers ───────────────────────────────────────────────────

    @staticmethod
    def now_utc() -> tuple[str, str]:
        """Return current UTC date and time as (date_str, time_str)."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    @staticmethod
    def success_result(
        platform: str,
        posted_url: str | None,
        public_access: bool,
    ) -> PlatformResult:
        """Build a successful PlatformResult from a real API response."""
        date_str, time_str = BasePlatform.now_utc()
        return PlatformResult(
            platform=platform,
            status="success",
            posted_url=posted_url,
            public_access=public_access,
            date=date_str,
            time=time_str,
            error=None,
        )

    @staticmethod
    def failure_result(platform: str, error: str) -> PlatformResult:
        """Build a failed PlatformResult with an error message."""
        date_str, time_str = BasePlatform.now_utc()
        return PlatformResult(
            platform=platform,
            status="failed",
            posted_url=None,
            public_access=None,
            date=date_str,
            time=time_str,
            error=error,
        )

    @staticmethod
    def mock_result(platform: str, note: str = "Mock mode active") -> PlatformResult:
        """
        Return a clearly-labelled mock result when MOCK_MODE=true.
        Never fabricates a real URL — posted_url is always None in mock mode.
        """
        date_str, time_str = BasePlatform.now_utc()
        return PlatformResult(
            platform=platform,
            status="mock",
            posted_url=None,
            public_access=None,
            date=date_str,
            time=time_str,
            error=note,
        )

    def _client(self) -> httpx.AsyncClient:
        """Create a fresh async HTTPX client with the configured timeout."""
        return httpx.AsyncClient(timeout=settings.request_timeout)

