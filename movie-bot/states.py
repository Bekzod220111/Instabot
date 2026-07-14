from aiogram.fsm.state import State, StatesGroup


class AddMovie(StatesGroup):
    waiting_for_number = State()
    waiting_for_video = State()


class Broadcast(StatesGroup):
    waiting_for_content = State()
