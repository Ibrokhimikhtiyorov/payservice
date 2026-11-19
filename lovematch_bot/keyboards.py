from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup,
)
from i18n import t, MENU_BTNS


def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
    ])


def gender_kb(lang: str):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(lang, "male")), KeyboardButton(text=t(lang, "female"))]
    ], resize_keyboard=True, one_time_keyboard=True)


def main_menu_kb(lang: str):
    btns = MENU_BTNS.get(lang, MENU_BTNS["uz"])
    rows = [[KeyboardButton(text=btns[i]), KeyboardButton(text=btns[i+1])] for i in range(0, len(btns), 2)]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def profile_card_kb(lang: str, target_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "like_btn"), callback_data=f"act:like:{target_id}"),
            InlineKeyboardButton(text=t(lang, "super_btn"), callback_data=f"act:super:{target_id}"),
            InlineKeyboardButton(text=t(lang, "skip_btn"), callback_data=f"act:skip:{target_id}"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "report_btn"), callback_data=f"act:report:{target_id}"),
            InlineKeyboardButton(text=t(lang, "block_btn"), callback_data=f"act:block:{target_id}"),
        ],
    ])


def match_kb(lang: str, match_id: int, is_paid: bool, price: int):
    if is_paid:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "open_chat_btn"), callback_data=f"chat:open:{match_id}")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "pay_chat_btn", price=price), callback_data=f"pay:chat:{match_id}")]
    ])


def pay_confirm_kb(lang: str, provider_ref: str, url: str | None = None):
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="💳 To'lov havolasi / Ссылка", url=url)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish / Проверить", callback_data=f"pay:check:{provider_ref}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_kb(lang: str, prices: dict):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 hafta / неделя — {prices.get('premium_week','?')} so'm", callback_data="buy:premium_week")],
        [InlineKeyboardButton(text=f"1 oy / месяц — {prices.get('premium_month','?')} so'm", callback_data="buy:premium_month")],
        [InlineKeyboardButton(text=f"VIP — {prices.get('premium_vip','?')} so'm", callback_data="buy:premium_vip")],
        [InlineKeyboardButton(text=t(lang, "boost"), callback_data="buy:boost")],
    ])


def edit_profile_kb(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "edit_name"), callback_data="edit:name"),
         InlineKeyboardButton(text=t(lang, "edit_age"), callback_data="edit:age")],
        [InlineKeyboardButton(text=t(lang, "edit_city"), callback_data="edit:city"),
         InlineKeyboardButton(text=t(lang, "edit_photo"), callback_data="edit:photo")],
        [InlineKeyboardButton(text=t(lang, "edit_bio"), callback_data="edit:bio"),
         InlineKeyboardButton(text=t(lang, "edit_looking"), callback_data="edit:looking")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="edit:back")],
    ])


def settings_kb(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "lang"), callback_data="set:lang")],
        [InlineKeyboardButton(text=t(lang, "search_filters"), callback_data="set:filters")],
    ])


def filter_gender_kb(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "male"), callback_data="filt:g:male"),
         InlineKeyboardButton(text=t(lang, "female"), callback_data="filt:g:female")],
        [InlineKeyboardButton(text=t(lang, "any"), callback_data="filt:g:any")],
    ])


def admin_kb(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users")],
        [InlineKeyboardButton(text="💳 To'lovlar (chat)", callback_data="adm:chatpay"),
         InlineKeyboardButton(text="⭐ Premium to'lovlar", callback_data="adm:prempay")],
        [InlineKeyboardButton(text="⚠️ Shikoyatlar", callback_data="adm:reports")],
        [InlineKeyboardButton(text="🚫 Bloklash", callback_data="adm:block"),
         InlineKeyboardButton(text="✅ Blokdan olish", callback_data="adm:unblock")],
        [InlineKeyboardButton(text="📢 Reklama", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="💰 Narxlarni o'zgartirish", callback_data="adm:prices")],
    ])


def back_menu_kb(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "back"), callback_data="nav:menu")]])
