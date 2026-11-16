"""
main.py — FastAPI application entry point.

Start the server with:
    uvicorn app.main:app --host 0.0.0.0 --port 4000

Swagger UI:  http://localhost:4000/docs
ReDoc:       http://localhost:4000/redoc
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas import PostingRequest, PostingResponse
from app.services.posting_service import publish_to_all

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Application lifecycle ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Automated Multi-Platform Posting System starting up …")
    yield
    logger.info("Shutting down …")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Automated Multi-Platform Posting System",
    description=(
        "A REST API that accepts a message and publishes it concurrently "
        "across five third-party platforms: Reddit, Mastodon, Telegram, "
        "Pastebin, and Hashnode.\n\n"
        "Set `MOCK_MODE=true` in your `.env` to run without real API credentials."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── Global validation-error handler ──────────────────────────────────────────
# Pydantic v2 raises RequestValidationError; we format it as a clean JSON body.
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Collect all error messages into a readable list
    messages = [
        f"{' → '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": messages},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root() -> dict:
    """Health-check endpoint."""
    return {"status": "ok", "service": "Automated Multi-Platform Posting System"}


@app.post(
    "/posting",
    response_model=PostingResponse,
    summary="Publish a message to all configured platforms",
    tags=["Posting"],
)
async def post_message(payload: PostingRequest) -> PostingResponse:
    """
    Accept a message and publish it concurrently to all five platforms.

    **Validation rules:**
    - `message` must not exceed 200 characters
    - `message` must contain exactly one valid HTTP/HTTPS URL (the CTA link)

    **Platform integrations:**
    - Reddit (r/test by default)
    - Mastodon (mastodon.social by default)
    - Telegram (via Bot API)
    - Pastebin
    - Hashnode

    Set `MOCK_MODE=true` in `.env` to test without real API credentials.
    """
    logger.info("POST /posting  message_length=%d", len(payload.message))
    response = await publish_to_all(payload.message)
    return response

