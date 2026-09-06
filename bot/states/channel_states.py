from aiogram.fsm.state import State, StatesGroup


class ChannelSetupStates(StatesGroup):
    awaiting_forwarded_message = State()
    awaiting_forwarded_alerts_message = State()
