from datetime import date, datetime, time, timedelta

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.keyboards.admin_kb import offhours_approve_keyboard
from bot.keyboards.client_kb import (
    confirm_keyboard,
    dates_keyboard,
    main_menu_keyboard,
    services_keyboard,
    times_keyboard,
)
from bot.models.database import (
    create_booking,
    get_active_services,
    get_client_by_telegram_id,
    get_service,
    get_setting,
    is_bookings_open,
)
from bot.services.booking_service import (
    create_new_booking,
    get_available_dates,
    get_available_slots,
)
from bot.services.calendar_service import CalendarService
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.states.booking import BookingStates
from bot.utils.datetime_helpers import (
    format_date_uk,
    format_time,
    generate_time_slots,
    kyiv_now,
    kyiv_to_utc,
    make_kyiv_dt,
    utc_to_kyiv,
)
from bot.utils.datetime_helpers import kyiv_now
from bot.utils.texts import (
    BOOKING_CONFIRM,
    BOOKING_CONFIRMED,
    BOOKINGS_CLOSED,
    ERROR_GENERAL,
    ERROR_GOOGLE_CALENDAR,
    ICS_FILENAME,
    MONTHS_UK,
    NEW_BOOKING_ADMIN,
    NO_DATES_AVAILABLE,
    NO_SLOTS_AVAILABLE,
    OFFHOURS_BOOKING_CONFIRM,
    OFFHOURS_PENDING_SENT,
    OFFHOURS_REQUEST_ADMIN,
    SELECT_DATE,
    SELECT_SERVICE,
    SELECT_TIME,
    SLOT_TAKEN,
    URGENT_BOOKING_ADMIN,
)

router = Router()


@router.callback_query(F.data == "menu:book")
async def start_booking(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    if not await is_bookings_open(db):
        await call.answer(BOOKINGS_CLOSED, show_alert=True)
        return
    services = await get_active_services(db)
    if not services:
        await call.answer("Послуги ще не додані.", show_alert=True)
        return
    await state.set_state(BookingStates.select_service)
    await call.message.edit_text(SELECT_SERVICE, reply_markup=services_keyboard(services))
    await call.answer()


@router.callback_query(BookingStates.select_service, F.data.startswith("svc:"))
async def select_service(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
) -> None:
    service_id = int(call.data.split(":")[1])
    service = await get_service(db, service_id)
    if not service:
        await call.answer("Послугу не знайдено.", show_alert=True)
        return

    now = kyiv_now()
    from_date = now.date()
    to_date = from_date + timedelta(days=60)

    requires_approval = bool(service.get("requires_approval"))

    if requires_approval:
        # All dates available — no calendar check needed
        await call.answer()
        all_dates: set[date] = set()
        current = from_date
        while current <= to_date:
            all_dates.add(current)
            current += timedelta(days=1)
        available_dates = all_dates
    else:
        await call.message.edit_text("Завантажую доступні дати...")
        await call.answer()
        try:
            available_dates = await get_available_dates(
                db, calendar, from_date, to_date, service["duration_minutes"]
            )
        except Exception:
            await call.message.edit_text(ERROR_GOOGLE_CALENDAR, reply_markup=main_menu_keyboard())
            await state.clear()
            return

        if not available_dates:
            await call.message.edit_text(NO_DATES_AVAILABLE, reply_markup=main_menu_keyboard())
            await state.clear()
            return

    year, month = now.year, now.month
    await state.update_data(
        service_id=service_id,
        requires_approval=requires_approval,
        year=year,
        month=month,
        available_dates=[d.isoformat() for d in available_dates],
    )
    await state.set_state(BookingStates.select_date)
    await call.message.edit_text(
        SELECT_DATE,
        reply_markup=dates_keyboard(available_dates, year, month, has_prev=False),
    )


@router.callback_query(BookingStates.select_date, F.data.startswith("month:"))
async def navigate_month(call: CallbackQuery, state: FSMContext) -> None:
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


@router.callback_query(BookingStates.select_date, F.data.startswith("date:"))
async def select_date(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
) -> None:
    date_str = call.data.split(":")[1]
    selected_date = date.fromisoformat(date_str)
    data = await state.get_data()
    service = await get_service(db, data["service_id"])

    if data.get("requires_approval"):
        interval = int(await get_setting(db, "slot_interval_minutes") or "30")
        slots = generate_time_slots(
            selected_date, 7, 23, interval, service["duration_minutes"], 0
        )
    else:
        slots = await get_available_slots(db, calendar, selected_date, service["duration_minutes"])

    if not slots:
        await call.answer(NO_SLOTS_AVAILABLE, show_alert=True)
        return

    await state.update_data(selected_date=date_str)
    await state.set_state(BookingStates.select_time)
    date_label = format_date_uk(selected_date, MONTHS_UK)
    await call.message.edit_text(
        SELECT_TIME.format(date=date_label),
        reply_markup=times_keyboard(slots, date_str),
    )
    await call.answer()


@router.callback_query(BookingStates.select_time, F.data.startswith("time:"))
async def select_time(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    time_str = call.data.split(":", 1)[1]
    h, m = map(int, time_str.split(":"))
    selected_time = time(h, m)

    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected_date = date.fromisoformat(data["selected_date"])

    start_dt = make_kyiv_dt(selected_date, selected_time)
    end_dt = start_dt + timedelta(minutes=service["duration_minutes"])
    price_str = f"💰 {service['price']}₴" if service.get("price") else "Ціна уточнюється"

    if data.get("requires_approval"):
        text = OFFHOURS_BOOKING_CONFIRM.format(
            service=service["name"],
            duration=service["duration_minutes"],
            date=format_date_uk(selected_date, MONTHS_UK),
            time_start=format_time(selected_time),
            time_end=format_time(end_dt.time()),
            price=price_str,
        )
    else:
        text = BOOKING_CONFIRM.format(
            service=service["name"],
            duration=service["duration_minutes"],
            date=format_date_uk(selected_date, MONTHS_UK),
            time_start=format_time(selected_time),
            time_end=format_time(end_dt.time()),
            price=price_str,
        )

    await state.update_data(selected_time=time_str)
    await state.set_state(BookingStates.confirm)
    await call.message.edit_text(text, reply_markup=confirm_keyboard())
    await call.answer()


@router.callback_query(BookingStates.confirm, F.data == "confirm:yes")
async def confirm_booking(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    admin_ids: list[int],
    therapist_name: str,
    location: str,
) -> None:
    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected_date = date.fromisoformat(data["selected_date"])
    h, m = map(int, data["selected_time"].split(":"))
    selected_time = time(h, m)

    client = await get_client_by_telegram_id(db, call.from_user.id)
    if not client:
        await call.answer(ERROR_GENERAL, show_alert=True)
        return

    # --- Off-hours: create pending booking, notify admin ---
    if data.get("requires_approval"):
        start_dt = make_kyiv_dt(selected_date, selected_time)
        end_dt = start_dt + timedelta(minutes=service["duration_minutes"])

        booking_id = await create_booking(
            db,
            client_id=client["id"],
            service_id=service["id"],
            start_time=kyiv_to_utc(start_dt).isoformat(),
            end_time=kyiv_to_utc(end_dt).isoformat(),
            status="pending_approval",
        )

        date_label = format_date_uk(selected_date, MONTHS_UK)
        time_str = data["selected_time"]
        phone = client.get("phone") or "—"
        name = f"{client['first_name']} {client.get('last_name') or ''}".strip()

        request_text = OFFHOURS_REQUEST_ADMIN.format(
            client=name,
            service=service["name"],
            date=date_label,
            time=time_str,
            phone=phone,
        )
        for aid in admin_ids:
            await bot.send_message(
                chat_id=aid,
                text=request_text,
                reply_markup=offhours_approve_keyboard(booking_id),
            )

        await call.message.edit_text(OFFHOURS_PENDING_SENT, reply_markup=main_menu_keyboard())
        await state.clear()
        await call.answer()
        return

    # --- Regular booking ---
    booking_id = await create_new_booking(
        db, calendar, client["id"], service, selected_date, selected_time
    )
    if not booking_id:
        await call.message.edit_text(SLOT_TAKEN, reply_markup=main_menu_keyboard())
        await state.clear()
        await call.answer()
        return

    from bot.models.database import get_booking
    booking = await get_booking(db, booking_id)
    start_utc = datetime.fromisoformat(booking["start_time"])
    reminder_service.schedule_reminders(booking_id, start_utc)

    start_kyiv = utc_to_kyiv(start_utc)
    end_kyiv = start_kyiv + timedelta(minutes=service["duration_minutes"])
    ics_bytes = generate_ics(
        service_name=service["name"],
        start=start_kyiv,
        end=end_kyiv,
        therapist_name=therapist_name,
        location=location,
    )

    date_label = format_date_uk(selected_date, MONTHS_UK)
    time_str = data["selected_time"]

    await call.message.edit_text(
        BOOKING_CONFIRMED.format(
            service=service["name"],
            date=date_label,
            time_start=time_str,
        ),
        reply_markup=main_menu_keyboard(),
    )

    filename = ICS_FILENAME.format(
        date=selected_date.isoformat(), time=time_str.replace(":", "")
    )
    await call.message.answer_document(
        BufferedInputFile(ics_bytes, filename=filename),
        caption="Додайте до вашого календаря",
    )

    phone = client.get("phone") or "—"
    name = f"{client['first_name']} {client.get('last_name') or ''}".strip()
    notify_text = NEW_BOOKING_ADMIN.format(
        client=name,
        service=service["name"],
        date=date_label,
        time=time_str,
        phone=phone,
    )
    for aid in admin_ids:
        await bot.send_message(chat_id=aid, text=notify_text)

    # Extra urgent notification if booking is within 30 minutes
    minutes_until = (start_kyiv - kyiv_now()).total_seconds() / 60
    if minutes_until <= 30:
        urgent_text = URGENT_BOOKING_ADMIN.format(
            client=name,
            service=service["name"],
            date=date_label,
            time=time_str,
            phone=phone,
        )
        for aid in admin_ids:
            await bot.send_message(chat_id=aid, text=urgent_text)

    await state.clear()
    await call.answer()


@router.callback_query(BookingStates.confirm, F.data == "confirm:no")
async def cancel_confirm(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Головне меню:", reply_markup=main_menu_keyboard())
    await call.answer()


@router.callback_query(F.data == "booking:back_to_service")
async def back_to_service(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    services = await get_active_services(db)
    await state.set_state(BookingStates.select_service)
    await call.message.edit_text(SELECT_SERVICE, reply_markup=services_keyboard(services))
    await call.answer()


@router.callback_query(F.data == "booking:back_to_time")
async def back_to_time(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
) -> None:
    data = await state.get_data()
    selected_date = date.fromisoformat(data["selected_date"])
    service = await get_service(db, data["service_id"])

    if data.get("requires_approval"):
        interval = int(await get_setting(db, "slot_interval_minutes") or "30")
        slots = generate_time_slots(
            selected_date, 7, 23, interval, service["duration_minutes"], 0
        )
    else:
        slots = await get_available_slots(db, calendar, selected_date, service["duration_minutes"])

    date_label = format_date_uk(selected_date, MONTHS_UK)
    await state.set_state(BookingStates.select_time)
    await call.message.edit_text(
        SELECT_TIME.format(date=date_label),
        reply_markup=times_keyboard(slots, data["selected_date"]),
    )
    await call.answer()


@router.callback_query(F.data == "booking:back_to_dates")
async def back_to_dates(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    available_dates = {date.fromisoformat(s) for s in data["available_dates"]}
    year, month = data["year"], data["month"]
    now = kyiv_now()
    has_prev = (year, month) > (now.year, now.month)
    await state.set_state(BookingStates.select_date)
    await call.message.edit_text(
        SELECT_DATE,
        reply_markup=dates_keyboard(available_dates, year, month, has_prev=has_prev),
    )
    await call.answer()


@router.callback_query(F.data == "menu:back")
async def main_menu_back(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Головне меню:", reply_markup=main_menu_keyboard())
    await call.answer()
