import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from config import ADMIN_IDS
from i18n import t
from keyboards import admin_kb, main_menu_kb
from states import AdminState

router = Router()
log = logging.getLogger(__name__)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def _guard(message_or_cb, uid: int, lang: str) -> bool:
    if not is_admin(uid):
        text = t(lang, "admin_only")
        if isinstance(message_or_cb, Message):
            await message_or_cb.answer(text)
        else:
            await message_or_cb.answer(text, show_alert=True)
        return False
    return True


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    if not await _guard(message, message.from_user.id, lang):
        return
    await message.answer(t(lang, "admin_panel"), reply_markup=admin_kb(lang))


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(callback: CallbackQuery, state: FSMContext):
    u = await db.get_user(callback.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    if not await _guard(callback, callback.from_user.id, lang):
        return
    action = callback.data.split(":", 1)[1]

    if action == "stats":
        s = await db.stats()
        text = (
            "📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"✅ Faol (7 kun): <b>{s['active']}</b>\n"
            f"💌 Matchlar: <b>{s['matches']}</b>\n"
            f"💰 Jami tushum: <b>{s['revenue']}</b> so'm\n"
            f"💬 Chat to'lovlari: <b>{s['chat_pay']}</b> so'm\n"
            f"⭐ Premium to'lovlari: <b>{s['prem_pay']}</b> so'm"
        )
        await callback.message.answer(text)
    elif action == "users":
        rows = await db.list_users(30)
        if not rows:
            await callback.message.answer("Foydalanuvchilar yo'q.")
        else:
            lines = ["👥 <b>Oxirgi foydalanuvchilar</b>"]
            for r in rows:
                flag = "🚫" if r["is_banned"] else ("⭐" if r["is_premium"] else "•")
                lines.append(f"{flag} <code>{r['tg_id']}</code> — {r['name'] or '-'} ({r.get('age') or '-'}) {r.get('city') or ''}")
            await callback.message.answer("\n".join(lines))
    elif action == "chatpay":
        rows = await db.list_payments(50)
        rows = [r for r in rows if r["purpose"] == "chat_unlock"]
        if not rows:
            await callback.message.answer("Chat to'lovlari yo'q.")
        else:
            lines = ["💬 <b>Chat to'lovlari</b>"]
            for r in rows[:30]:
                st = "✅" if r["status"] == "paid" else "⏳"
                lines.append(f"{st} #{r['id']} uid:<code>{r['tg_id']}</code> {r['amount']} so'm ({r['status']})")
            await callback.message.answer("\n".join(lines))
    elif action == "prempay":
        rows = await db.list_payments(50)
        rows = [r for r in rows if (r["purpose"] or "").startswith("premium_") or r["purpose"] == "boost"]
        if not rows:
            await callback.message.answer("Premium/boost to'lovlari yo'q.")
        else:
            lines = ["⭐ <b>Premium/Boost to'lovlari</b>"]
            for r in rows[:30]:
                st = "✅" if r["status"] == "paid" else "⏳"
                lines.append(f"{st} #{r['id']} uid:<code>{r['tg_id']}</code> {r['purpose']} {r['amount']} so'm ({r['status']})")
            await callback.message.answer("\n".join(lines))
    elif action == "reports":
        rows = await db.list_reports(30)
        if not rows:
            await callback.message.answer("Shikoyatlar yo'q.")
        else:
            lines = ["⚠️ <b>Shikoyatlar</b>"]
            for r in rows:
                lines.append(f"#{r['id']} {r['reporter_id']} → {r['reported_id']}: { (r['reason'] or '')[:80] }")
            await callback.message.answer("\n".join(lines))
    elif action == "block":
        await state.set_state(AdminState.block_user)
        await callback.message.answer("Bloklash uchun foydalanuvchi tg_id yuboring:")
    elif action == "unblock":
        await state.set_state(AdminState.unblock_user)
        await callback.message.answer("Blokdan olish uchun foydalanuvchi tg_id yuboring:")
    elif action == "broadcast":
        await state.set_state(AdminState.broadcast)
        await callback.message.answer("Reklama/xabar matnini yuboring (barcha foydalanuvchilarga yuboriladi):")
    elif action == "prices":
        await state.set_state(AdminState.set_price_key)
        await callback.message.answer(
            "Narx kalitini yuboring:\n"
            "<code>chat_price</code>, <code>premium_week</code>, <code>premium_month</code>, <code>premium_vip</code>, <code>boost_price</code>"
        )
    await callback.answer()


@router.message(AdminState.block_user)
async def adm_block(message: Message, state: FSMContext):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    if not is_admin(uid):
        return
    txt = (message.text or "").strip()
    if not txt.lstrip("-").isdigit():
        await message.answer("Raqam (tg_id) yuboring.")
        return
    await db.set_banned(int(txt), True)
    await state.clear()
    await message.answer(f"✅ {txt} bloklandi.", reply_markup=main_menu_kb(lang))


@router.message(AdminState.unblock_user)
async def adm_unblock(message: Message, state: FSMContext):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    if not is_admin(uid):
        return
    txt = (message.text or "").strip()
    if not txt.lstrip("-").isdigit():
        await message.answer("Raqam (tg_id) yuboring.")
        return
    await db.set_banned(int(txt), False)
    await state.clear()
    await message.answer(f"✅ {txt} blokdan olindi.", reply_markup=main_menu_kb(lang))


@router.message(AdminState.broadcast)
async def adm_broadcast(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    if not is_admin(uid):
        return
    text = message.text or message.caption or ""
    if not text and not message.photo:
        await message.answer("Matn yoki rasm yuboring.")
        return
    await state.clear()
    rows = await db.fetch("SELECT tg_id FROM users")
    ok = fail = 0
    for r in rows:
        try:
            await bot.copy_message(r["tg_id"], message.chat.id, message.message_id)
            ok += 1
        except Exception:
            fail += 1
    await message.answer(f"📢 Yuborildi: {ok}, xato: {fail}", reply_markup=main_menu_kb(lang))


@router.message(AdminState.set_price_key)
async def adm_price_key(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not is_admin(uid):
        return
    key = (message.text or "").strip()
    allowed = {"chat_price", "premium_week", "premium_month", "premium_vip", "boost_price"}
    if key not in allowed:
        await message.answer("Noto'g'ri kalit. Qaytadan yuboring.")
        return
    await state.update_data(price_key=key)
    await state.set_state(AdminState.set_price_value)
    cur = await db.get_setting(key, "")
    await message.answer(f"{key} uchun yangi narxni (so'm) yuboring. Hozirgi: {cur}")


@router.message(AdminState.set_price_value)
async def adm_price_value(message: Message, state: FSMContext):
    uid = message.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    if not is_admin(uid):
        return
    val = (message.text or "").strip().replace(" ", "")
    if not val.isdigit():
        await message.answer("Faqat raqam yuboring.")
        return
    data = await state.get_data()
    key = data.get("price_key")
    await db.set_setting(key, val)
    await state.clear()
    await message.answer(f"✅ {key} = {val} so'm saqlandi.", reply_markup=main_menu_kb(lang))
