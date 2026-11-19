import hashlib
import hmac
import logging

from aiohttp import ClientSession, ClientTimeout, web

import db
from config import ADMIN_IDS, HAMYON_API_BASE, HAMYON_SHOP_ID, HAMYON_SHOP_KEY, HAMYON_TIMEOUT
from i18n import t

log = logging.getLogger(__name__)


def valid(form) -> bool:
    pid = str(form.get("payment_id", ""))
    amount = str(form.get("amount", ""))
    sign = str(form.get("sign", "")).lower()
    if not (HAMYON_SHOP_ID and HAMYON_SHOP_KEY and pid and amount and sign):
        return False
    expected = hashlib.md5(f"{HAMYON_SHOP_ID}{pid}{amount}{HAMYON_SHOP_KEY}".encode()).hexdigest()
    return hmac.compare_digest(expected, sign)


async def create_payment(order: str, amount: int) -> dict:
    if not HAMYON_SHOP_ID or not HAMYON_SHOP_KEY:
        raise RuntimeError("HamyonAPI SHOP_ID/SHOP_KEY sozlanmagan")
    timeout = ClientTimeout(total=HAMYON_TIMEOUT)
    async with ClientSession(timeout=timeout) as s:
        async with s.post(
            HAMYON_API_BASE + "/payment/create",
            data={
                "shop_id": HAMYON_SHOP_ID,
                "shop_key": HAMYON_SHOP_KEY,
                "amount": str(amount),
                "order_id": order,
            },
        ) as r:
            data = await r.json(content_type=None)
            if r.status >= 400 or not isinstance(data, dict) or data.get("error"):
                raise RuntimeError(str(data))
    pid = data.get("payment_id")
    if pid:
        await db.set_payment_id(order, str(pid))
    return data


async def prepare(request: web.Request):
    form = await request.post()
    if not valid(form):
        return web.json_response({"error": "signature"}, status=403)
    order = str(form.get("order_id", ""))
    try:
        amount = int(form.get("amount", "0"))
    except ValueError:
        return web.json_response({"error": "amount"}, status=400)
    p = await db.get_payment_by_ref(order)
    if not p or int(p["amount"]) != amount:
        return web.json_response({"error": "order_not_found_or_amount_mismatch"}, status=404)
    pid = str(form.get("payment_id", ""))
    if pid:
        await db.set_payment_id(order, pid)
    return web.json_response({"result": "ok"})


async def complete(request: web.Request):
    form = await request.post()
    if not valid(form):
        return web.json_response({"error": "signature"}, status=403)
    order = str(form.get("order_id", ""))
    pid = str(form.get("payment_id", ""))
    status = str(form.get("status", "")).lower()
    try:
        amount = int(form.get("amount", "0"))
    except ValueError:
        return web.json_response({"error": "amount"}, status=400)

    p = await db.get_payment_by_ref(order) if order else None
    if not p and pid:
        p = await db.get_payment_by_payment_id(pid)
        if p:
            order = p["provider_ref"]
    if not p:
        return web.json_response({"error": "payment_not_found"}, status=404)
    if int(p["amount"]) != amount:
        return web.json_response({"error": "amount_mismatch"}, status=400)
    if status != "paid":
        return web.json_response({"result": "ok"})

    ok, updated, newly = await db.confirm_payment(order)
    if not ok:
        return web.json_response({"error": "payment_not_found"}, status=404)

    bot = request.app.get("bot")
    if newly and bot and updated:
        tg_id = updated.get("tg_id")
        lang = "uz"
        try:
            u = await db.get_user(tg_id)
            lang = (u["lang"] if u else "uz") or "uz"
        except Exception:
            pass
        msg = t(lang, "boost_ok") if updated.get("purpose") == "boost" else t(lang, "payment_ok")
        try:
            await bot.send_message(tg_id, msg)
        except Exception:
            log.exception("notify user failed")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💳 <b>Yangi to'lov</b>\nID: #{updated['id']}\nUser: <code>{tg_id}</code>\nMaqsad: {updated.get('purpose')}\nSumma: {updated.get('amount')} so'm",
                )
            except Exception:
                pass
    return web.json_response({"result": "ok"})
