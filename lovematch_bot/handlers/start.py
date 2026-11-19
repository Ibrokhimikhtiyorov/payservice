import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from i18n import t
from keyboards import lang_kb, main_menu_kb, gender_kb
from states import Reg

router = Router()
log = logging.getLogger(__name__)


async def _menu(message: Message, lang: str, text_key: str = "menu"):
    await message.answer(t(lang, text_key), reply_markup=main_menu_kb(lang))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    from aiogram.filters import CommandStart as _CS  # noqa
    await state.clear()
    uid = message.from_user.id
    await db.ensure_user(uid, "uz")
    u = await db.get_user(uid)
    if u and u["is_banned"]:
        lang = (u["lang"] if u else "uz") or "uz"
        await message.answer(t(lang, "banned"))
        return
    if not u or not u.get("name"):
        # new user - ask language
        await message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())
        return
    lang = u["lang"] or "uz"
    if not u["reg_done"]:
        await state.set_state(Reg.name)
        await message.answer(t(lang, "reg_start") + "\n\n" + t(lang, "reg_name"))
        return
    await _menu(message, lang, "menu")


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":", 1)[1]
    if lang not in ("uz", "ru"):
        lang = "uz"
    uid = callback.from_user.id
    await db.ensure_user(uid, lang)
    await db.set_user_lang(uid, lang)
    u = await db.get_user(uid)
    await callback.answer()
    if u and not u["reg_done"]:
        await state.set_state(Reg.name)
        await callback.message.answer(t(lang, "welcome"))
        await callback.message.answer(t(lang, "reg_name"))
    else:
        await callback.message.answer(t(lang, "menu"), reply_markup=main_menu_kb(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    from aiogram.filters import Command as _C  # noqa
    await state.clear()
    u = await db.get_user(message.from_user.id)
    if not u:
        await cmd_start(message, state)
        return
    if u["is_banned"]:
        await message.answer(t(u["lang"] or "uz", "banned"))
        return
    if not u["reg_done"]:
        await state.set_state(Reg.name)
        await message.answer(t(u["lang"] or "uz", "reg_name"))
        return
    await _menu(message, u["lang"] or "uz", "menu")


@router.message(Reg.name)
async def reg_name(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    name = (message.text or "").strip()[:50]
    if len(name) < 2:
        await message.answer(t(lang, "reg_name"))
        return
    await db.upsert_profile(message.from_user.id, name=name)
    await state.set_state(Reg.age)
    await message.answer(t(lang, "reg_age"))


@router.message(Reg.age)
async def reg_age(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(t(lang, "reg_age_invalid"))
        return
    age = int(raw)
    if age < 18 or age > 80:
        await message.answer(t(lang, "reg_age_invalid"))
        return
    await db.upsert_profile(message.from_user.id, age=age)
    await state.set_state(Reg.gender)
    await message.answer(t(lang, "reg_gender"), reply_markup=gender_kb(lang))


@router.message(Reg.gender)
async def reg_gender(message: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    txt = (message.text or "").strip()
    if txt in (t(lang, "male"), "Erkak", "Мужчина", "👨 Erkak", "👨 Мужчина"):
        g = "male"
    elif txt in (t(lang, "female"), "Ayol", "Женщина", "👩 Ayol", "👩 Женщина"):
        g = "female"
    else:
        await message.answer(t(lang, "reg_gender"), reply_markup=gender_kb(lang))
        return
    await db.upsert_profile(message.from_user.id, gender=g)
    await state.set_state(Reg.city)
    await message.answer(t(lang, "reg_city"), reply_markup=ReplyKeyboardRemove())


@router.message(Reg.city)
async def reg_city(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    city = (message.text or "").strip()[:60]
    if len(city) < 2:
        await message.answer(t(lang, "reg_city"))
        return
    await db.upsert_profile(message.from_user.id, city=city)
    await state.set_state(Reg.photo)
    await message.answer(t(lang, "reg_photo"))


@router.message(Reg.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    photo_id = message.photo[-1].file_id
    await db.upsert_profile(message.from_user.id, photo_id=photo_id)
    await state.set_state(Reg.bio)
    await message.answer(t(lang, "reg_bio"))


@router.message(Reg.photo)
async def reg_photo_invalid(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    await message.answer(t(lang, "reg_photo"))


@router.message(Reg.bio)
async def reg_bio(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    bio = (message.text or "").strip()[:500]
    await db.upsert_profile(message.from_user.id, bio=bio)
    await state.set_state(Reg.looking)
    await message.answer(t(lang, "reg_looking"))


@router.message(Reg.looking)
async def reg_looking(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    looking = (message.text or "").strip()[:300]
    await db.upsert_profile(message.from_user.id, looking_for=looking, reg_done=True)
    await state.clear()
    await message.answer(t(lang, "reg_done"), reply_markup=main_menu_kb(lang))
