import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, TelegramConnection, Chat, Message, Direction

async def upsert_connection(db: AsyncSession, user: User, bcid: str, enabled: bool, can_reply: bool):
    conn = await db.scalar(select(TelegramConnection).where(TelegramConnection.business_connection_id == bcid))
    if conn and conn.user_id != user.id:
        raise ValueError("Business connection is already assigned to another user")
    if conn is None:
        conn = TelegramConnection(user_id=user.id, business_connection_id=bcid, is_enabled=enabled, can_reply=can_reply)
        db.add(conn)
    else:
        conn.is_enabled, conn.can_reply = enabled, can_reply
        conn.revoked_at = None if enabled else datetime.now(timezone.utc)
    await db.flush()
    return conn

async def resolve_connection(db: AsyncSession, bcid: str):
    return await db.scalar(select(TelegramConnection).where(TelegramConnection.business_connection_id == bcid, TelegramConnection.is_enabled.is_(True)))

async def get_or_create_chat(db: AsyncSession, user: User, conn: TelegramConnection, peer_id: int, peer_name: str | None):
    chat = await db.scalar(select(Chat).where(Chat.connection_id == conn.id, Chat.peer_tg_id == peer_id))
    if chat is None:
        chat = Chat(user_id=user.id, connection_id=conn.id, peer_tg_id=peer_id, peer_name=peer_name)
        db.add(chat)
        await db.flush()
    elif peer_name:
        chat.peer_name = peer_name
    return chat

async def store_inbound(db: AsyncSession, chat: Chat, message_id: int, text: str, sent_at, media_type=None, file_id=None, file_unique_id=None, file_meta=None):
    values = dict(id=uuid.uuid4(), chat_id=chat.id, tg_message_id=message_id, direction=Direction.inbound, text=text or "", sent_at=sent_at or datetime.now(timezone.utc), media_type=media_type, file_id=file_id, file_unique_id=file_unique_id, file_meta=file_meta)
    dialect = db.bind.dialect.name
    stmt = (sqlite_insert if dialect == "sqlite" else pg_insert)(Message).values(**values).on_conflict_do_nothing(index_elements=["chat_id", "tg_message_id"]).returning(Message.id)
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return await db.get(Message, row[0])

async def edit_inbound(db: AsyncSession, chat: Chat, message_id: int, text: str, media_type, file_id, file_unique_id, file_meta):
    stmt = update(Message).where(Message.chat_id == chat.id, Message.tg_message_id == message_id, Message.direction == Direction.inbound).values(text=text or "", media_type=media_type, file_id=file_id, file_unique_id=file_unique_id, file_meta=file_meta, edited_at=datetime.now(timezone.utc)).returning(Message.id)
    row = (await db.execute(stmt)).first()
    return await db.get(Message, row[0]) if row else None

async def delete_inbound(db: AsyncSession, chat: Chat, ids: list[int]):
    if not ids: return []
    result = await db.execute(delete(Message).where(Message.chat_id == chat.id, Message.direction == Direction.inbound, Message.tg_message_id.in_(ids)).returning(Message.tg_message_id))
    return [r[0] for r in result.all()]
