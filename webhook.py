import hmac, logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.bot.dispatcher import get_bot,get_dispatcher
from app.config import get_settings
from app.database import get_session_factory
from app.models import ProcessedUpdate
from aiogram.types import Update
logger=logging.getLogger(__name__)
router=APIRouter()

async def claim_update(update_id: int) -> bool:
    """Atomically claim an update; concurrent webhook retries cannot both own it."""
    async with get_session_factory()() as db:
        now = datetime.now(timezone.utc)
        dialect = db.bind.dialect.name
        insert_fn = sqlite_insert if dialect == "sqlite" else pg_insert
        stmt = insert_fn(ProcessedUpdate).values(
            update_id=update_id, status="processing", updated_at=now
        ).on_conflict_do_nothing(index_elements=["update_id"]).returning(ProcessedUpdate.update_id)
        inserted = (await db.execute(stmt)).first()
        if inserted:
            await db.commit()
            return True
        # Only a failed attempt or an abandoned lease can be reclaimed.
        cutoff = now - timedelta(minutes=2)
        reclaimed = await db.execute(
            update(ProcessedUpdate)
            .where(
                ProcessedUpdate.update_id == update_id,
                or_(
                    ProcessedUpdate.status == "retry",
                    (ProcessedUpdate.status == "processing") & (ProcessedUpdate.updated_at < cutoff),
                ),
            )
            .values(status="processing", updated_at=now)
            .returning(ProcessedUpdate.update_id)
        )
        row = reclaimed.first()
        await db.commit()
        return row is not None

async def finish_update(update_id: int, status_value: str):
    async with get_session_factory()() as db:
        await db.execute(update(ProcessedUpdate).where(ProcessedUpdate.update_id==update_id).values(status=status_value,updated_at=datetime.now(timezone.utc)))
        await db.commit()

@router.post("/telegram/webhook/{path_secret}")
async def telegram_webhook(path_secret: str, request: Request, x_telegram_bot_api_secret_token: str|None=Header(default=None)):
    settings=get_settings()
    if not hmac.compare_digest(path_secret,settings.WEBHOOK_SECRET[:24]) or not x_telegram_bot_api_secret_token or not hmac.compare_digest(x_telegram_bot_api_secret_token,settings.WEBHOOK_SECRET):
        raise HTTPException(403,"Forbidden")
    try: update_obj=Update.model_validate(await request.json())
    except Exception as exc: raise HTTPException(400,"Invalid update") from exc
    if not await claim_update(update_obj.update_id): return {"ok":True,"duplicate":True}
    try:
        await get_dispatcher().feed_update(bot=get_bot(),update=update_obj)
        await finish_update(update_obj.update_id,"done")
    except Exception:
        await finish_update(update_obj.update_id,"retry")
        logger.exception("Telegram update processing failed; retry allowed")
        raise HTTPException(500,"Update processing failed")
    return {"ok":True}
