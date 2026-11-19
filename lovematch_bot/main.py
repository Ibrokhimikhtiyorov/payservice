import asyncio
import logging

from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import db
import hamyon
from config import BOT_TOKEN, PAYMENT_PROVIDER, PAYMENT_WEBHOOK_SECRET, PORT, WEB_HOST
from handlers import admin, chat, discovery, matches, premium, profile, settings, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("lovematch")


class ActiveMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            try:
                await db.touch_active(user.id)
            except Exception:
                pass
        return await handler(event, data)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "lovematch-bot", "payment": PAYMENT_PROVIDER})


async def payment_webhook(request: web.Request) -> web.Response:
    try:
        if request.content_type and "json" in request.content_type:
            data = await request.json()
        else:
            data = dict(await request.post())
    except Exception:
        return web.json_response({"ok": False, "error": "bad_payload"}, status=400)

    secret = str(data.get("secret") or request.headers.get("X-Webhook-Secret") or "").strip()
    if PAYMENT_WEBHOOK_SECRET and secret != PAYMENT_WEBHOOK_SECRET:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    ref = str(data.get("provider_ref") or data.get("ref") or data.get("order_id") or "").strip()
    if not ref:
        return web.json_response({"ok": False, "error": "no_ref"}, status=400)

    ok, p, _newly = await db.confirm_payment(ref)
    if not ok:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.json_response({"ok": True, "status": p.get("status") if p else "paid"})


async def on_startup(bot: Bot):
    await db.init_pool()
    me = await bot.get_me()
    log.info("Bot started as @%s", me.username)


async def on_shutdown(bot: Bot):
    await db.close_pool()
    await bot.session.close()


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida yo'q")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(ActiveMiddleware())

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(profile.router)
    dp.include_router(discovery.router)
    dp.include_router(matches.router)
    dp.include_router(chat.router)
    dp.include_router(premium.router)
    dp.include_router(settings.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/payment/webhook", payment_webhook)
    app.router.add_post("/hamyon/prepare", hamyon.prepare)
    app.router.add_post("/hamyon/complete", hamyon.complete)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, PORT)
    await site.start()
    log.info("HTTP server on %s:%s", WEB_HOST, PORT)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
