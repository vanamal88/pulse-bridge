from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.config import get_settings
from app.bot.handlers import start, business
_bot = None
_dp = None
def get_bot():
    global _bot
    if _bot is None: _bot = Bot(get_settings().BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot
def get_dispatcher():
    global _dp
    if _dp is None:
        _dp = Dispatcher()
        _dp.include_router(start.router)
        _dp.include_router(business.router)
    return _dp
async def shutdown_bot():
    global _bot, _dp
    if _bot:
        await _bot.session.close()
    _bot = _dp = None
