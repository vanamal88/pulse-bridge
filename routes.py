import hashlib, uuid, re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user, issue_ws_token
from app.config import get_settings
from app.database import get_db
from app.models import User, Chat, Message, TelegramConnection, Direction, OutboundRequest
from app.schemas import ChatRead, MessageRead, MessageCreate, WsTokenResponse
from app.services.telegram import TelegramService
from app.bot.dispatcher import get_bot

router = APIRouter()
@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    try:
        await db.execute(text("SELECT 1")); db_status = "ok"
    except Exception:
        await db.rollback(); db_status = "error"
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status, "version": "1.3.0"}

@router.get("/chats", response_model=list[ChatRead])
async def list_chats(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.created_at.desc()).limit(limit).offset(offset))
    return list(result.all())

@router.get("/messages", response_model=list[MessageRead])
async def list_messages(chat_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    chat = await db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat: raise HTTPException(404, "Chat not found")
    result = await db.scalars(select(Message).where(Message.chat_id == chat.id).order_by(Message.sent_at.asc()).limit(limit).offset(offset))
    return list(result.all())

@router.post("/messages", response_model=MessageRead, status_code=201)
async def send_message(payload: MessageCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    chat = await db.scalar(select(Chat).where(Chat.id == payload.chat_id, Chat.user_id == user.id))
    if not chat: raise HTTPException(404, "Chat not found")
    conn = await db.get(TelegramConnection, chat.connection_id)
    if not conn or not conn.is_enabled or not conn.can_reply: raise HTTPException(409, "Telegram Business connection is not allowed to send")
    body_hash = hashlib.sha256(f"{payload.chat_id}|{payload.text}|{payload.media_type}|{payload.file_id}".encode()).hexdigest()
    existing = await db.scalar(select(OutboundRequest).where(OutboundRequest.user_id == user.id, OutboundRequest.client_message_id == payload.client_message_id))
    if existing:
        if existing.payload_hash != body_hash: raise HTTPException(409, "client_message_id was already used with a different payload")
        if existing.status == "sent" and existing.telegram_message_id:
            msg = await db.scalar(select(Message).where(Message.chat_id == chat.id, Message.tg_message_id == existing.telegram_message_id, Message.direction == Direction.outbound))
            if msg: return msg
        raise HTTPException(409, f"Request already exists with status={existing.status}; do not retry automatically")
    reservation = OutboundRequest(user_id=user.id, chat_id=chat.id, client_message_id=payload.client_message_id, payload_hash=body_hash, status="pending")
    db.add(reservation)
    try:
        await db.commit()  # reserve idempotency key before external side effect
    except Exception:
        await db.rollback()
        raise HTTPException(409, "Duplicate client_message_id; retry by fetching the existing result")
    try:
        result = await TelegramService(get_bot()).send_business_message(conn.business_connection_id, chat.peer_tg_id, payload.text, payload.media_type, payload.file_id)
    except Exception as exc:
        reservation.status = "unknown"  # Telegram may have accepted request before connection failed
        reservation.error = type(exc).__name__
        await db.commit()
        raise HTTPException(502, "Telegram send outcome is unknown; do not retry with a new id") from exc
    msg = Message(chat_id=chat.id, tg_message_id=result.message_id, direction=Direction.outbound, text=payload.text, media_type=payload.media_type, file_id=result.file_id or payload.file_id, file_unique_id=result.file_unique_id, file_meta=result.file_meta)
    db.add(msg)
    reservation.status = "sent"
    reservation.telegram_message_id = result.message_id
    await db.commit()
    await db.refresh(msg)
    from app.websocket.manager import manager
    await manager.broadcast(str(user.id), {"event": "message_new", "message": {"id": str(msg.id), "chat_id": str(chat.id), "tg_message_id": msg.tg_message_id, "direction": "outbound", "text": msg.text, "media_type": msg.media_type.value if msg.media_type else None, "file_id": msg.file_id, "file_unique_id": msg.file_unique_id, "file_meta": msg.file_meta, "sent_at": msg.sent_at.isoformat()}})
    return msg

@router.get("/outbound/{client_message_id}")
async def outbound_status(client_message_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    request = await db.scalar(select(OutboundRequest).where(OutboundRequest.user_id == user.id, OutboundRequest.client_message_id == client_message_id))
    if request is None:
        raise HTTPException(404, "Outbound request not found")
    return {"client_message_id": request.client_message_id, "status": request.status, "telegram_message_id": request.telegram_message_id, "error": request.error}

@router.post("/ws-token", response_model=WsTokenResponse)
async def ws_token(user: User = Depends(current_user)):
    ttl = get_settings().WS_TOKEN_TTL
    return WsTokenResponse(token=issue_ws_token(str(user.id), ttl), expires_in=ttl)

@router.get("/telegram/connect")
async def connection_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    conn = await db.scalar(select(TelegramConnection).where(TelegramConnection.user_id == user.id, TelegramConnection.is_enabled.is_(True)))
    return {"connected": bool(conn), "can_reply": bool(conn and conn.can_reply), "instructions": "Telegram → Settings → Telegram Business → Chatbots → add @PulseBridge_Bot and grant required rights."}

@router.get("/files/{message_id}")
async def download_message_file(message_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    from app.config import get_settings
    msg = await db.scalar(select(Message).join(Chat).where(Message.id == message_id, Chat.user_id == user.id))
    if not msg or not msg.file_id: raise HTTPException(404, "File not found")
    bot = get_bot()
    tg_file = await bot.get_file(msg.file_id)
    if not tg_file.file_path: raise HTTPException(404, "Telegram file path unavailable")
    size = msg.file_meta.get("file_size") if msg.file_meta else None
    max_bytes = get_settings().MAX_FILE_BYTES
    if size is not None and size > max_bytes: raise HTTPException(413, "File exceeds configured limit")
    url = f"https://api.telegram.org/file/bot{bot.token}/{tg_file.file_path}"
    async def chunks():
        total = 0
        async for chunk in bot.session.stream_content(url):
            total += len(chunk)
            if total > max_bytes: raise RuntimeError("Telegram file exceeded streaming limit")
            yield chunk
    filename = "attachment"
    if msg.file_meta and msg.file_meta.get("file_name"): filename = re.sub(r"[^A-Za-z0-9._ -]", "_", str(msg.file_meta["file_name"]).split("/")[-1].split("\\")[-1])[:120] or "attachment"
    media_type = (msg.file_meta or {}).get("mime_type") or "application/octet-stream"
    return StreamingResponse(chunks(), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"})
