from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    awaiting_message = State()


class SupportReplyStates(StatesGroup):
    awaiting_reply = State()
