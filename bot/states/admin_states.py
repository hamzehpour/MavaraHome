from aiogram.fsm.state import State, StatesGroup


class AdminReviewStates(StatesGroup):
    awaiting_reject_reason = State()
    awaiting_approve_note = State()


class AdminEventStates(StatesGroup):
    awaiting_event_title = State()
    awaiting_event_icon = State()
    awaiting_calendar_type = State()
    picking_session_date = State()
    awaiting_session_count = State()
    awaiting_session_capacity = State()
    awaiting_session_time = State()
    awaiting_edit_capacity = State()
    awaiting_edit_date = State()
    awaiting_edit_time = State()
    awaiting_reservation_people_edit = State()
    picking_reservation_move_target = State()
    awaiting_event_address = State()


class AdminBroadcastStates(StatesGroup):
    choosing_audience = State()
    choosing_event_for_date = State()
    choosing_date_for_audience = State()
    awaiting_message = State()
    awaiting_confirm = State()


class DirectMessageStates(StatesGroup):
    awaiting_target = State()
    awaiting_text = State()


class AdminSettingsStates(StatesGroup):
    awaiting_new_value = State()


class StaffManagementStates(StatesGroup):
    awaiting_new_staff_id = State()
    awaiting_new_staff_role = State()
    awaiting_remove_staff_id = State()


class StaffBookingStates(StatesGroup):
    choosing_event = State()
    choosing_date = State()
    choosing_session = State()
    entering_people = State()
    entering_name = State()
    entering_phone = State()
    reviewing = State()
