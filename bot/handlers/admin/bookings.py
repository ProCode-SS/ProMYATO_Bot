from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.admin_kb import admin_menu_keyboard
from bot.models.database import (
    approve_pending_booking,
    get_booking,
    get_pending_approval_bookings,
    get_today_bookings,
    get_week_bookings,
    is_bookings_open,
    reject_pending_booking,
    set_setting,
)
from bot.services.booking_service import cancel_existing_booking
from bot.services.calendar_service import CalendarService
from bot.services.group_notify import notify_group_cancellation
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import (
    BOOKINGS_TOGGLE_CLOSED,
    BOOKINGS_TOGGLE_OPENED,
    ICS_FILENAME,
    MONTHS_UK,
    NO_BOOKINGS_TODAY,
    NO_BOOKINGS_WEEK,
    NO_PENDING_APPROVALS,
    OFFHOURS_APPROVED_ADMIN,
    OFFHOURS_APPROVED_CLIENT,
    OFFHOURS_REJECTED_ADMIN,
    OFFHOURS_REJECTED_CLIENT,
    WEEKDAY_HEADERS,
)

router = Router()


def _bookings_display(
    bookings: list[dict], source: str, header: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Returns (message_text, keyboard) with booking details in text, action buttons in keyboard."""
    lines = [header, ""]
    kb_rows = []
    for b in bookings:
        start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
        day_abbr = WEEKDAY_HEADERS[start_kyiv.weekday()]
        name = f"{b['first_name']} {b.get('last_name') or ''}".strip()
        phone = b.get("phone") or "—"
        confirmed = " ✅" if b.get("confirmed_at") else ""
        time_str = format_time(start_kyiv.time())
        date_str = f"{start_kyiv.day} {MONTHS_UK[start_kyiv.month]}"

        lines.append(f"<b>{day_abbr} {date_str}, {time_str}</b> — {name}{confirmed}")
        lines.append(f"{b['service_name']} {b['duration_minutes']}хв")
        lines.append(f"📞 {phone}")
        lines.append("")

        btn = f"{day_abbr} {time_str}"
        kb_rows.append([
            InlineKeyboardButton(text=f"📅 {btn}", callback_data=f"admin:ics:{b['id']}"),
            InlineKeyboardButton(text=f"❌ {btn}", callback_data=f"admin:cancel:{source}:{b['id']}"),
        ])

    kb_rows.append([InlineKeyboardButton(text="← Назад", callback_data="admin:menu")])
    return "\n".join(lines).rstrip(), InlineKeyboardMarkup(inline_keyboard=kb_rows)


def _pending_display(bookings: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    """Returns (message_text, keyboard) for pending approval bookings."""
    lines = [f"Запити на схвалення ({len(bookings)}):", ""]
    kb_rows = []
    for b in bookings:
        start_kyiv = utc_to_kyiv(datetime.fromisoformat(b["start_time"]))
        day_abbr = WEEKDAY_HEADERS[start_kyiv.weekday()]
        name = f"{b['first_name']} {b.get('last_name') or ''}".strip()
        phone = b.get("phone") or "—"
        time_str = format_time(start_kyiv.time())
        date_str = f"{start_kyiv.day} {MONTHS_UK[start_kyiv.month]}"

        lines.append(f"<b>{day_abbr} {date_str}, {time_str}</b>")
        lines.append(f"💆 {b['service_name']} {b['duration_minutes']}хв")
        lines.append(f"👤 {name}")
        lines.append(f"📞 {phone}")
        lines.append("")

        btn = f"{day_abbr} {time_str}"
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ {btn}", callback_data=f"offhours:approve:{b['id']}"),
            InlineKeyboardButton(text=f"❌ {btn}", callback_data=f"offhours:reject:{b['id']}"),
        ])

    kb_rows.append([InlineKeyboardButton(text="← Назад", callback_data="admin:menu")])
    return "\n".join(lines).rstrip(), InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.callback_query(F.data == "admin:today")
async def today_bookings(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    bookings = await get_today_bookings(db)
    if not bookings:
        await call.message.edit_text(
            NO_BOOKINGS_TODAY, reply_markup=admin_menu_keyboard(await is_bookings_open(db))
        )
        await call.answer()
        return

    text, kb = _bookings_display(bookings, "today", f"Записи на сьогодні ({len(bookings)}):")
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "admin:week")
async def week_bookings(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    bookings = await get_week_bookings(db)
    if not bookings:
        await call.message.edit_text(
            NO_BOOKINGS_WEEK, reply_markup=admin_menu_keyboard(await is_bookings_open(db))
        )
        await call.answer()
        return

    text, kb = _bookings_display(bookings, "week", f"Записи на тиждень ({len(bookings)}):")
    await call.message.edit_text(text, reply_markup=kb)
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
            now = datetime.now(timezone.utc)
            start_utc = datetime.fromisoformat(booking["start_time"])
            if not start_utc.tzinfo:
                start_utc = start_utc.replace(tzinfo=ZoneInfo("UTC"))
            hours_until = (start_utc - now).total_seconds() / 3600
            is_urgent = bool(booking.get("confirmed_at")) and hours_until < 12

            await notify_group_cancellation(
                bot, db, cancellation_group_id, booking, is_urgent=is_urgent
            )
    else:
        await call.answer("Не вдалось скасувати.", show_alert=True)

    open_status = await is_bookings_open(db)
    if source == "week":
        bookings = await get_week_bookings(db)
        if not bookings:
            await call.message.edit_text(NO_BOOKINGS_WEEK, reply_markup=admin_menu_keyboard(open_status))
            return
        text, kb = _bookings_display(bookings, "week", f"Записи на тиждень ({len(bookings)}):")
        await call.message.edit_text(text, reply_markup=kb)
    else:
        bookings = await get_today_bookings(db)
        if not bookings:
            await call.message.edit_text(NO_BOOKINGS_TODAY, reply_markup=admin_menu_keyboard(open_status))
            return
        text, kb = _bookings_display(bookings, "today", f"Записи на сьогодні ({len(bookings)}):")
        await call.message.edit_text(text, reply_markup=kb)


# ─── Toggle bookings open/closed ─────────────────────────────────────────────

@router.callback_query(F.data == "admin:toggle_bookings")
async def toggle_bookings(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    current_open = await is_bookings_open(db)
    new_state = "0" if current_open else "1"
    await set_setting(db, "bookings_open", new_state)
    msg = BOOKINGS_TOGGLE_CLOSED if new_state == "0" else BOOKINGS_TOGGLE_OPENED
    await call.answer(msg, show_alert=True)
    await call.message.edit_text(
        "Адмін-панель:", reply_markup=admin_menu_keyboard(new_state == "1")
    )


# ─── Pending approval bookings list ──────────────────────────────────────────

@router.callback_query(F.data == "admin:pending")
async def pending_approvals(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    bookings = await get_pending_approval_bookings(db)
    if not bookings:
        await call.message.edit_text(
            NO_PENDING_APPROVALS, reply_markup=admin_menu_keyboard(await is_bookings_open(db))
        )
        await call.answer()
        return

    text, kb = _pending_display(bookings)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Off-hours approve / reject ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("offhours:approve:"))
async def offhours_approve(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    therapist_name: str,
    location: str,
) -> None:
    booking_id = int(call.data.split(":")[-1])
    booking = await get_booking(db, booking_id)

    if not booking or booking["status"] != "pending_approval":
        await call.answer("Запит вже не актуальний.", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
    end_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["end_time"]))

    try:
        event_id = await calendar.create_event(
            summary=f"Масаж: {booking['service_name']}",
            start=start_kyiv,
            end=end_kyiv,
        )
    except Exception:
        event_id = None

    await approve_pending_booking(db, booking_id, google_event_id=event_id)

    start_utc = datetime.fromisoformat(booking["start_time"])
    if not start_utc.tzinfo:
        start_utc = start_utc.replace(tzinfo=ZoneInfo("UTC"))
    reminder_service.schedule_reminders(booking_id, start_utc)

    ics_bytes = generate_ics(
        service_name=booking["service_name"],
        start=start_kyiv,
        end=end_kyiv,
        therapist_name=therapist_name,
        location=location,
    )
    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_label = format_time(start_kyiv.time())
    filename = ICS_FILENAME.format(
        date=start_kyiv.date().isoformat(),
        time=start_kyiv.strftime("%H%M"),
    )

    telegram_id = booking.get("telegram_id")
    if telegram_id and telegram_id > 0:
        await bot.send_message(
            chat_id=telegram_id,
            text=OFFHOURS_APPROVED_CLIENT.format(
                service=booking["service_name"],
                date=date_label,
                time_start=time_label,
            ),
        )
        await bot.send_document(
            chat_id=telegram_id,
            document=BufferedInputFile(ics_bytes, filename=filename),
            caption="Додайте до вашого календаря",
        )

    name = f"{booking['first_name']} {booking.get('last_name') or ''}".strip()
    await call.message.edit_text(
        f"✅ Підтверджено: {name} — {booking['service_name']}, {date_label} {time_label}",
        reply_markup=None,
    )
    await call.answer(OFFHOURS_APPROVED_ADMIN)


@router.callback_query(F.data.startswith("offhours:reject:"))
async def offhours_reject(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    bot: Bot,
) -> None:
    booking_id = int(call.data.split(":")[-1])
    booking = await get_booking(db, booking_id)

    if not booking or booking["status"] != "pending_approval":
        await call.answer("Запит вже не актуальний.", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    await reject_pending_booking(db, booking_id)

    telegram_id = booking.get("telegram_id")
    if telegram_id and telegram_id > 0:
        start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
        await bot.send_message(
            chat_id=telegram_id,
            text=OFFHOURS_REJECTED_CLIENT.format(
                service=booking["service_name"],
                date=format_date_uk(start_kyiv.date(), MONTHS_UK),
                time=format_time(start_kyiv.time()),
            ),
        )

    name = f"{booking['first_name']} {booking.get('last_name') or ''}".strip()
    await call.message.edit_text(
        f"❌ Відхилено: {name} — {booking['service_name']}",
        reply_markup=None,
    )
    await call.answer(OFFHOURS_REJECTED_ADMIN)
