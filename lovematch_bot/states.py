from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    photo = State()
    bio = State()
    looking = State()


class EditProfile(StatesGroup):
    waiting_value = State()


class SearchFilter(StatesGroup):
    gender = State()
    city = State()
    age_min = State()
    age_max = State()


class ChatState(StatesGroup):
    active = State()
    report_reason = State()


class AdminState(StatesGroup):
    broadcast = State()
    block_user = State()
    unblock_user = State()
    set_price_key = State()
    set_price_value = State()
