import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from i18n import t, MENU_BTNS
from keyboards import main_menu_kb, match_kb, profile_card_kb
from handlers.discovery import card_text, send_profile

router = Router()
log = logging.getLogger(__name__)


def is_premium(u) -> bool:
    return bool(u and u.get("is_premium") and (u.get("premium_until") is None or u["premium_until"] > datetime.now(timezone.utc)))


@router.message(F.text.in_(MENU_BTNS["uz"][1:2] + MENU_BTNS["ru"][1:2]))
async def menu_liked_me(message: Message, bot: Bot):
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("reg_done"):
        return
    lang = u["lang"] or "uz"
    if not is_premium(u):
        await message.answer(t(lang, "liked_premium_only"), reply_markup=main_menu_kb(lang))
        return
    rows = await db.who_liked_me(message.from_user.id)
    if not rows:
        await message.answer(t(lang, "liked_empty"), reply_markup=main_menu_kb(lang))
        return
    for r in rows[:15]:
        await send_profile(bot, message.from_user.id, dict(r), lang, reply_markup=profile_card_kb(lang, r["tg_id"]))


@router.message(F.text.in_(MENU_BTNS["uz"][2:3] + MENU_BTNS["ru"][2:3]))
async def menu_matches(message: Message, bot: Bot):
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("reg_done"):
        return
    lang = u["lang"] or "uz"
    rows = await db.get_matches(message.from_user.id)
    if not rows:
        await message.answer(t(lang, "matches_empty"), reply_markup=main_menu_kb(lang))
        return
    price = int(await db.get_setting("chat_price", "5000"))
    for m in rows[:20]:
        title = f"💌 {m['name'] or '—'}, {m.get('age') or '—'} — {m.get('city') or '—'}"
        status = "✅" if m["is_paid"] else "🔒"
        text = f"{status} {title}"
        kb = match_kb(lang, m["id"], bool(m["is_paid"]), price)
        if m.get("photo_id"):
            try:
                await bot.send_photo(message.from_user.id, m["photo_id"], caption=text, reply_markup=kb)
                continue
            except Exception:
                pass
        await message.answer(text, reply_markup=kb)


@router.message(F.text.in_(MENU_BTNS["uz"][3:4] + MENU_BTNS["ru"][3:4]))
async def menu_chats(message: Message, bot: Bot):
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("reg_done"):
        return
    lang = u["lang"] or "uz"
    rows = await db.get_matches(message.from_user.id)
    paid = [m for m in rows if m["is_paid"]]
    if not paid:
        await message.answer(t(lang, "chat_list_empty"), reply_markup=main_menu_kb(lang))
        return
    kb_rows = []
    for m in paid[:30]:
        name = m.get("name") or "—"
        kb_rows.append([InlineKeyboardButton(text=f"💬 {name}", callback_data=f"chat:open:{m['id']}")])
    await message.answer(t(lang, "choose_chat"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
