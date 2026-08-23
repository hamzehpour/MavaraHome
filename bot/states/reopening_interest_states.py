from aiogram.fsm.state import State, StatesGroup


class ReopeningInterestStates(StatesGroup):
    choosing_event = State()
    confirming_name = State()
    entering_name = State()
    awaiting_phone = State()
