import logging
import secrets
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

import db
from config import PAYMENT_PAY_URL, PAYMENT_PROVIDER
from i18n import t, MENU_BTNS
from keyboards import main_menu_kb, premium_kb, pay_confirm_kb

router = Router()
log = logging.getLogger(__name__)


async def _create_and_maybe_confirm(uid: int, purpose: str, amount: int, meta: str = ""):
    ref = f"lm_{purpose}_{uid}_{int(time.time())}_{secrets.token_hex(4)}"
    row = await db.create_payment(uid, purpose, amount, ref, None, meta)
    if not row:
        row = await db.get_payment_by_ref(ref)
    extra = {}
    if PAYMENT_PROVIDER == "test" and row and row["status"] != "paid":
        ok, p, _newly = await db.confirm_payment(ref)
        if ok and p:
            row = p
    elif PAYMENT_PROVIDER == "hamyon" and row and row["status"] != "paid":
        try:
            import hamyon
            data = await hamyon.create_payment(ref, amount)
            extra["url"] = data.get("url") or data.get("payment_url") or data.get("checkout_url")
            extra["card"] = data.get("card")
        except Exception:
            log.exception("Hamyon create failed")
            extra["error"] = True
    return row, ref, extra


@router.message(F.text.in_(MENU_BTNS["uz"][5:6] + MENU_BTNS["ru"][5:6]))
async def menu_premium(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u:
        return
    lang = u["lang"] or "uz"
    prices = {
        "premium_week": await db.get_setting("premium_week", "15000"),
        "premium_month": await db.get_setting("premium_month", "39000"),
        "premium_vip": await db.get_setting("premium_vip", "79000"),
    }
    await message.answer(t(lang, "premium_info"), reply_markup=premium_kb(lang, prices))


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    kind = callback.data.split(":", 1)[1]
    if kind == "boost":
        amount = int(await db.get_setting("boost_price", "10000"))
        purpose = "boost"
    elif kind in ("premium_week", "premium_month", "premium_vip"):
        amount = int(await db.get_setting(kind, {"premium_week": "15000", "premium_month": "39000", "premium_vip": "79000"}[kind]))
        purpose = kind
    else:
        await callback.answer()
        return
    row, ref, extra = await _create_and_maybe_confirm(uid, purpose, amount)
    if not row or extra.get("error"):
        await callback.answer(t(lang, "payment_fail"), show_alert=True)
        return
    if row["status"] == "paid":
        msg = t(lang, "boost_ok") if purpose == "boost" else t(lang, "payment_ok")
        await callback.message.answer(msg)
        await callback.answer()
        return
    url = extra.get("url") or (PAYMENT_PAY_URL.format(ref=ref, amount=amount) if PAYMENT_PAY_URL else None)
    text = t(lang, "payment_created", amount=amount, purpose=purpose, pid=row["id"])
    if extra.get("card"):
        text += f"\n💳 Karta: <code>{extra['card']}</code>"
    await callback.message.answer(text, reply_markup=pay_confirm_kb(lang, ref, url))
    await callback.answer()
