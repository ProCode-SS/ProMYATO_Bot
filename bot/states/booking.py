from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    select_service = State()
    select_date = State()
    select_time = State()
    confirm = State()


class MyBookingsStates(StatesGroup):
    view = State()
    confirm_cancel = State()


class AdminServiceStates(StatesGroup):
    add_name = State()
    add_duration = State()
    add_price = State()
    add_description = State()


class AdminScheduleStates(StatesGroup):
    edit_start = State()
    edit_end = State()
    edit_interval = State()
    edit_break = State()
    add_day_off_date = State()
    add_day_off_reason = State()


class AdminBookingStates(StatesGroup):
    select_service = State()
    enter_date = State()
    select_time = State()
    enter_client_name = State()
    enter_client_phone = State()
    confirm = State()
