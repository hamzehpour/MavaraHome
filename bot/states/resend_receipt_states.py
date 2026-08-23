from aiogram.fsm.state import State, StatesGroup


class ResendReceiptStates(StatesGroup):
    awaiting_new_receipt = State()
