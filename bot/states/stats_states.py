from aiogram.fsm.state import State, StatesGroup


class StatsStates(StatesGroup):
    picking_from_date = State()
    picking_to_date = State()
