from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.admin_kb import admin_menu_keyboard
from bot.models.database import get_booking, get_today_bookings, get_week_bookings
from bot.services.booking_service import cancel_existing_booking
from bot.services.calendar_service import CalendarService
from bot.services.group_notify import notify_group_cancellation
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import ICS_FILENAME, MONTHS_UK, NO_BOOKINGS_TODAY, NO_BOOKINGS_WEEK

router = Router()


def _booking_line(b: dict) -> str:
    start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
    time_str = format_time(start_kyiv.time())
    name = f"{b['first_name']} {b.get('last_name') or ''}".strip()
    phone = b.get("phone") or "—"
    confirmed = " ✅" if b.get("confirmed_at") else ""
    return f"{time_str} — {name} — {b['service_name']} {b['duration_minutes']}хв — {phone}{confirmed}"


def _bookings_keyboard(bookings: list[dict], source: str):
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text="📅 ICS", callback_data=f"admin:ics:{b['id']}")
        kb.button(text="❌ Скасувати", callback_data=f"admin:cancel:{source}:{b['id']}")
    kb.button(text="Назад", callback_data="admin:menu")
    kb.adjust(*([2] * len(bookings)), 1)
    return kb.as_markup()


@router.callback_query(F.data == "admin:today")
async def today_bookings(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    bookings = await get_today_bookings(db)
    if not bookings:
        await call.message.edit_text(NO_BOOKINGS_TODAY, reply_markup=admin_menu_keyboard())
        await call.answer()
        return

    lines = ["Записи на сьогодні:\n"]
    for b in bookings:
        lines.append(_booking_line(b))

    await call.message.edit_text(
        "\n".join(lines), reply_markup=_bookings_keyboard(bookings, "today")
    )
    await call.answer()


@router.callback_query(F.data == "admin:week")
async def week_bookings(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    bookings = await get_week_bookings(db)
    if not bookings:
        await call.message.edit_text(NO_BOOKINGS_WEEK, reply_markup=admin_menu_keyboard())
        await call.answer()
        return

    lines = ["Записи на тиждень:\n"]
    current_date = None
    for b in bookings:
        start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
        d = start_kyiv.date()
        if d != current_date:
            current_date = d
            lines.append(f"\n{format_date_uk(d, MONTHS_UK)}")
        lines.append(_booking_line(b))

    await call.message.edit_text(
        "\n".join(lines), reply_markup=_bookings_keyboard(bookings, "week")
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin:ics:"))
async def admin_send_ics(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    therapist_name: str,
    location: str,
) -> None:
    booking_id = int(call.data.split(":")[-1])
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
        caption=f"{booking['first_name']} — {booking['service_name']}, {format_date_uk(start_kyiv.date(), MONTHS_UK)} {format_time(start_kyiv.time())}",
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin:cancel:"))
async def admin_cancel_booking(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    cancellation_group_id: str,
) -> None:
    parts = call.data.split(":")
    source = parts[2]
    booking_id = int(parts[3])

    booking = await get_booking(db, booking_id)
    success = await cancel_existing_booking(db, calendar, booking_id)
    if success:
        reminder_service.cancel_reminders(booking_id)
        await call.answer("Запис скасовано.", show_alert=True)

        if booking:
            # Determine urgency
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
        await call.answer("Не вдалось скасувати.", show_alert=True)

    if source == "week":
        bookings = await get_week_bookings(db)
        if not bookings:
            await call.message.edit_text(NO_BOOKINGS_WEEK, reply_markup=admin_menu_keyboard())
            return
        lines = ["Записи на тиждень:\n"]
        current_date = None
        for b in bookings:
            start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
            d = start_kyiv.date()
            if d != current_date:
                current_date = d
                lines.append(f"\n{format_date_uk(d, MONTHS_UK)}")
            lines.append(_booking_line(b))
        await call.message.edit_text(
            "\n".join(lines), reply_markup=_bookings_keyboard(bookings, "week")
        )
    else:
        bookings = await get_today_bookings(db)
        if not bookings:
            await call.message.edit_text(NO_BOOKINGS_TODAY, reply_markup=admin_menu_keyboard())
            return
        lines = ["Записи на сьогодні:\n"]
        for b in bookings:
            lines.append(_booking_line(b))
        await call.message.edit_text(
            "\n".join(lines), reply_markup=_bookings_keyboard(bookings, "today")
        )
