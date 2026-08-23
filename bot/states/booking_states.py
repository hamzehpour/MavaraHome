from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_event = State()
    choosing_date = State()
    choosing_session = State()
    choosing_people = State()
    choosing_for_whom = State()
    entering_attendee_name = State()
    entering_attendee_phone = State()
    entering_name = State()
    entering_phone = State()
    reviewing = State()
    awaiting_receipt = State()
