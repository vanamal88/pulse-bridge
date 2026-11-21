# PULSE Bridge v1.3

Backend bridge between Telegram Business and the PULSE client. The bot does **not** compose or send replies on its own. Outbound messages are sent only after an authenticated PULSE API request.

## Stack

- Python 3.12
- FastAPI + aiogram 3
- PostgreSQL + SQLAlchemy 2 async
- Alembic migrations
- WebSocket events scoped to the owning PULSE user
- Docker / Render

## Important design points

1. Every Telegram user receives a separate random `pulse_...` API key in the bot's private chat. Only its SHA-256 hash is stored. `/newkey` revokes previous keys and issues a new one. The raw key is shown only once.
2. All chat/message/file queries are filtered by the authenticated user.
3. WebSocket handshake uses a short-lived, single-use token bound to that user. Events are broadcast only to that user's sockets.
4. Inbound Telegram messages use a unique `(chat_id, tg_message_id)` constraint and dialect-specific `ON CONFLICT DO NOTHING`.
5. Webhook updates are recorded with `processing/done/retry` states. Failed updates can be retried; abandoned processing claims become recoverable after two minutes.
6. Outbound requests require `client_message_id`. A reservation is committed before calling Telegram. If the outcome is ambiguous, the request is marked `unknown` and is not automatically resent. This is deliberate: Telegram does not offer a general idempotency key, so strict exactly-once delivery cannot be guaranteed across a network/database failure.
7. Media download is scoped to the owning user and has a configured byte limit. Telegram's own Bot API download limits still apply.
8. Production schema changes are managed by Alembic; `create_all()` is not called during app startup.

## Telegram setup

1. Create a bot with BotFather and set `BOT_TOKEN`.
2. Start a private chat with the bot and send `/start`. Save the API key shown. If lost, use `/newkey` (the old key is revoked).
3. In Telegram: Settings → Telegram Business → Chatbots → add `@PulseBridge_Bot`.
4. Grant the required message access/reply permissions. The connection is usable for outbound sends only when Telegram reports `can_reply`.
5. Telegram Business bots do not receive the account's pre-connection chat history. Only updates delivered after connection and within granted permissions are available.

## Environment

Copy `.env.example` to `.env` and set real values. Never commit `.env`, bot tokens, API keys, or webhook secrets.

- `BOT_TOKEN`: BotFather token.
- `WEBHOOK_SECRET`: at least 32 random characters; Telegram webhook secret token.
- `DATABASE_URL`: PostgreSQL URL. `postgres://` and `postgresql://` are normalized to `postgresql+asyncpg://`.
- `BOT_MODE`: `webhook` for Render or `polling` for local development.
- `WEBHOOK_BASE_URL`: public HTTPS base URL when using webhook mode.

## Local run with Docker

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN, WEBHOOK_SECRET, DATABASE_URL.
docker compose up --build
```

API docs: `http://localhost:8000/docs`.

For local polling mode set `BOT_MODE=polling`; `WEBHOOK_BASE_URL` is not needed. Run PostgreSQL with `docker compose up -d db`, then run migrations and Uvicorn locally:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Render

1. Push this folder to a GitHub repository.
2. Create a PostgreSQL database and a Docker Web Service from that repository.
3. Set environment variables: `BOT_TOKEN`, `WEBHOOK_SECRET`, `DATABASE_URL` (Internal Database URL), `BOT_MODE=webhook`, `WEBHOOK_BASE_URL` (the actual service URL), `LOG_LEVEL=INFO`.
4. Docker startup runs `alembic upgrade head` before Uvicorn.
5. Set health check path to `/api/v1/health`.
6. Use one running web instance for this initial deployment. The one-time WS-token store is process-local; multiple instances require Redis/shared storage and sticky routing or a shared token store.

`render.yaml` is a starting blueprint. Verify the actual Render service URL and database name before deploying; do not assume the placeholder URL is correct.

## API

All endpoints except `/`, `/api/v1/health`, and Telegram webhook require `X-API-Key`.

- `GET /api/v1/health`
- `GET /api/v1/telegram/connect`
- `GET /api/v1/chats`
- `GET /api/v1/messages?chat_id=<uuid>`
- `POST /api/v1/messages`
- `GET /api/v1/files/{message_id}`
- `GET /api/v1/outbound/{client_message_id}`
- `POST /api/v1/ws-token`
- `WS /ws/messages?token=<one-time-token>`

Example outbound body:

```json
{
  "chat_id": "CHAT_UUID",
  "client_message_id": "a-unique-client-generated-id",
  "text": "Hello"
}
```

For media, include `media_type` and a Telegram `file_id` previously received for this bot. A future upload endpoint can add user-uploaded files; this version does not pretend that a raw device file can be sent by passing a local path.

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

SQLite tests cover API-key ownership/revocation, inbound deduplication, edit/delete behavior, and user-bound single-use WS tokens. A real PostgreSQL + Telegram + Render integration test is still required before production use.

## Known limitations before production

- Telegram API/network outcomes can be ambiguous. `unknown` outbound requests require reconciliation; never blindly resend them.
- WS token storage is in-memory and intended for one app process/instance.
- The webhook claim uses a two-minute stale-processing lease. For high-volume production, move update processing to a durable queue with worker leases.
- Telegram Business rights and supported update fields depend on the Bot API version available to Telegram and the installed aiogram version.
- No old chat history is imported; Telegram only sends eligible updates after the bot is connected.
