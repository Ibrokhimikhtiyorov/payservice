import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from i18n import t, MENU_BTNS
from keyboards import main_menu_kb, profile_card_kb
from states import EditProfile

router = Router()
log = logging.getLogger(__name__)


def is_premium(u) -> bool:
    return bool(u and u.get("is_premium") and (u.get("premium_until") is None or u["premium_until"] > datetime.now(timezone.utc)))


def profile_text(u, lang: str, viewer: dict | None = None) -> str:
    vip = t(lang, "vip_badge") if is_premium(u) else ""
    name = u.get("name") or t(lang, "no_name")
    age = u.get("age") or "—"
    city = u.get("city") or "—"
    bio = u.get("bio") or "—"
    looking = u.get("looking_for") or "—"
    return t(lang, "card_line", vip=vip, name=name, age=age, city=city, bio=bio, looking=looking)


async def show_my_profile(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u or not u["reg_done"]:
        return
    lang = u["lang"] or "uz"
    text = t(lang, "profile_title") + "\n\n" + profile_text(u, lang)
    from keyboards import edit_profile_kb
    if u.get("photo_id"):
        await message.answer_photo(u["photo_id"], caption=text, reply_markup=edit_profile_kb(lang))
    else:
        await message.answer(text, reply_markup=edit_profile_kb(lang))


@router.message(F.text.in_(MENU_BTNS["uz"][4:5] + MENU_BTNS["ru"][4:5]))
async def menu_profile(message: Message):
    await show_my_profile(message)


@router.callback_query(F.data.startswith("edit:"))
async def cb_edit(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    u = await db.get_user(uid)
    lang = (u["lang"] if u else "uz") or "uz"
    field = callback.data.split(":", 1)[1]
    if field == "back":
        await callback.message.delete()
        await callback.message.answer(t(lang, "menu"), reply_markup=main_menu_kb(lang))
        await callback.answer()
        return
    if field == "photo":
        await state.set_state(EditProfile.waiting_value)
        await state.update_data(edit_field="photo")
        await callback.message.answer(t(lang, "edit_photo_prompt"))
    else:
        await state.set_state(EditProfile.waiting_value)
        await state.update_data(edit_field=field)
        await callback.message.answer(t(lang, "edit_prompt"))
    await callback.answer()


@router.message(EditProfile.waiting_value, F.photo)
async def edit_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    if data.get("edit_field") != "photo":
        await message.answer(t(lang, "edit_photo_prompt"))
        return
    await db.upsert_profile(message.from_user.id, photo_id=message.photo[-1].file_id)
    await state.clear()
    await message.answer(t(lang, "saved"), reply_markup=main_menu_kb(lang))


@router.message(EditProfile.waiting_value)
async def edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    val = (message.text or "").strip()
    if field == "name" and len(val) >= 2:
        await db.upsert_profile(message.from_user.id, name=val[:50])
    elif field == "age" and val.isdigit() and 18 <= int(val) <= 80:
        await db.upsert_profile(message.from_user.id, age=int(val))
    elif field == "city" and len(val) >= 2:
        await db.upsert_profile(message.from_user.id, city=val[:60])
    elif field == "bio":
        await db.upsert_profile(message.from_user.id, bio=val[:500])
    elif field == "looking":
        await db.upsert_profile(message.from_user.id, looking_for=val[:300])
    else:
        await message.answer(t(lang, "edit_prompt"))
        return
    await state.clear()
    await message.answer(t(lang, "saved"), reply_markup=main_menu_kb(lang))
