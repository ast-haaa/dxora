from app.config import settings
from app.schemas import PostingRequest, PostingResponse
from app.platforms.base import BasePlatform
from app.platforms.platform_a import RedditPlatform
from app.platforms.platform_b import MastodonPlatform
from app.platforms.platform_c import TelegramPlatform
from app.platforms.platform_d import PastebinPlatform
from app.platforms.platform_e import HashnodePlatform
from app.services.posting_service import publish_to_all
from app.main import app

print("ALL IMPORTS OK")
print(f"Mock mode: {settings.mock_mode}")
print(f"Platforms registered: {5}")

