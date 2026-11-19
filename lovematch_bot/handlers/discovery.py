import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from i18n import t, MENU_BTNS
from keyboards import profile_card_kb, main_menu_kb
from states import ChatState

router = Router()
log = logging.getLogger(__name__)


def _val(row, key, default=""):
    if row is None:
        return default
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


def is_premium(u) -> bool:
    pu = _val(u, "premium_until", None)
    return bool(u and _val(u, "is_premium", False) and (pu is None or pu > datetime.now(timezone.utc)))


def card_text(u, lang: str) -> str:
    d = dict(u) if u is not None else {}
    vip = t(lang, "vip_badge") if is_premium(d) else ""
    name = d.get("name") or t(lang, "no_name")
    age = d.get("age") or "—"
    city = d.get("city") or "—"
    bio = d.get("bio") or "—"
    looking = d.get("looking_for") or "—"
    return t(lang, "card_line", vip=vip, name=name, age=age, city=city, bio=bio, looking=looking)


async def send_profile(bot_or_msg, chat_id: int, profile: dict, lang: str, *, reply_markup=None):
    text = card_text(profile, lang)
    bot = bot_or_msg if isinstance(bot_or_msg, Bot) else bot_or_msg.bot
    if profile.get("photo_id"):
        await bot.send_photo(chat_id, profile["photo_id"], caption=text, reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def next_card(message: Message, bot: Bot):
    u = await db.get_user(message.from_user.id)
    if not u or not u["reg_done"]:
        return
    lang = u["lang"] or "uz"
    if u["is_banned"]:
        await message.answer(t(lang, "banned"))
        return
    p = await db.get_next_profile(message.from_user.id)
    if not p:
        await message.answer(t(lang, "no_profiles"), reply_markup=main_menu_kb(lang))
        return
    await send_profile(bot, message.from_user.id, dict(p), lang, reply_markup=profile_card_kb(lang, p["tg_id"]))


@router.message(F.text.in_(MENU_BTNS["uz"][0:1] + MENU_BTNS["ru"][0:1]))
async def menu_find(message: Message, bot: Bot):
    await next_card(message, bot)


@router.callback_query(F.data.startswith("act:"))
async def cb_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    uid = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, action, tid_s = parts
    if not tid_s.lstrip("-").isdigit():
        await callback.answer()
        return
    target_id = int(tid_s)
    u = await db.get_user(uid)
    if not u or not u.get("reg_done"):
        await callback.answer()
        return
    lang = u["lang"] or "uz"

    if action == "skip":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer(t(lang, "skipped"))
        p = await db.get_next_profile(uid)
        if p:
            await send_profile(bot, uid, dict(p), lang, reply_markup=profile_card_kb(lang, p["tg_id"]))
        else:
            await bot.send_message(uid, t(lang, "no_profiles"), reply_markup=main_menu_kb(lang))
        return

    if action in ("like", "super"):
        can = await db.can_like(uid)
        if not can and action == "like":
            await callback.answer(t(lang, "limit_likes"), show_alert=True)
            return
        await db.inc_like(uid)
        is_super = action == "super"
        try:
            new_match = await db.add_like(uid, target_id, is_super=is_super)
        except Exception:
            log.exception("add_like failed")
            new_match = False
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer(t(lang, "super_liked" if is_super else "liked"))
        if new_match:
            me = await db.get_user(uid)
            other = await db.get_user(target_id)
            other_lang = (other["lang"] if other else "uz") or "uz"
            other_name = (other["name"] if other and other["name"] else "—")
            my_name = (me["name"] if me and me["name"] else "—")
            try:
                await bot.send_message(uid, t(lang, "its_match", name=other_name))
            except Exception:
                pass
            try:
                await bot.send_message(target_id, t(other_lang, "its_match", name=my_name))
            except Exception:
                pass
        p = await db.get_next_profile(uid)
        if p:
            await send_profile(bot, uid, dict(p), lang, reply_markup=profile_card_kb(lang, p["tg_id"]))
        else:
            await bot.send_message(uid, t(lang, "no_profiles"), reply_markup=main_menu_kb(lang))
        return

    if action == "report":
        await state.set_state(ChatState.report_reason)
        await state.update_data(report_target=target_id)
        await callback.message.answer(t(lang, "report_reason"))
        await callback.answer()
        return

    if action == "block":
        await db.add_block(uid, target_id)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer(t(lang, "blocked"))
        p = await db.get_next_profile(uid)
        if p:
            await send_profile(bot, uid, dict(p), lang, reply_markup=profile_card_kb(lang, p["tg_id"]))
        else:
            await bot.send_message(uid, t(lang, "no_profiles"), reply_markup=main_menu_kb(lang))
        return

    await callback.answer()


@router.message(ChatState.report_reason)
async def handle_report(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    data = await state.get_data()
    target = data.get("report_target")
    reason = (message.text or "").strip()[:1000]
    if target:
        try:
            await db.add_report(message.from_user.id, int(target), reason or "-")
        except Exception:
            log.exception("add_report failed")
    await state.clear()
    await message.answer(t(lang, "reported"), reply_markup=main_menu_kb(lang))
