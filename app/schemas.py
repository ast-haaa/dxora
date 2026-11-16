"""
schemas.py — Pydantic models for request/response validation.

All data contracts are defined here so they can be reused across
the application and auto-documented by FastAPI's OpenAPI generator.
"""

from __future__ import annotations

import re
from typing import Optional
from datetime import date, time

from pydantic import BaseModel, field_validator, model_validator


from urllib.parse import urlparse


# ── URL extraction and validation helpers ──────────────────────────────────────

# Pattern matching potential URI/URL strings starting with scheme://
_CANDIDATE_URL_PATTERN = re.compile(
    r"(?:https?://|[a-zA-Z][a-zA-Z0-9+.-]*://)[^\s<>\"'`]*",
    re.IGNORECASE,
)


def _clean_extracted_url(raw_url: str) -> str:
    """
    Strips trailing sentence punctuation and handles parenthesized/bracketed URLs
    without truncating legitimate URL contents (such as query strings or fragments).
    """
    trailing_chars = ".,!?:;\"'>"
    while raw_url and raw_url[-1] in trailing_chars:
        raw_url = raw_url[:-1]

    # Handle unmatched closing parenthesis or brackets
    if raw_url.endswith(")") and raw_url.count(")") > raw_url.count("("):
        raw_url = raw_url[:-1]
    if raw_url.endswith("]") and raw_url.count("]") > raw_url.count("["):
        raw_url = raw_url[:-1]
    if raw_url.endswith("}") and raw_url.count("}") > raw_url.count("{"):
        raw_url = raw_url[:-1]

    while raw_url and raw_url[-1] in trailing_chars:
        raw_url = raw_url[:-1]

    return raw_url


def _extract_and_validate_urls(text: str) -> list[str]:
    """
    Extracts candidate URLs, cleans trailing punctuation/parentheses,
    and validates them using urllib.parse.urlparse.
    Returns the list of valid extracted URLs.
    Raises ValueError on malformed URLs or invalid schemes.
    """
    raw_matches = _CANDIDATE_URL_PATTERN.findall(text)
    if not raw_matches:
        return []

    cleaned_urls: list[str] = []
    for raw in raw_matches:
        cleaned = _clean_extracted_url(raw)
        if not cleaned:
            continue

        parsed = urlparse(cleaned)

        # 1. Validate scheme (HTTP or HTTPS required)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError(
                f"CTA link must use HTTP or HTTPS scheme (got '{scheme}' in '{cleaned}')"
            )

        # 2. Validate hostname
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"CTA link '{cleaned}' has a missing or malformed hostname")

        # Reject malformed hostname patterns
        if hostname.startswith(".") or hostname.endswith("."):
            raise ValueError(f"CTA link '{cleaned}' has a malformed hostname: '{hostname}'")
        if hostname.startswith("-") or hostname.endswith("-"):
            raise ValueError(f"CTA link '{cleaned}' has a malformed hostname: '{hostname}'")
        if ".." in hostname:
            raise ValueError(f"CTA link '{cleaned}' has a malformed hostname: '{hostname}'")
        if hostname.lower() != "localhost" and "." not in hostname:
            raise ValueError(f"CTA link '{cleaned}' has a malformed hostname: '{hostname}'")

        # 3. Validate port if present
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                raise ValueError(f"CTA link '{cleaned}' has an invalid port number: {parsed.port}")

        cleaned_urls.append(cleaned)

    return cleaned_urls


def _extract_urls(text: str) -> list[str]:
    """Backward compatibility helper returning extracted and validated URLs."""
    return _extract_and_validate_urls(text)


# ── Request schema ────────────────────────────────────────────────────────────

class PostingRequest(BaseModel):
    """
    Payload accepted by POST /posting.

    Rules (validated before any platform call is made):
    - message ≤ 200 characters
    - Exactly one valid HTTP/HTTPS URL must be present
    """

    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v

    @model_validator(mode="after")
    def validate_message_rules(self) -> "PostingRequest":
        msg = self.message

        # Rule 1 — length
        if len(msg) > 200:
            raise ValueError(
                f"message exceeds 200 characters (got {len(msg)})"
            )

        # Rule 2 — exactly one CTA URL
        urls = _extract_urls(msg)
        if len(urls) == 0:
            raise ValueError(
                "message must contain exactly one CTA link (none found)"
            )
        if len(urls) > 1:
            raise ValueError(
                f"message must contain exactly one CTA link ({len(urls)} found)"
            )

        return self


# ── Per-platform result ───────────────────────────────────────────────────────

class PlatformResult(BaseModel):
    """
    Outcome of a single platform posting attempt.
    Fields are populated from real API responses — nothing is fabricated.
    """

    platform: str
    status: str                          # "success" | "failed" | "mock"
    posted_url: Optional[str] = None     # Actual URL returned by the platform
    public_access: Optional[bool] = None # Whether the post is publicly viewable
    date: Optional[str] = None           # ISO date string  e.g. "2026-11-15"
    time: Optional[str] = None           # HH:MM:SS          e.g. "10:30:00"
    error: Optional[str] = None          # Human-readable error message


# ── Top-level response ────────────────────────────────────────────────────────

class PostingResponse(BaseModel):
    """
    Response envelope returned by POST /posting.
    success = True when at least one platform succeeded.
    """

    success: bool
    results: list[PlatformResult]

