from aiogram.fsm.state import State, StatesGroup


class DisputeStates(StatesGroup):
    awaiting_buyer_explanation = State()


class DisputeAgainStates(StatesGroup):
    awaiting_new_reason = State()
