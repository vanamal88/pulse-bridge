import logging
from datetime import timezone
from aiogram import Router
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted
from sqlalchemy import select
from app.database import get_session_factory
from app.models import User, TelegramConnection, MediaType
from app.services.users import get_or_create_user
from app.services.sync import upsert_connection, resolve_connection, get_or_create_chat, store_inbound, edit_inbound, delete_inbound
from app.websocket.manager import manager
logger = logging.getLogger(__name__)
router = Router(name="business")

def extract_media(msg: Message):
    if msg.photo:
        p=msg.photo[-1]; return MediaType.photo,p.file_id,p.file_unique_id,{"width":p.width,"height":p.height,"file_size":p.file_size}
    for attr, kind in (("video",MediaType.video),("document",MediaType.document),("voice",MediaType.voice),("audio",MediaType.audio),("video_note",MediaType.video_note)):
        obj=getattr(msg,attr,None)
        if obj:
            meta={k:getattr(obj,k,None) for k in ("width","height","duration","file_size","mime_type","file_name","length") if getattr(obj,k,None) is not None}
            return kind,obj.file_id,obj.file_unique_id,meta
    return None,None,None,None

def peer_name(msg: Message):
    chat=msg.chat
    return " ".join(x for x in (chat.first_name, chat.last_name) if x) or chat.title or chat.username

@router.business_connection()
async def on_connection(event: BusinessConnection):
    async with get_session_factory()() as db:
        user=await get_or_create_user(db,event.user.id,event.user.first_name,event.user.username)
        rights=getattr(event,"rights",None)
        can_reply=bool(getattr(rights,"can_reply",False)) if rights else bool(getattr(event,"can_reply",False))
        await upsert_connection(db,user,event.id,event.is_enabled,can_reply)
        await db.commit()

async def _process_message(message: Message, edited: bool=False):
    bcid=message.business_connection_id
    if not bcid: return
    async with get_session_factory()() as db:
        conn=await resolve_connection(db,bcid)
        if not conn: return
        user=await db.get(User,conn.user_id)
        if message.from_user and message.from_user.id == user.tg_user_id: return
        chat=await get_or_create_chat(db,user,conn,message.chat.id,peer_name(message))
        text=message.text or message.caption or ""
        media_type,file_id,file_unique_id,file_meta=extract_media(message)
        if not text and not media_type: return
        if edited:
            saved=await edit_inbound(db,chat,message.message_id,text,media_type,file_id,file_unique_id,file_meta)
            event_name="message_edited"
        else:
            saved=await store_inbound(db,chat,message.message_id,text,message.date.astimezone(timezone.utc),media_type,file_id,file_unique_id,file_meta)
            event_name="message_new"
        await db.commit()
        if saved:
            await manager.broadcast(str(user.id),{"event":event_name,"message":{"id":str(saved.id),"chat_id":str(chat.id),"tg_message_id":saved.tg_message_id,"direction":saved.direction.value,"text":saved.text,"media_type":saved.media_type.value if saved.media_type else None,"file_id":saved.file_id,"file_unique_id":saved.file_unique_id,"file_meta":saved.file_meta,"sent_at":saved.sent_at.isoformat()}})

@router.business_message()
async def on_message(message: Message):
    try: await _process_message(message)
    except Exception:
        logger.exception("Failed to sync business message")
        raise

@router.edited_business_message()
async def on_edited(message: Message):
    try: await _process_message(message,True)
    except Exception:
        logger.exception("Failed to sync edited business message")
        raise

@router.deleted_business_messages()
async def on_deleted(event: BusinessMessagesDeleted):
    async with get_session_factory()() as db:
        conn=await resolve_connection(db,event.business_connection_id)
        if not conn: return
        from app.models import Chat
        chat=await db.scalar(select(Chat).where(Chat.connection_id==conn.id,Chat.peer_tg_id==event.chat.id))
        if not chat: return
        deleted=await delete_inbound(db,chat,event.message_ids)
        await db.commit()
        if deleted: await manager.broadcast(str(conn.user_id),{"event":"messages_deleted","chat_id":str(chat.id),"tg_message_ids":deleted})
