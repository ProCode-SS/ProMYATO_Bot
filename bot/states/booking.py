from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    enter_first_name = State()
    enter_last_name = State()
    wait_phone = State()


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


class AdminVIPStates(StatesGroup):
    add_by_phone = State()
    search_by_name = State()
    confirm_add = State()


class AdminVIPBookingStates(StatesGroup):
    select_client = State()
    select_service = State()
    enter_time = State()
    select_dates = State()
    confirm = State()
