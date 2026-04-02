from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.keyboards.client_kb import cancel_confirm_keyboard, main_menu_keyboard, my_bookings_keyboard
from bot.models.database import get_booking, get_client_by_telegram_id, get_client_upcoming_bookings
from bot.services.booking_service import cancel_existing_booking
from bot.services.calendar_service import CalendarService
from bot.services.group_notify import notify_group_cancellation
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.states.booking import MyBookingsStates
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import (
    BOOKING_CANCELLED,
    CANCEL_BOOKING_ADMIN,
    CANCEL_CONFIRM_Q,
    ICS_FILENAME,
    MONTHS_UK,
    MY_BOOKINGS_EMPTY,
    MY_BOOKINGS_HEADER,
)

router = Router()


@router.callback_query(F.data == "menu:mybookings")
async def my_bookings(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    client = await get_client_by_telegram_id(db, call.from_user.id)
    if not client:
        await call.answer("Спочатку зареєструйтесь через /start", show_alert=True)
        return

    bookings = await get_client_upcoming_bookings(db, client["id"])
    if not bookings:
        await call.message.edit_text(MY_BOOKINGS_EMPTY, reply_markup=main_menu_keyboard())
        await call.answer()
        return

    lines = [MY_BOOKINGS_HEADER]
    for b in bookings:
        start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
        confirmed = " ✅" if b.get("confirmed_at") else ""
        lines.append(
            f"\n{format_date_uk(start_kyiv.date(), MONTHS_UK)} "
            f"{format_time(start_kyiv.time())} — {b['service_name']}{confirmed}"
        )

    await state.set_state(MyBookingsStates.view)
    await call.message.edit_text(
        "\n".join(lines), reply_markup=my_bookings_keyboard(bookings)
    )
    await call.answer()


@router.callback_query(MyBookingsStates.view, F.data.startswith("ics:"))
async def send_ics(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    therapist_name: str,
    location: str,
) -> None:
    booking_id = int(call.data.split(":")[1])
    booking = await get_booking(db, booking_id)
    if not booking:
        await call.answer("Запис не знайдено.", show_alert=True)
        return

    start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
    end_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["end_time"]))
    ics_bytes = generate_ics(
        service_name=booking["service_name"],
        start=start_kyiv,
        end=end_kyiv,
        therapist_name=therapist_name,
        location=location,
    )
    filename = ICS_FILENAME.format(
        date=start_kyiv.date().isoformat(),
        time=start_kyiv.strftime("%H%M"),
    )
    await call.message.answer_document(
        BufferedInputFile(ics_bytes, filename=filename),
        caption="Додайте до вашого календаря",
    )
    await call.answer()


@router.callback_query(MyBookingsStates.view, F.data.startswith("cancel:"))
async def cancel_booking_request(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    booking_id = int(call.data.split(":")[1])
    booking = await get_booking(db, booking_id)
    if not booking:
        await call.answer("Запис не знайдено.", show_alert=True)
        return

    start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_label = format_time(start_kyiv.time())

    await state.update_data(cancel_booking_id=booking_id)
    await state.set_state(MyBookingsStates.confirm_cancel)
    await call.message.edit_text(
        CANCEL_CONFIRM_Q.format(date=date_label, time=time_label),
        reply_markup=cancel_confirm_keyboard(booking_id),
    )
    await call.answer()


@router.callback_query(MyBookingsStates.confirm_cancel, F.data.startswith("cancel_yes:"))
async def confirm_cancel(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    admin_ids: list[int],
    cancellation_group_id: str,
) -> None:
    booking_id = int(call.data.split(":")[1])
    client = await get_client_by_telegram_id(db, call.from_user.id)
    booking = await get_booking(db, booking_id)

    success = await cancel_existing_booking(
        db, calendar, booking_id, client_id=client["id"] if client else None
    )
    if success:
        reminder_service.cancel_reminders(booking_id)
        await call.message.edit_text(BOOKING_CANCELLED, reply_markup=main_menu_keyboard())

        start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
        name = f"{booking['first_name']} {booking.get('last_name') or ''}".strip()
        date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
        time_label = format_time(start_kyiv.time())

        cancel_text = CANCEL_BOOKING_ADMIN.format(
            client=name,
            service=booking["service_name"],
            date=date_label,
            time=time_label,
        )
        for aid in admin_ids:
            await bot.send_message(chat_id=aid, text=cancel_text)

        # Determine urgency: confirmed + less than 12h until appointment
        now = datetime.now(timezone.utc)
        start_utc = datetime.fromisoformat(booking["start_time"])
        if not start_utc.tzinfo:
            from zoneinfo import ZoneInfo
            start_utc = start_utc.replace(tzinfo=ZoneInfo("UTC"))
        hours_until = (start_utc - now).total_seconds() / 3600
        is_urgent = bool(booking.get("confirmed_at")) and hours_until < 12

        await notify_group_cancellation(
            bot, db, cancellation_group_id, booking, is_urgent=is_urgent
        )
    else:
        await call.message.edit_text(
            "Не вдалось скасувати запис.", reply_markup=main_menu_keyboard()
        )

    await state.clear()
    await call.answer()


@router.callback_query(MyBookingsStates.confirm_cancel, F.data == "cancel_no")
async def keep_booking(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    await state.clear()
    client = await get_client_by_telegram_id(db, call.from_user.id)
    bookings = await get_client_upcoming_bookings(db, client["id"])
    if not bookings:
        await call.message.edit_text(MY_BOOKINGS_EMPTY, reply_markup=main_menu_keyboard())
    else:
        await call.message.edit_text(
            MY_BOOKINGS_HEADER, reply_markup=my_bookings_keyboard(bookings)
        )
    await call.answer()
