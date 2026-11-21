from app.bot.dispatcher import get_bot,get_dispatcher
async def run_polling():
    bot=get_bot()
    await bot.delete_webhook(drop_pending_updates=False)
    await get_dispatcher().start_polling(bot)
