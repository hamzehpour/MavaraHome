from aiogram.fsm.state import State, StatesGroup


class BankCardStates(StatesGroup):
    awaiting_number = State()
    awaiting_holder = State()
    awaiting_bank = State()
