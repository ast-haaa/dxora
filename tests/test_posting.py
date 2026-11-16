"""
test_posting.py — Comprehensive test suite for the posting system.

Run with:
    .venv\\Scripts\\pytest tests/ -v

All tests use mocks — no real API calls are made.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas import PostingRequest, PlatformResult


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_message() -> str:
    return "Check out our latest business platform. https://example.com"


@pytest.fixture
def mock_success_result():
    """Factory for a successful PlatformResult."""
    def _make(platform: str) -> PlatformResult:
        return PlatformResult(
            platform=platform,
            status="success",
            posted_url=f"https://{platform.lower()}.example.com/post/123",
            public_access=True,
            date="2026-11-15",
            time="10:30:00",
            error=None,
        )
    return _make


@pytest.fixture
def mock_failure_result():
    """Factory for a failed PlatformResult."""
    def _make(platform: str, error: str = "auth failed") -> PlatformResult:
        return PlatformResult(
            platform=platform,
            status="failed",
            posted_url=None,
            public_access=None,
            date="2026-11-15",
            time="10:30:00",
            error=error,
        )
    return _make


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INPUT VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputValidation:
    """Test all validation rules on the PostingRequest schema."""

    def test_valid_message_accepted(self, valid_message):
        req = PostingRequest(message=valid_message)
        assert req.message == valid_message

    def test_message_exceeds_200_characters_rejected(self):
        long_msg = "A" * 170 + " https://example.com " + "B" * 20
        with pytest.raises(Exception) as exc_info:
            PostingRequest(message=long_msg)
        assert "200" in str(exc_info.value)

    def test_message_exactly_200_characters_accepted(self):
        # Build a 200-char message with exactly one URL
        url = "https://example.com"
        padding = "X" * (200 - len(url) - 1)
        msg = padding + " " + url
        assert len(msg) == 200
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_message_201_characters_rejected(self):
        url = "https://example.com"
        padding = "X" * (201 - len(url) - 1)
        msg = padding + " " + url
        assert len(msg) == 201
        with pytest.raises(Exception) as exc_info:
            PostingRequest(message=msg)
        assert "200" in str(exc_info.value)

    def test_message_no_url_rejected(self):
        with pytest.raises(Exception) as exc_info:
            PostingRequest(message="Hello world no link here")
        assert "none found" in str(exc_info.value).lower() or \
               "cta" in str(exc_info.value).lower() or \
               "link" in str(exc_info.value).lower()

    def test_message_multiple_urls_rejected(self):
        msg = "Visit https://example.com and also https://another.com"
        with pytest.raises(Exception) as exc_info:
            PostingRequest(message=msg)
        assert "2" in str(exc_info.value)

    def test_message_blank_rejected(self):
        with pytest.raises(Exception):
            PostingRequest(message="   ")

    def test_message_empty_string_rejected(self):
        with pytest.raises(Exception):
            PostingRequest(message="")

    def test_invalid_url_scheme_rejected(self):
        """URLs without http/https should not be counted as valid CTA links."""
        msg = "Visit ftp://example.com for more info"
        with pytest.raises(Exception):
            PostingRequest(message=msg)

    def test_http_url_accepted(self):
        req = PostingRequest(message="Check this out http://example.com today")
        assert req.message is not None

    def test_https_url_accepted(self):
        req = PostingRequest(message="Check this out https://example.com today")
        assert req.message is not None

    def test_url_query_parameters_accepted(self):
        msg = "Check our platform https://example.com/app?utm_source=twitter&ref=abc123"
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_url_fragment_accepted(self):
        msg = "Read the documentation https://example.com/guide#section-2"
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_url_port_accepted(self):
        msg = "Connect to our API at https://example.com:8443/v1/health"
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_url_trailing_punctuation_stripped(self):
        msg = "Visit our site https://example.com/deal."
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_url_in_parentheses_accepted(self):
        msg = "Our business site (https://example.com/growth) is now live!"
        req = PostingRequest(message=msg)
        assert req.message == msg

    def test_malformed_hostname_rejected(self):
        with pytest.raises(Exception):
            PostingRequest(message="Check out https://.. for details")
        with pytest.raises(Exception):
            PostingRequest(message="Check out https://-badhost-.com")

    def test_invalid_scheme_rejected(self):
        with pytest.raises(Exception) as exc_info:
            PostingRequest(message="Download our files from ftp://files.example.com/pkg")
        assert "scheme" in str(exc_info.value).lower() or "ftp" in str(exc_info.value).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. API ENDPOINT TESTS (via HTTPX AsyncClient + ASGI transport)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestPostingEndpoint:
    """
    Integration tests that call the FastAPI endpoint through HTTPX.
    The publish_to_all service is mocked to avoid real network calls.
    """

    async def test_valid_request_returns_200(self, valid_message):
        mock_response = {
            "success": True,
            "results": [
                {
                    "platform": "Reddit",
                    "status": "success",
                    "posted_url": "https://reddit.com/r/test/abc",
                    "public_access": True,
                    "date": "2026-11-15",
                    "time": "10:30:00",
                    "error": None,
                }
            ],
        }
        from app.schemas import PostingResponse, PlatformResult
        mocked = PostingResponse(
            success=True,
            results=[PlatformResult(**mock_response["results"][0])],
        )

        with patch(
            "app.main.publish_to_all", new=AsyncMock(return_value=mocked)
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/posting", json={"message": valid_message})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["results"]) == 1

    async def test_message_too_long_returns_422(self):
        long_msg = "A" * 170 + " https://example.com " + "B" * 20
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/posting", json={"message": long_msg})
        assert response.status_code == 422

    async def test_no_url_returns_422(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/posting", json={"message": "No link here"})
        assert response.status_code == 422

    async def test_multiple_urls_returns_422(self):
        msg = "Visit https://example.com and also https://another.com"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/posting", json={"message": msg})
        assert response.status_code == 422

    async def test_missing_message_field_returns_422(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/posting", json={})
        assert response.status_code == 422

    async def test_health_check_returns_ok(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PLATFORM-LEVEL UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestPlatformUnits:
    """
    Unit-test each platform connector in isolation using mocked HTTPX responses.
    """

    # ── Reddit ────────────────────────────────────────────────────────────────

    async def test_reddit_missing_credentials_returns_failure(self):
        from app.platforms.platform_a import RedditPlatform
        platform = RedditPlatform()

        # Temporarily clear credentials
        with patch("app.platforms.platform_a.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.reddit_client_id = ""
            mock_cfg.reddit_client_secret = ""
            mock_cfg.reddit_username = ""
            mock_cfg.reddit_password = ""
            result = await platform.post("test https://example.com")

        assert result.status == "failed"
        assert "not configured" in result.error.lower()

    async def test_reddit_mock_mode_returns_mock(self):
        from app.platforms.platform_a import RedditPlatform
        platform = RedditPlatform()

        with patch("app.platforms.platform_a.settings") as mock_cfg:
            mock_cfg.mock_mode = True
            result = await platform.post("test https://example.com")

        assert result.status == "mock"
        assert result.platform == "Reddit"

    async def test_reddit_auth_failure_returns_failed(self):
        from app.platforms.platform_a import RedditPlatform
        platform = RedditPlatform()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("app.platforms.platform_a.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.reddit_client_id = "fake_id"
            mock_cfg.reddit_client_secret = "fake_secret"
            mock_cfg.reddit_username = "fake_user"
            mock_cfg.reddit_password = "fake_pass"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "failed"

    async def test_reddit_success(self):
        from app.platforms.platform_a import RedditPlatform
        platform = RedditPlatform()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "mock_reddit_token"}

        mock_submit_resp = MagicMock()
        mock_submit_resp.status_code = 200
        mock_submit_resp.json.return_value = {
            "json": {
                "errors": [],
                "data": {
                    "id": "abc123xyz",
                    "permalink": "/r/test/comments/abc123xyz/automated_post/",
                    "url": "https://www.reddit.com/r/test/comments/abc123xyz/automated_post/",
                },
            }
        }

        with patch("app.platforms.platform_a.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.reddit_client_id = "fake_id"
            mock_cfg.reddit_client_secret = "fake_secret"
            mock_cfg.reddit_username = "fake_user"
            mock_cfg.reddit_password = "fake_pass"
            mock_cfg.reddit_subreddit = "test"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(
                    side_effect=[mock_token_resp, mock_submit_resp]
                )
                MockClient.return_value = mock_instance

                # Pass a message with newlines to verify title sanitization
                msg_with_newlines = "Title line 1\nTitle line 2\nhttps://example.com"
                result = await platform.post(msg_with_newlines)

        assert result.status == "success"
        assert result.posted_url == "https://www.reddit.com/r/test/comments/abc123xyz/automated_post/"
        assert result.public_access is True
        # Verify submit call used sanitized title without newlines
        submit_call_data = mock_instance.post.call_args_list[1][1]["data"]
        assert "\n" not in submit_call_data["title"]
        assert submit_call_data["text"] == msg_with_newlines

    # ── Mastodon ──────────────────────────────────────────────────────────────

    async def test_mastodon_missing_credentials_returns_failure(self):
        from app.platforms.platform_b import MastodonPlatform
        platform = MastodonPlatform()

        with patch("app.platforms.platform_b.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.mastodon_access_token = ""
            result = await platform.post("test https://example.com")

        assert result.status == "failed"

    async def test_mastodon_mock_mode_returns_mock(self):
        from app.platforms.platform_b import MastodonPlatform
        platform = MastodonPlatform()

        with patch("app.platforms.platform_b.settings") as mock_cfg:
            mock_cfg.mock_mode = True
            result = await platform.post("test https://example.com")

        assert result.status == "mock"

    async def test_mastodon_success(self):
        from app.platforms.platform_b import MastodonPlatform
        platform = MastodonPlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "url": "https://mastodon.social/@user/123456",
            "visibility": "public",
        }

        with patch("app.platforms.platform_b.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.mastodon_access_token = "fake_token"
            mock_cfg.mastodon_instance_url = "https://mastodon.social"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "success"
        assert result.posted_url == "https://mastodon.social/@user/123456"
        assert result.public_access is True

    # ── Telegram ──────────────────────────────────────────────────────────────

    async def test_telegram_missing_credentials_returns_failure(self):
        from app.platforms.platform_c import TelegramPlatform
        platform = TelegramPlatform()

        with patch("app.platforms.platform_c.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.telegram_bot_token = ""
            mock_cfg.telegram_chat_id = ""
            result = await platform.post("test https://example.com")

        assert result.status == "failed"

    async def test_telegram_success_public_channel(self):
        from app.platforms.platform_c import TelegramPlatform
        platform = TelegramPlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 42},
        }

        with patch("app.platforms.platform_c.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.telegram_bot_token = "fake_token"
            mock_cfg.telegram_chat_id = "@mychannel"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "success"
        assert result.posted_url == "https://t.me/mychannel/42"
        assert result.public_access is True

    async def test_telegram_numeric_chat_id_with_public_username(self):
        from app.platforms.platform_c import TelegramPlatform
        platform = TelegramPlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "message_id": 99,
                "chat": {
                    "id": -1001234567890,
                    "username": "public_channel_name",
                    "type": "channel",
                },
            },
        }

        with patch("app.platforms.platform_c.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.telegram_bot_token = "fake_token"
            mock_cfg.telegram_chat_id = "-1001234567890"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "success"
        assert result.posted_url == "https://t.me/public_channel_name/99"
        assert result.public_access is True

    # ── Pastebin ──────────────────────────────────────────────────────────────

    async def test_pastebin_missing_credentials_returns_failure(self):
        from app.platforms.platform_d import PastebinPlatform
        platform = PastebinPlatform()

        with patch("app.platforms.platform_d.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.pastebin_api_key = ""
            result = await platform.post("test https://example.com")

        assert result.status == "failed"

    async def test_pastebin_success(self):
        from app.platforms.platform_d import PastebinPlatform
        platform = PastebinPlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "https://pastebin.com/AbCd1234"

        with patch("app.platforms.platform_d.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.pastebin_api_key = "fake_key"
            mock_cfg.pastebin_username = ""
            mock_cfg.pastebin_password = ""
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "success"
        assert result.posted_url == "https://pastebin.com/AbCd1234"

    # ── Hashnode ──────────────────────────────────────────────────────────────

    async def test_hashnode_missing_credentials_returns_failure(self):
        from app.platforms.platform_e import HashnodePlatform
        platform = HashnodePlatform()

        with patch("app.platforms.platform_e.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.hashnode_token = ""
            mock_cfg.hashnode_publication_id = ""
            result = await platform.post("test https://example.com")

        assert result.status == "failed"

    async def test_hashnode_graphql_error_returns_failure(self):
        from app.platforms.platform_e import HashnodePlatform
        platform = HashnodePlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Publication not found"}]
        }

        with patch("app.platforms.platform_e.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.hashnode_token = "fake_token"
            mock_cfg.hashnode_publication_id = "fake_pub_id"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("test https://example.com")

        assert result.status == "failed"
        assert "publication not found" in result.error.lower()

    async def test_hashnode_success(self):
        from app.platforms.platform_e import HashnodePlatform
        platform = HashnodePlatform()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishPost": {
                    "post": {
                        "id": "hash123",
                        "url": "https://blog.hashnode.dev/automated-post-test",
                        "slug": "automated-post-test",
                    }
                }
            }
        }

        with patch("app.platforms.platform_e.settings") as mock_cfg:
            mock_cfg.mock_mode = False
            mock_cfg.hashnode_token = "raw_pat_token_without_bearer"
            mock_cfg.hashnode_publication_id = "pub123"
            mock_cfg.request_timeout = 10

            with patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value = mock_instance

                result = await platform.post("Testing Hashnode publication https://example.com")

        assert result.status == "success"
        assert result.posted_url == "https://blog.hashnode.dev/automated-post-test"
        assert result.public_access is True
        # Verify Bearer token was prepended to raw token
        post_headers = mock_instance.post.call_args[1]["headers"]
        assert post_headers["Authorization"] == "Bearer raw_pat_token_without_bearer"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SERVICE-LEVEL TESTS (one platform fails, others succeed)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestPostingService:
    """Test the orchestration layer in posting_service.py."""

    async def test_one_failure_does_not_cancel_others(self):
        """
        Simulate Reddit failing while all other platforms succeed.
        The response must still contain results for every platform.
        """
        from app.services.posting_service import publish_to_all, PLATFORMS

        # Build side-effects: first platform fails, rest succeed
        side_effects = []
        for i, p in enumerate(PLATFORMS):
            if i == 0:
                side_effects.append(
                    PlatformResult(
                        platform=p.name,
                        status="failed",
                        posted_url=None,
                        public_access=None,
                        date="2026-11-15",
                        time="10:00:00",
                        error="auth failed",
                    )
                )
            else:
                side_effects.append(
                    PlatformResult(
                        platform=p.name,
                        status="success",
                        posted_url=f"https://{p.name.lower()}.example.com/1",
                        public_access=True,
                        date="2026-11-15",
                        time="10:00:00",
                        error=None,
                    )
                )

        async def mock_post(msg):
            return side_effects[PLATFORMS.index(self._current_platform)]

        mocks = [AsyncMock(return_value=r) for r in side_effects]

        with patch.object(PLATFORMS[0], "post", mocks[0]), \
             patch.object(PLATFORMS[1], "post", mocks[1]), \
             patch.object(PLATFORMS[2], "post", mocks[2]), \
             patch.object(PLATFORMS[3], "post", mocks[3]), \
             patch.object(PLATFORMS[4], "post", mocks[4]):

            response = await publish_to_all(
                "Check out https://example.com for details"
            )

        assert len(response.results) == len(PLATFORMS)
        statuses = [r.status for r in response.results]
        assert "failed" in statuses
        assert "success" in statuses
        # Overall success because at least one succeeded
        assert response.success is True

    async def test_all_platforms_fail_success_is_false(self):
        """When every platform fails, success must be False."""
        from app.services.posting_service import publish_to_all, PLATFORMS

        failure = PlatformResult(
            platform="X",
            status="failed",
            posted_url=None,
            public_access=None,
            date="2026-11-15",
            time="10:00:00",
            error="network error",
        )

        mocks = [AsyncMock(return_value=failure) for _ in PLATFORMS]
        patches = {
            p: patch.object(p_obj, "post", m)
            for p_obj, m in zip(PLATFORMS, mocks)
            for p in [p_obj]
        }

        with patch.object(PLATFORMS[0], "post", mocks[0]), \
             patch.object(PLATFORMS[1], "post", mocks[1]), \
             patch.object(PLATFORMS[2], "post", mocks[2]), \
             patch.object(PLATFORMS[3], "post", mocks[3]), \
             patch.object(PLATFORMS[4], "post", mocks[4]):

            response = await publish_to_all(
                "Check out https://example.com for details"
            )

        assert response.success is False
        assert all(r.status == "failed" for r in response.results)

    async def test_mock_mode_overall_success(self):
        """When mock mode is enabled, overall success must be True and statuses must be 'mock'."""
        from app.services.posting_service import publish_to_all
        from app.config import settings

        with patch.object(settings, "mock_mode", True):
            response = await publish_to_all("Test mock post https://example.com")

        assert response.success is True
        assert len(response.results) == 5
        assert all(r.status == "mock" for r in response.results)
        assert all(r.posted_url is None for r in response.results)
