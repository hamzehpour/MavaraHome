from aiogram.fsm.state import State, StatesGroup


class OwnerPasscodeStates(StatesGroup):
    awaiting_new_passcode = State()


class AddOwnerStates(StatesGroup):
    awaiting_target = State()
    awaiting_passcode = State()
