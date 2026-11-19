import logging
import secrets
import time

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from config import PAYMENT_PAY_URL, PAYMENT_PROVIDER
from i18n import t
from keyboards import pay_confirm_kb, main_menu_kb
from states import ChatState

router = Router()
log = logging.getLogger(__name__)


async def _other_user(match_row, my_id: int):
    other_id = match_row["user_b"] if match_row["user_a"] == my_id else match_row["user_a"]
    return await db.get_user(other_id), other_id


async def _create_and_maybe_confirm(uid: int, purpose: str, amount: int, match_id: int | None, meta: str = ""):
    ref = f"lm_{purpose}_{uid}_{int(time.time())}_{secrets.token_hex(4)}"
    row = await db.create_payment(uid, purpose, amount, ref, match_id, meta)
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


@router.callback_query(F.data.startswith("pay:chat:"))
async def pay_chat(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    try:
        match_id = int(callback.data.split(":")[-1])
    except Exception:
        await callback.answer()
        return
    m = await db.get_match(match_id)
    if not m or uid not in (m["user_a"], m["user_b"]):
        await callback.answer("Not found", show_alert=True)
        return
    if m["is_paid"]:
        await callback.answer(t(lang, "already_paid"), show_alert=True)
        return
    price = int(await db.get_setting("chat_price", "5000"))
    row, ref, extra = await _create_and_maybe_confirm(uid, "chat_unlock", price, match_id)
    if not row or extra.get("error"):
        await callback.answer(t(lang, "payment_fail"), show_alert=True)
        return
    if row["status"] == "paid":
        await callback.message.answer(t(lang, "payment_ok"))
        await callback.answer()
        return
    url = extra.get("url") or (PAYMENT_PAY_URL.format(ref=ref, amount=price) if PAYMENT_PAY_URL else None)
    text = t(lang, "payment_created", amount=price, purpose="chat_unlock", pid=row["id"])
    if extra.get("card"):
        text += f"\n💳 Karta: <code>{extra['card']}</code>"
    await callback.message.answer(text, reply_markup=pay_confirm_kb(lang, ref, url))
    await callback.answer()


@router.callback_query(F.data.startswith("pay:check:"))
async def pay_check(callback: CallbackQuery):
    uid = callback.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    ref = callback.data.split(":", 2)[2]
    p = await db.get_payment_by_ref(ref)
    if not p:
        await callback.answer(t(lang, "payment_fail"), show_alert=True)
        return
    if p["status"] == "paid":
        await callback.answer(t(lang, "payment_ok"), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await callback.answer(t(lang, "payment_pending"), show_alert=True)


@router.callback_query(F.data.startswith("chat:open:"))
async def chat_open(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    try:
        match_id = int(callback.data.split(":")[-1])
    except Exception:
        await callback.answer()
        return
    m = await db.get_match(match_id)
    if not m or uid not in (m["user_a"], m["user_b"]):
        await callback.answer("Not found", show_alert=True)
        return
    if not m["is_paid"]:
        price = int(await db.get_setting("chat_price", "5000"))
        await callback.answer(t(lang, "match_locked", price=price), show_alert=True)
        return
    other, other_id = await _other_user(m, uid)
    if await db.is_blocked_either(uid, other_id):
        await callback.answer(t(lang, "banned"), show_alert=True)
        return
    await state.set_state(ChatState.active)
    await state.update_data(match_id=match_id, other_id=other_id)
    name = (other.get("name") if other else "—") or "—"
    await callback.message.answer(t(lang, "chat_opened", name=name))
    await callback.answer()


@router.message(ChatState.active, F.text)
async def chat_message(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    text = message.text or ""
    from i18n import all_menu_texts
    if text == "/menu" or text in all_menu_texts():
        await state.clear()
        await message.answer(t(lang, "menu"), reply_markup=main_menu_kb(lang))
        return
    data = await state.get_data()
    match_id = data.get("match_id")
    other_id = data.get("other_id")
    if not match_id or not other_id:
        await state.clear()
        await message.answer(t(lang, "menu"), reply_markup=main_menu_kb(lang))
        return
    m = await db.get_match(int(match_id))
    if not m or not m["is_paid"]:
        await message.answer(t(lang, "msg_blocked"))
        return
    if await db.is_blocked_either(uid, int(other_id)):
        await state.clear()
        await message.answer(t(lang, "blocked"), reply_markup=main_menu_kb(lang))
        return
    await db.add_message(int(match_id), uid, text[:2000])
    sender_name = (u.get("name") if u else "") or "—"
    try:
        await bot.send_message(int(other_id), f"💬 <b>{sender_name}:</b>\n{text}")
    except Exception:
        log.warning("failed to relay message to %s", other_id)
    await message.answer("✅")


@router.message(ChatState.active)
async def chat_non_text(message: Message, state: FSMContext):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    data = await state.get_data()
    match_id = data.get("match_id")
    other_id = data.get("other_id")
    if not match_id or not other_id:
        await state.clear()
        return
    m = await db.get_match(int(match_id))
    if not m or not m["is_paid"]:
        await message.answer(t(lang, "msg_blocked"))
        return
    if await db.is_blocked_either(uid, int(other_id)):
        await state.clear()
        return
    try:
        sender_name = (u.get("name") if u else "") or "—"
        await message.bot.send_message(int(other_id), f"💬 <b>{sender_name}:</b>")
        await message.copy_to(int(other_id))
        await db.add_message(int(match_id), uid, "[media]")
        await message.answer("✅")
    except Exception:
        log.warning("failed to relay media")
