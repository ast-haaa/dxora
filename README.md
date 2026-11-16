# Automated Multi-Platform Posting System

A production-quality FastAPI application that accepts a message and publishes it **concurrently** across five third-party platforms through their official APIs.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Installation & Setup](#installation--setup)
6. [Environment Variables](#environment-variables)
7. [Running the Application](#running-the-application)
8. [Interactive API Documentation (Swagger)](#interactive-api-documentation-swagger)
9. [Sample Request & Response](#sample-request--response)
10. [Platform Integrations](#platform-integrations)
11. [Testing](#testing)
12. [Known Limitations](#known-limitations)
13. [Security & Submission Readiness](#security--submission-readiness)

---

## Project Overview

This system provides an automated multi-platform publishing REST API accessible at:

```
POST http://localhost:4000/posting
```

When a request is received, the system:
1. Validates the input message using Pydantic v2 (ensuring it is $\le$ 200 characters and contains exactly one valid HTTP/HTTPS CTA link).
2. Concurrently dispatches the post across **five third-party platforms** using `asyncio.gather(..., return_exceptions=True)`.
3. Handles each platform independently — if any platform experiences rate limiting, auth failures, or timeouts, the remaining platforms continue uninterrupted.
4. Returns a unified JSON response detailing the status, posted URL, public access flag, and execution timestamp for each platform.

---

## Architecture

```
                        ┌─────────────────────────┐
                        │   FastAPI  (main.py)     │
                        │   POST /posting          │
                        └────────────┬────────────┘
                                     │  validated PostingRequest
                                     ▼
                        ┌─────────────────────────┐
                        │  PostingService          │
                        │  posting_service.py      │
                        │  asyncio.gather(...)     │
                        └──┬──┬──┬──┬──┬──────────┘
                           │  │  │  │  │
              ┌────────────┘  │  │  │  └───────────────┐
              ▼               ▼  ▼  ▼                   ▼
           Bluesky         Mastodon  Telegram  Pastebin  Discord
        (platform_a)   (platform_b)(platform_c)(platform_d)(platform_e)
              │               │  │  │                   │
              └───────────────┴──┴──┴───────────────────┘
                                     │  List[PlatformResult]
                                     ▼
                             PostingResponse JSON
```

### Architectural Highlights
- **BasePlatform (Abstract Base Class)**: Enforces a consistent contract across all platform integrations (`post(message) -> PlatformResult`).
- **Resilient Concurrency**: `asyncio.gather(..., return_exceptions=True)` isolates platform execution so unexpected errors in one adapter never bubble up to break the entire batch.
- **Pydantic v2 Schema Sanitization**: Performs strict URL extraction and validation (supporting queries, fragments, ports, and parenthesis stripping) while rejecting malformed inputs.
- **Integrated Mock Mode**: Setting `MOCK_MODE=true` allows full automated pipeline testing without requiring live external platform API credentials.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| **Python 3.12** | Core programming language |
| **FastAPI** | Modern, high-performance async web framework |
| **Uvicorn** | Production-ready ASGI web server |
| **Pydantic v2** | Data parsing, schema definition, and URL validation |
| **pydantic-settings** | Type-safe environment variable management |
| **HTTPX** | Asynchronous HTTP client for external REST APIs |
| **atproto** | Official Bluesky / AT Protocol Python SDK |
| **python-dotenv** | Loads `.env` configuration into environment variables |
| **Pytest & pytest-asyncio** | Comprehensive test suite for synchronous and asynchronous flows |

---

## Project Structure

```
dxora/
│
├── app/
│   ├── __init__.py
│   ├── main.py              ← FastAPI entry point, lifecycle, routes & error handlers
│   ├── schemas.py           ← Pydantic request, response & platform outcome models
│   ├── config.py            ← Settings loaded from environment variables / .env
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── base.py          ← Abstract base class and standard result factories
│   │   ├── platform_a.py    ← Bluesky integration (atproto SDK)
│   │   ├── platform_b.py    ← Mastodon integration (REST API)
│   │   ├── platform_c.py    ← Telegram integration (Bot API)
│   │   ├── platform_d.py    ← Pastebin integration (POST API)
│   │   └── platform_e.py    ← Discord integration (Webhook API)
│   └── services/
│       ├── __init__.py
│       └── posting_service.py ← Concurrently triggers all platforms & computes result
│
├── tests/
│   ├── __init__.py
│   └── test_posting.py      ← 44 unit and integration tests covering all requirements
│
├── .env.example             ← Template documenting all environment variables
├── .gitignore               ← Excludes .env, .venv, caches, and IDE metadata
├── check_imports.py         ← Quick diagnostic script verifying platform imports
├── pytest.ini               ← Pytest configuration with asyncio default loop scope
├── requirements.txt         ← Project dependencies with pinned minimum versions
└── README.md                ← Complete project documentation
```

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ast-haaa/dxora.git
cd dxora
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example configuration to `.env`:

**Windows:**
```powershell
copy .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` and fill in your platform credentials (see [Environment Variables](#environment-variables)).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BLUESKY_HANDLE` | For Bluesky | Your Bluesky handle (e.g., `user.bsky.social`) |
| `BLUESKY_APP_PASSWORD` | For Bluesky | Dedicated App Password from Bluesky Settings $\rightarrow$ App Passwords |
| `MASTODON_INSTANCE_URL` | Optional | Instance base URL (default: `https://mastodon.social`) |
| `MASTODON_ACCESS_TOKEN` | For Mastodon | OAuth access token with `write:statuses` scope |
| `TELEGRAM_BOT_TOKEN` | For Telegram | Bot token created via `@BotFather` |
| `TELEGRAM_CHAT_ID` | For Telegram | Channel username (`@channelname`) or numeric chat ID |
| `PASTEBIN_API_KEY` | For Pastebin | Developer API key from `pastebin.com/doc_api` |
| `PASTEBIN_USERNAME` | Optional | Pastebin account username |
| `PASTEBIN_PASSWORD` | Optional | Pastebin account password |
| `DISCORD_WEBHOOK_URL` | For Discord | Full Discord Webhook URL (`https://discord.com/api/webhooks/...`) |
| `MOCK_MODE` | Optional | Set to `true` to simulate all postings without hitting live APIs (default: `false`) |
| `REQUEST_TIMEOUT` | Optional | Outbound HTTP request timeout in seconds (default: `15`) |

> **Security Note:** Never commit your real `.env` file to version control. It is explicitly listed in `.gitignore`.

---

## Running the Application

### Production / Live Mode

Ensure `.env` contains your live credentials, then run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

The server will be reachable at:
`http://localhost:4000`

### Mock Mode (No credentials required)

To test the end-to-end API without external credentials, enable `MOCK_MODE`:

**Windows PowerShell:**
```powershell
$env:MOCK_MODE="true"; uvicorn app.main:app --host 0.0.0.0 --port 4000
```

**macOS / Linux:**
```bash
MOCK_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 4000
```

In mock mode, all 5 platforms return `status: "mock"` and realistic URLs immediately without outbound network calls.

---

## Interactive API Documentation (Swagger)

Once the server is running, explore and test the API directly from your browser:
- **Interactive Swagger UI**: [http://localhost:4000/docs](http://localhost:4000/docs)
- **ReDoc Documentation**: [http://localhost:4000/redoc](http://localhost:4000/redoc)

---

## Sample Request & Response

### Request

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Check out our latest business platform and grow your online visibility. https://example.com"}'
```

### Successful Live Response (All 5 Platforms Configured)

```json
{
  "success": true,
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/demouser.bsky.social/post/3ldabc1234xyz",
      "public_access": true,
      "date": "2026-11-16",
      "time": "22:15:30",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@demouser/113495829104857201",
      "public_access": true,
      "date": "2026-11-16",
      "time": "22:15:30",
      "error": null
    },
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/demochannel/42",
      "public_access": true,
      "date": "2026-11-16",
      "time": "22:15:30",
      "error": null
    },
    {
      "platform": "Pastebin",
      "status": "success",
      "posted_url": "https://pastebin.com/kH8pQw1A",
      "public_access": true,
      "date": "2026-11-16",
      "time": "22:15:30",
      "error": null
    },
    {
      "platform": "Discord",
      "status": "success",
      "posted_url": "https://discord.com/channels/123456789012345678/987654321098765432/112233445566778899",
      "public_access": false,
      "date": "2026-11-16",
      "time": "22:15:30",
      "error": null
    }
  ]
}
```

### Validation Error Responses (HTTP 422)

**Message exceeds 200 characters:**
```json
{
  "detail": [
    "body → message: message exceeds 200 characters (got 215)"
  ]
}
```

**Missing CTA Link:**
```json
{
  "detail": [
    "body → message: message must contain exactly one valid HTTP or HTTPS CTA link, found 0"
  ]
}
```

**Multiple CTA Links:**
```json
{
  "detail": [
    "body → message: message must contain exactly one valid HTTP or HTTPS CTA link, found 2: ['https://example.com', 'https://other.com']"
  ]
}
```

---

## Platform Integrations

### 1. Platform A — Bluesky
- **Official Documentation**: [https://docs.bsky.app/](https://docs.bsky.app/)
- **Integration**: AT Protocol using the official `atproto` SDK. Synchronous SDK calls are offloaded to worker threads via `asyncio.to_thread` to maintain a non-blocking event loop.
- **Authentication**: Handle + App Password (generated via Bluesky Settings $\rightarrow$ Privacy and Security $\rightarrow$ App Passwords).
- **URL Resolution**: Post rkey is extracted from the returned AT URI (`at://did:plc:.../app.bsky.feed.post/<rkey>`) to construct the canonical web URL: `https://bsky.app/profile/{handle}/post/{rkey}`.
- **Public Access**: `true`.

### 2. Platform B — Mastodon
- **Official Documentation**: [https://docs.joinmastodon.org/methods/statuses/](https://docs.joinmastodon.org/methods/statuses/)
- **Integration**: HTTPX asynchronous `POST` to `{instance_url}/api/v1/statuses`.
- **Authentication**: Bearer token with `write:statuses` scope.
- **URL Resolution**: Extracted directly from response `url`.
- **Public Access**: `true` (status visibility defaults to public).

### 3. Platform C — Telegram
- **Official Documentation**: [https://core.telegram.org/bots/api#sendmessage](https://core.telegram.org/bots/api#sendmessage)
- **Integration**: HTTPX asynchronous `POST` to `https://api.telegram.org/bot{TOKEN}/sendMessage`.
- **Authentication**: Bot API token obtained from `@BotFather`.
- **URL Resolution**:
  - For public channels (e.g. `@channelname`), constructed as `https://t.me/{channelname}/{message_id}` (`public_access=true`).
  - For numeric chat IDs, queries chat info; if private, `public_access=false` and `posted_url=null`.

### 4. Platform D — Pastebin
- **Official Documentation**: [https://pastebin.com/doc_api](https://pastebin.com/doc_api)
- **Integration**: HTTPX asynchronous `POST` to `https://pastebin.com/api/api_post.php`.
- **Authentication**: Developer API Key. If username/password are supplied, requests a user session key via `api_login.php`.
- **URL Resolution**: The API directly returns the public paste URL (e.g., `https://pastebin.com/XXXXXXXX`).
- **Public Access**: `true`.

### 5. Platform E — Discord
- **Official Documentation**: [https://discord.com/developers/docs/resources/webhook](https://discord.com/developers/docs/resources/webhook)
- **Integration**: HTTPX asynchronous calls against the configured Webhook URL. First retrieves channel/guild metadata (`GET`), then submits the message with query param `?wait=true` to receive the created message payload.
- **Authentication**: Embedded webhook token within the webhook URL.
- **URL Resolution**: Constructs canonical message permalink `https://discord.com/channels/{guild_id}/{channel_id}/{message_id}`.
- **Public Access**: `false` (access is restricted to members possessing read permissions in that Discord server channel).

---

## Testing

The test suite validates input parsing, platform failure isolation, mock mode behavior, and unit-level platform operations with full mocking (no network calls required during testing).

### Running the Tests

**Windows PowerShell:**
```powershell
.\.venv\Scripts\pytest.exe tests/ -v
```

**macOS / Linux:**
```bash
pytest tests/ -v
```

### Test Coverage Summary

```
============================= 44 passed in 2.56s ==============================
```

| Test Class | Test Case | Purpose | Result |
|---|---|---|:---:|
| `TestInputValidation` | `test_valid_message_accepted` | Standard valid message and CTA URL | ✅ PASSED |
| `TestInputValidation` | `test_message_exceeds_200_characters_rejected` | Message > 200 chars triggers 422 | ✅ PASSED |
| `TestInputValidation` | `test_message_exactly_200_characters_accepted` | Boundary check: 200 chars accepted | ✅ PASSED |
| `TestInputValidation` | `test_message_201_characters_rejected` | Boundary check: 201 chars rejected | ✅ PASSED |
| `TestInputValidation` | `test_message_no_url_rejected` | Zero CTA URLs rejected | ✅ PASSED |
| `TestInputValidation` | `test_message_multiple_urls_rejected` | >1 CTA URLs rejected | ✅ PASSED |
| `TestInputValidation` | `test_message_blank_rejected` | Whitespace-only message rejected | ✅ PASSED |
| `TestInputValidation` | `test_message_empty_string_rejected` | Empty string rejected | ✅ PASSED |
| `TestInputValidation` | `test_invalid_url_scheme_rejected` | `ftp://` scheme rejected | ✅ PASSED |
| `TestInputValidation` | `test_http_url_accepted` | Plain `http://` URL accepted | ✅ PASSED |
| `TestInputValidation` | `test_https_url_accepted` | Secure `https://` URL accepted | ✅ PASSED |
| `TestInputValidation` | `test_url_query_parameters_accepted` | URLs with query strings preserved | ✅ PASSED |
| `TestInputValidation` | `test_url_fragment_accepted` | URLs with anchors/fragments preserved | ✅ PASSED |
| `TestInputValidation` | `test_url_port_accepted` | URLs with explicit ports accepted | ✅ PASSED |
| `TestInputValidation` | `test_url_trailing_punctuation_stripped` | Strips trailing `.` or `,` without breaking URL | ✅ PASSED |
| `TestInputValidation` | `test_url_in_parentheses_accepted` | Extracts URL cleanly from `(https://...)` | ✅ PASSED |
| `TestInputValidation` | `test_malformed_hostname_rejected` | Missing domain/host rejected | ✅ PASSED |
| `TestInputValidation` | `test_invalid_scheme_rejected` | Protocol relative / missing scheme rejected | ✅ PASSED |
| `TestPostingEndpoint` | `test_valid_request_returns_200` | Full HTTP POST `/posting` succeeds | ✅ PASSED |
| `TestPostingEndpoint` | `test_message_too_long_returns_422` | API layer returns HTTP 422 | ✅ PASSED |
| `TestPostingEndpoint` | `test_no_url_returns_422` | API layer enforces CTA rule | ✅ PASSED |
| `TestPostingEndpoint` | `test_multiple_urls_returns_422` | API layer rejects multi-link messages | ✅ PASSED |
| `TestPostingEndpoint` | `test_missing_message_field_returns_422` | Empty payload returns 422 | ✅ PASSED |
| `TestPostingEndpoint` | `test_health_check_returns_ok` | GET `/` returns 200 OK | ✅ PASSED |
| `TestPlatformUnits` | `test_bluesky_missing_credentials_returns_failure` | Detects absent Bluesky credentials | ✅ PASSED |
| `TestPlatformUnits` | `test_bluesky_mock_mode_returns_mock` | Verified mock generation for Bluesky | ✅ PASSED |
| `TestPlatformUnits` | `test_bluesky_auth_failure_returns_failed` | Gracefully captures Bluesky login errors | ✅ PASSED |
| `TestPlatformUnits` | `test_bluesky_success` | Full mock test of atproto client post | ✅ PASSED |
| `TestPlatformUnits` | `test_mastodon_missing_credentials_returns_failure` | Detects absent Mastodon token | ✅ PASSED |
| `TestPlatformUnits` | `test_mastodon_mock_mode_returns_mock` | Verified mock generation for Mastodon | ✅ PASSED |
| `TestPlatformUnits` | `test_mastodon_success` | Full mock test of Mastodon status post | ✅ PASSED |
| `TestPlatformUnits` | `test_telegram_missing_credentials_returns_failure` | Detects absent Telegram token | ✅ PASSED |
| `TestPlatformUnits` | `test_telegram_success_public_channel` | Constructs public Telegram permalink | ✅ PASSED |
| `TestPlatformUnits` | `test_telegram_numeric_chat_id_with_public_username` | Resolves numeric chat with public handle | ✅ PASSED |
| `TestPlatformUnits` | `test_pastebin_missing_credentials_returns_failure` | Detects absent Pastebin API key | ✅ PASSED |
| `TestPlatformUnits` | `test_pastebin_success` | Verifies paste creation flow | ✅ PASSED |
| `TestPlatformUnits` | `test_discord_missing_credentials_returns_failure` | Detects absent Discord webhook URL | ✅ PASSED |
| `TestPlatformUnits` | `test_discord_mock_mode_returns_mock` | Verified mock generation for Discord | ✅ PASSED |
| `TestPlatformUnits` | `test_discord_webhook_check_failure_returns_failed` | Captures invalid Discord webhook status | ✅ PASSED |
| `TestPlatformUnits` | `test_discord_posting_failure_returns_failed` | Captures message dispatch failure | ✅ PASSED |
| `TestPlatformUnits` | `test_discord_success` | Full mock test of Discord webhook post | ✅ PASSED |
| `TestPostingService` | `test_one_failure_does_not_cancel_others` | Proves platform failure isolation | ✅ PASSED |
| `TestPostingService` | `test_all_platforms_fail_success_is_false` | Overall success=False when all fail | ✅ PASSED |
| `TestPostingService` | `test_mock_mode_overall_success` | Overall success=True in mock mode | ✅ PASSED |

---

## Known Limitations

| Platform | Known Limitation |
|---|---|
| **Bluesky** | Rate limits apply for post creation. Requires an App Password rather than the primary account password for authenticated access. |
| **Mastodon** | Character limits and rate limits vary depending on the chosen federated instance (mastodon.social imposes 500 characters, well within our 200-char requirement). |
| **Telegram** | Posting to private groups/chats does not yield a public URL (`posted_url` is `null` and `public_access` is `false`). |
| **Pastebin** | Free-tier accounts have an IP-based limit of 10 pastes per 24 hours. Output is a raw text paste rather than a conversational feed post. |
| **Discord** | Webhook messages are posted into a specific server channel; view access requires appropriate channel permissions (`public_access` is `false`). |

---

## Security & Submission Readiness

1. **Zero Secret Leakage**: The repository is pre-configured with a comprehensive `.gitignore` preventing `.env`, `.env*.local`, virtual environments (`.venv/`), and pycache files from being tracked.
2. **Template Provided**: `.env.example` provides an exhaustive reference of all configuration options without disclosing live tokens.
3. **Mock Mode for Evaluators**: Reviewers without live API credentials can test the entire workflow out-of-the-box by setting `MOCK_MODE=true`.
