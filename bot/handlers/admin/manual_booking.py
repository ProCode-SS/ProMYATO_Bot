from datetime import date, datetime, time, timedelta

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_kb import admin_menu_keyboard
from bot.keyboards.client_kb import confirm_keyboard, dates_keyboard, services_keyboard, times_keyboard
from bot.models.database import get_active_services, get_service, get_setting, is_bookings_open, upsert_virtual_client
from bot.services.booking_service import (
    create_new_booking,
    get_admin_only_dates,
    get_admin_only_slots,
    get_available_dates,
    get_available_slots,
)
from bot.services.calendar_service import CalendarService
from bot.services.reminder_service import ReminderService
from bot.states.booking import AdminBookingStates
from bot.utils.datetime_helpers import (
    format_date_uk,
    format_time,
    kyiv_now,
    make_kyiv_dt,
    utc_to_kyiv,
)
from bot.utils.texts import (
    ADMIN_BOOKING_CONFIRM,
    ADMIN_BOOKING_CREATED,
    ADMIN_BOOKING_ENTER_NAME,
    ADMIN_BOOKING_ENTER_PHONE,
    ADMIN_BOOKING_SELECT_SERVICE,
    ADMIN_MANUAL_BOOKING_NOTIFY,
    ERROR_GOOGLE_CALENDAR,
    MONTHS_UK,
    NO_DATES_AVAILABLE,
    NO_SLOTS_AVAILABLE,
    SELECT_DATE,
    URGENT_BOOKING_ADMIN,
)

router = Router()


@router.callback_query(F.data == "admin:new_booking")
async def new_booking_start(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    services = await get_active_services(db, for_admin=True)
    if not services:
        await call.answer("Спочатку додайте послуги.", show_alert=True)
        return
    await state.set_state(AdminBookingStates.select_service)
    await call.message.edit_text(
        ADMIN_BOOKING_SELECT_SERVICE, reply_markup=services_keyboard(services, back_callback="admin:menu")
    )
    await call.answer()


@router.callback_query(AdminBookingStates.select_service, F.data.startswith("svc:"))
async def admin_select_service(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection, calendar: CalendarService
) -> None:
    service_id = int(call.data.split(":")[1])
    service = await get_service(db, service_id)
    if not service:
        await call.answer("Послугу не знайдено.", show_alert=True)
        return

    now = kyiv_now()
    from_date = now.date()
    to_date = from_date + timedelta(days=60)
    admin_only = bool(service.get("admin_only"))

    if admin_only:
        available_dates = get_admin_only_dates(from_date, to_date)
        await call.answer()
    else:
        await call.message.edit_text("Завантажую доступні дати...")
        await call.answer()
        try:
            available_dates = await get_available_dates(
                db, calendar, from_date, to_date, service["duration_minutes"]
            )
        except Exception:
            await call.message.edit_text(ERROR_GOOGLE_CALENDAR, reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
            await state.clear()
            return
        if not available_dates:
            await call.message.edit_text(NO_DATES_AVAILABLE, reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
            await state.clear()
            return

    year, month = now.year, now.month
    await state.update_data(
        service_id=service_id,
        admin_only=admin_only,
        year=year,
        month=month,
        available_dates=[d.isoformat() for d in available_dates],
    )
    await state.set_state(AdminBookingStates.enter_date)
    await call.message.edit_text(
        SELECT_DATE,
        reply_markup=dates_keyboard(available_dates, year, month, has_prev=False),
    )


@router.callback_query(AdminBookingStates.enter_date, F.data.startswith("month:"))
async def admin_navigate_month(call: CallbackQuery, state: FSMContext) -> None:
    direction = int(call.data.split(":")[1])
    data = await state.get_data()
    year, month = data["year"], data["month"]

    month += direction
    if month > 12:
        month, year = 1, year + 1
    elif month < 1:
        month, year = 12, year - 1

    await state.update_data(year=year, month=month)
    now = kyiv_now()
    available_dates = {date.fromisoformat(s) for s in data["available_dates"]}
    has_prev = (year, month) > (now.year, now.month)
    await call.message.edit_reply_markup(
        reply_markup=dates_keyboard(available_dates, year, month, has_prev=has_prev)
    )
    await call.answer()


@router.callback_query(AdminBookingStates.enter_date, F.data.startswith("date:"))
async def admin_select_date(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
) -> None:
    date_str = call.data.split(":")[1]
    selected_date = date.fromisoformat(date_str)
    data = await state.get_data()
    service = await get_service(db, data["service_id"])

    if data.get("admin_only"):
        interval = int(await get_setting(db, "slot_interval_minutes") or "30")
        slots = get_admin_only_slots(selected_date, interval, service["duration_minutes"])
    else:
        slots = await get_available_slots(db, calendar, selected_date, service["duration_minutes"])
    if not slots:
        await call.answer(NO_SLOTS_AVAILABLE, show_alert=True)
        return

    await state.update_data(selected_date=date_str)
    await state.set_state(AdminBookingStates.select_time)
    date_label = format_date_uk(selected_date, MONTHS_UK)
    await call.message.edit_text(
        f"Слоти на {date_label}:",
        reply_markup=times_keyboard(slots, date_str),
    )
    await call.answer()


@router.callback_query(AdminBookingStates.select_time, F.data.startswith("time:"))
async def admin_select_time(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    time_str = call.data.split(":", 1)[1]
    h, m = map(int, time_str.split(":"))
    selected_time = time(h, m)

    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected_date = date.fromisoformat(data["selected_date"])
    end_dt = make_kyiv_dt(selected_date, selected_time) + timedelta(
        minutes=service["duration_minutes"]
    )

    await state.update_data(selected_time=time_str)
    await state.set_state(AdminBookingStates.enter_client_name)
    await call.message.edit_text(
        f"Обрано: {format_date_uk(selected_date, MONTHS_UK)}, "
        f"{time_str} - {format_time(end_dt.time())}\n\n"
        + ADMIN_BOOKING_ENTER_NAME
    )
    await call.answer()


@router.message(AdminBookingStates.enter_client_name)
async def admin_enter_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(ADMIN_BOOKING_ENTER_NAME)
        return
    await state.update_data(client_name=name)
    await state.set_state(AdminBookingStates.enter_client_phone)
    await message.answer(ADMIN_BOOKING_ENTER_PHONE)


@router.message(AdminBookingStates.enter_client_phone)
async def admin_enter_phone(message: Message, state: FSMContext, db: aiosqlite.Connection) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer(ADMIN_BOOKING_ENTER_PHONE)
        return

    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected_date = date.fromisoformat(data["selected_date"])
    h, m = map(int, data["selected_time"].split(":"))
    selected_time = time(h, m)
    end_dt = make_kyiv_dt(selected_date, selected_time) + timedelta(
        minutes=service["duration_minutes"]
    )

    await state.update_data(client_phone=phone)
    await state.set_state(AdminBookingStates.confirm)
    await message.answer(
        ADMIN_BOOKING_CONFIRM.format(
            name=data["client_name"],
            phone=phone,
            service=service["name"],
            duration=service["duration_minutes"],
            date=format_date_uk(selected_date, MONTHS_UK),
            time_start=data["selected_time"],
            time_end=format_time(end_dt.time()),
        ),
        reply_markup=confirm_keyboard(back_callback="confirm:no"),
    )


@router.callback_query(AdminBookingStates.confirm, F.data == "confirm:yes")
async def admin_confirm_booking(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    admin_ids: list[int],
) -> None:
    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected_date = date.fromisoformat(data["selected_date"])
    h, m = map(int, data["selected_time"].split(":"))
    selected_time = time(h, m)

    client_id = await upsert_virtual_client(db, data["client_name"], data["client_phone"])

    booking_id = await create_new_booking(
        db, calendar, client_id, service, selected_date, selected_time,
        skip_availability_check=bool(data.get("admin_only")),
    )
    if not booking_id:
        await call.message.edit_text(
            "Цей час вже зайнятий. Оберіть інший.", reply_markup=admin_menu_keyboard(await is_bookings_open(db))
        )
        await state.clear()
        await call.answer()
        return

    from bot.models.database import get_booking
    from bot.utils.datetime_helpers import utc_to_kyiv
    booking = await get_booking(db, booking_id)
    start_utc = datetime.fromisoformat(booking["start_time"])
    reminder_service.schedule_reminders(booking_id, start_utc)

    date_label = format_date_uk(selected_date, MONTHS_UK)
    notify_text = ADMIN_MANUAL_BOOKING_NOTIFY.format(
        client=data["client_name"],
        service=service["name"],
        date=date_label,
        time=data["selected_time"],
        phone=data["client_phone"],
    )
    for aid in admin_ids:
        await bot.send_message(chat_id=aid, text=notify_text)

    # Urgent notification if booking is within 30 minutes
    start_kyiv = utc_to_kyiv(start_utc)
    minutes_until = (start_kyiv - kyiv_now()).total_seconds() / 60
    if minutes_until <= 30:
        urgent_text = URGENT_BOOKING_ADMIN.format(
            client=data["client_name"],
            service=service["name"],
            date=date_label,
            time=data["selected_time"],
            phone=data["client_phone"],
        )
        for aid in admin_ids:
            await bot.send_message(chat_id=aid, text=urgent_text)

    await call.message.edit_text(ADMIN_BOOKING_CREATED, reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
    await state.clear()
    await call.answer()


@router.callback_query(AdminBookingStates.confirm, F.data == "confirm:no")
async def admin_cancel_new_booking(call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection) -> None:
    await state.clear()
    await call.message.edit_text("Скасовано.", reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
    await call.answer()
