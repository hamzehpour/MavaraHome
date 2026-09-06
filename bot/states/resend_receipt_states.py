from aiogram.fsm.state import State, StatesGroup


class ResendReceiptStates(StatesGroup):
    awaiting_new_receipt = State()
    # Buyer self-service resubmission from "رزروهای من" for a reservation
    # the admin marked needs_correction (see handlers/common.py's
    # my_reservations() and its resubmit:<id> callback) — kept separate
    # from awaiting_new_receipt above since that one is specific to the
    # awaiting_buyer_confirmation dispute flow (a different starting
    # status, see reservation_service.submit_receipt()'s docstring).
    awaiting_correction_receipt = State()
