import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from i18n import t, MENU_BTNS
from keyboards import settings_kb, filter_gender_kb, lang_kb, main_menu_kb
from states import SearchFilter

router = Router()
log = logging.getLogger(__name__)


@router.message(F.text.in_(MENU_BTNS["uz"][6:7] + MENU_BTNS["ru"][6:7]))
async def menu_settings(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u:
        return
    lang = u["lang"] or "uz"
    await message.answer(t(lang, "settings_title"), reply_markup=settings_kb(lang))


@router.message(F.text.in_(MENU_BTNS["uz"][7:8] + MENU_BTNS["ru"][7:8]))
async def menu_help(message: Message):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    await message.answer(t(lang, "help_text"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "set:lang")
async def set_lang(callback: CallbackQuery):
    await callback.message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())
    await callback.answer()


@router.callback_query(F.data == "set:filters")
async def set_filters(callback: CallbackQuery, state: FSMContext):
    u = await db.get_user(callback.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    await state.set_state(SearchFilter.gender)
    await callback.message.answer(t(lang, "filter_gender"), reply_markup=filter_gender_kb(lang))
    await callback.answer()


@router.callback_query(SearchFilter.gender, F.data.startswith("filt:g:"))
async def filt_gender(callback: CallbackQuery, state: FSMContext):
    u = await db.get_user(callback.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    val = callback.data.split(":")[-1]
    pref_gender = None if val == "any" else val
    await state.update_data(pref_gender=pref_gender)
    await state.set_state(SearchFilter.city)
    await callback.message.answer(t(lang, "filter_city"))
    await callback.answer()


@router.message(SearchFilter.city)
async def filt_city(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    txt = (message.text or "").strip()
    if txt.lower() in ("hammasi", "все", "all", t(lang, "all_cities").lower()):
        pref_city = None
    else:
        pref_city = txt[:60]
    await state.update_data(pref_city=pref_city)
    await state.set_state(SearchFilter.age_min)
    await message.answer(t(lang, "filter_age"))


@router.message(SearchFilter.age_min)
async def filt_age(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    lang = (u["lang"] if u else "uz") or "uz"
    txt = (message.text or "").replace(" ", "")
    amin = amax = None
    try:
        if "-" in txt:
            a, b = txt.split("-", 1)
            if a.isdigit() and b.isdigit():
                amin, amax = int(a), int(b)
        elif txt.isdigit():
            amin = amax = int(txt)
    except Exception:
        pass
    if amin is None or amax is None or amin < 18 or amax > 80 or amin > amax:
        await message.answer(t(lang, "filter_age"))
        return
    data = await state.get_data()
    await db.set_search_prefs(message.from_user.id, data.get("pref_gender"), data.get("pref_city"), amin, amax)
    await state.clear()
    await message.answer(t(lang, "filter_saved"), reply_markup=main_menu_kb(lang))
