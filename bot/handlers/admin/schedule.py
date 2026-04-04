import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_kb import (
    admin_menu_keyboard,
    days_off_keyboard,
    schedule_keyboard,
    workdays_keyboard,
)
from bot.models.database import add_day_off, get_days_off, get_setting, is_bookings_open, remove_day_off, set_setting
from bot.states.booking import AdminScheduleStates
from bot.utils.datetime_helpers import parse_date
from bot.utils.texts import (
    DAY_OFF_ADD,
    DAY_OFF_ADDED,
    DAY_OFF_REASON,
    DAY_OFF_REMOVED,
    DAYS_OFF_HEADER,
    NO_DAYS_OFF,
    SCHEDULE_EDIT_BREAK,
    SCHEDULE_EDIT_END,
    SCHEDULE_EDIT_INTERVAL,
    SCHEDULE_EDIT_START,
    SCHEDULE_INFO,
    SCHEDULE_SAVED,
)

router = Router()


async def _schedule_text(db: aiosqlite.Connection) -> str:
    start = await get_setting(db, "work_start_hour") or "9"
    end = await get_setting(db, "work_end_hour") or "20"
    interval = await get_setting(db, "slot_interval_minutes") or "30"
    break_ = await get_setting(db, "break_between_minutes") or "15"
    days_str = await get_setting(db, "work_days") or "0,1,2,3,4,5"
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    days_label = " ".join(day_names[int(d)] for d in days_str.split(","))
    return SCHEDULE_INFO.format(
        start=start, end=end, days=days_label, interval=interval, break_=break_
    )


@router.callback_query(F.data == "admin:schedule")
async def schedule_menu(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    text = await _schedule_text(db)
    await call.message.edit_text(text, reply_markup=schedule_keyboard())
    await call.answer()


@router.callback_query(F.data == "admin:edit_hours")
async def edit_hours_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminScheduleStates.edit_start)
    await call.message.answer(SCHEDULE_EDIT_START)
    await call.answer()


@router.message(AdminScheduleStates.edit_start)
async def edit_hours_start_input(message: Message, state: FSMContext) -> None:
    try:
        hour = int((message.text or "").strip())
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        await message.answer(SCHEDULE_EDIT_START)
        return
    await state.update_data(work_start=hour)
    await state.set_state(AdminScheduleStates.edit_end)
    await message.answer(SCHEDULE_EDIT_END)


@router.message(AdminScheduleStates.edit_end)
async def edit_hours_end_input(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    try:
        hour = int((message.text or "").strip())
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        await message.answer(SCHEDULE_EDIT_END)
        return
    data = await state.get_data()
    if hour <= data["work_start"]:
        await message.answer("Час закінчення має бути більше ніж початок. Введіть ще раз:")
        return
    await set_setting(db, "work_start_hour", str(data["work_start"]))
    await set_setting(db, "work_end_hour", str(hour))
    await state.clear()
    await message.answer(SCHEDULE_SAVED)


@router.callback_query(F.data == "admin:edit_interval")
async def edit_interval_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminScheduleStates.edit_interval)
    await call.message.answer(SCHEDULE_EDIT_INTERVAL)
    await call.answer()


@router.message(AdminScheduleStates.edit_interval)
async def edit_interval_input(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    try:
        val = int((message.text or "").strip())
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введіть ціле число більше 0 (наприклад 30):")
        return
    await set_setting(db, "slot_interval_minutes", str(val))
    await state.clear()
    await message.answer(SCHEDULE_SAVED)


@router.callback_query(F.data == "admin:edit_break")
async def edit_break_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminScheduleStates.edit_break)
    await call.message.answer(SCHEDULE_EDIT_BREAK)
    await call.answer()


@router.message(AdminScheduleStates.edit_break)
async def edit_break_input(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    try:
        val = int((message.text or "").strip())
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введіть число 0 або більше (наприклад 15):")
        return
    await set_setting(db, "break_between_minutes", str(val))
    await state.clear()
    await message.answer(SCHEDULE_SAVED)


@router.callback_query(F.data == "admin:edit_workdays")
async def edit_workdays(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    days_str = await get_setting(db, "work_days") or "0,1,2,3,4,5"
    current = [int(d) for d in days_str.split(",")]
    await call.message.edit_text("Оберіть робочі дні:", reply_markup=workdays_keyboard(current))
    await call.answer()


@router.callback_query(F.data.startswith("admin:toggle_day:"))
async def toggle_workday(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    day = int(call.data.split(":")[-1])
    days_str = await get_setting(db, "work_days") or "0,1,2,3,4,5"
    current = [int(d) for d in days_str.split(",")]
    if day in current:
        current.remove(day)
    else:
        current.append(day)
        current.sort()
    await set_setting(db, "work_days", ",".join(map(str, current)))
    await call.message.edit_reply_markup(reply_markup=workdays_keyboard(current))
    await call.answer()


@router.callback_query(F.data == "admin:save_workdays")
async def save_workdays(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    await call.message.edit_text(SCHEDULE_SAVED, reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
    await call.answer()


@router.callback_query(F.data == "admin:days_off")
async def days_off_menu(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    days = await get_days_off(db)
    text = DAYS_OFF_HEADER if days else NO_DAYS_OFF
    await call.message.edit_text(text, reply_markup=days_off_keyboard(days))
    await call.answer()


@router.callback_query(F.data == "admin:add_dayoff")
async def add_dayoff_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminScheduleStates.add_day_off_date)
    await call.message.answer(DAY_OFF_ADD)
    await call.answer()


@router.message(AdminScheduleStates.add_day_off_date)
async def add_dayoff_date(message: Message, state: FSMContext) -> None:
    d = parse_date(message.text or "")
    if not d:
        await message.answer("Невірний формат. Введіть у форматі DD.MM.YYYY:")
        return
    await state.update_data(day_off_date=d.isoformat())
    await state.set_state(AdminScheduleStates.add_day_off_reason)
    await message.answer(DAY_OFF_REASON)


@router.message(AdminScheduleStates.add_day_off_reason)
async def add_dayoff_reason(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    reason = (message.text or "").strip()
    if reason == "-":
        reason = None
    data = await state.get_data()
    await add_day_off(db, data["day_off_date"], reason)
    await state.clear()
    days = await get_days_off(db)
    await message.answer(DAY_OFF_ADDED, reply_markup=days_off_keyboard(days))


@router.callback_query(F.data.startswith("admin:del_dayoff:"))
async def delete_dayoff(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    day_id = int(call.data.split(":")[-1])
    await remove_day_off(db, day_id)
    days = await get_days_off(db)
    text = DAYS_OFF_HEADER if days else NO_DAYS_OFF
    await call.message.edit_text(text, reply_markup=days_off_keyboard(days))
    await call.answer(DAY_OFF_REMOVED)
