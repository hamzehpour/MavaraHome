from aiogram.fsm.state import State, StatesGroup


class ResendReceiptStates(StatesGroup):
    # Buyer self-service resubmission from "رزروهای من" for a reservation
    # the admin marked needs_correction (see handlers/common.py's
    # my_reservations() and its resubmit_correction:<id> callback).
    awaiting_correction_receipt = State()
