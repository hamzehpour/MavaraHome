from aiogram.fsm.state import State, StatesGroup


class TicketVerifyStates(StatesGroup):
    awaiting_qr_payload = State()
