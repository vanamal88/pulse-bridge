import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app import __version__
from app.api.deps import consume_ws_token
from app.api.v1.router import router as api_router
from app.bot.dispatcher import get_bot,shutdown_bot
from app.bot.polling import run_polling
from app.bot.webhook import router as webhook_router
from app.config import get_settings
from app.database import close_db
from app.websocket.manager import manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings=get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL.upper(),format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot=get_bot(); task=None
    if settings.BOT_MODE=="polling":
        task=asyncio.create_task(run_polling())
    else:
        await bot.set_webhook(url=settings.full_webhook_url,secret_token=settings.WEBHOOK_SECRET,allowed_updates=["business_connection","business_message","edited_business_message","deleted_business_messages","message"])
    yield
    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
    if settings.BOT_MODE=="webhook":
        try: await bot.delete_webhook(drop_pending_updates=False)
        except Exception: logging.exception("Could not remove webhook on shutdown")
    await shutdown_bot(); await close_db()

app=FastAPI(title="PULSE Bridge",version=__version__,lifespan=lifespan)
app.include_router(api_router); app.include_router(webhook_router)
@app.websocket("/ws/messages")
async def ws_messages(websocket: WebSocket, token: str|None=None):
    user_id=consume_ws_token(token) if token else None
    if not user_id:
        await websocket.close(code=4401,reason="Unauthorized"); return
    await manager.connect(user_id,websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass
    finally: await manager.disconnect(user_id,websocket)
@app.get("/")
def root(): return {"name":"PULSE Bridge","version":__version__}
