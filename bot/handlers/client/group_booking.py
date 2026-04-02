"""
Handles the "Записатись" button pressed in a Telegram group/channel
when a cancelled booking slot is announced.
"""
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.keyboards.client_kb import open_bot_keyboard
from bot.models.database import (
    create_pending_slot_claim,
    get_booking,
    get_client_by_telegram_id,
    get_group_slot,
    get_service,
    mark_group_slot_booked,
)
from bot.services.booking_service import create_new_booking
from bot.services.calendar_service import CalendarService
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import (
    GROUP_BOOKING_ALREADY_TAKEN,
    GROUP_BOOKING_NOT_REGISTERED,
    GROUP_BOOKING_SUCCESS,
    GROUP_SLOT_BOOKED,
    ICS_FILENAME,
    MONTHS_UK,
    NEW_BOOKING_ADMIN,
)

router = Router()


@router.callback_query(F.data.startswith("book_slot:"))
async def handle_group_book(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    bot: Bot,
    calendar: CalendarService,
    reminder_service: ReminderService,
    admin_ids: list[int],
    therapist_name: str,
    location: str,
    bot_username: str,
) -> None:
    slot_id = int(call.data.split(":")[1])
    slot = await get_group_slot(db, slot_id)

    if not slot or slot["is_booked"]:
        await call.answer(GROUP_BOOKING_ALREADY_TAKEN, show_alert=True)
        return

    client = await get_client_by_telegram_id(db, call.from_user.id)

    if not client or not client.get("phone"):
        # User not registered — save pending claim and send instructions
        await create_pending_slot_claim(db, call.from_user.id, slot_id)
        await call.answer(GROUP_BOOKING_NOT_REGISTERED, show_alert=True)
        try:
            await call.message.answer(
                GROUP_BOOKING_NOT_REGISTERED,
                reply_markup=open_bot_keyboard(bot_username, slot_id),
            )
        except Exception:
            pass
        return

    # User is registered — book immediately
    service = await get_service(db, slot["service_id"])
    if not service:
        await call.answer("Послугу не знайдено.", show_alert=True)
        return

    start_utc = datetime.fromisoformat(slot["start_time"])
    start_kyiv = utc_to_kyiv(start_utc)
    end_kyiv = utc_to_kyiv(datetime.fromisoformat(slot["end_time"]))

    booking_id = await create_new_booking(
        db, calendar, client["id"], service,
        start_kyiv.date(), start_kyiv.time(),
        skip_availability_check=True,
    )
    if not booking_id:
        await call.answer(GROUP_BOOKING_ALREADY_TAKEN, show_alert=True)
        return

    await mark_group_slot_booked(db, slot_id)

    # Edit group message to show it's taken
    try:
        await call.message.edit_text(GROUP_SLOT_BOOKED)
    except Exception:
        pass

    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_label = format_time(start_kyiv.time())

    await call.answer(
        GROUP_BOOKING_SUCCESS.format(
            service=service["name"],
            date=date_label,
            time_start=time_label,
        ),
        show_alert=True,
    )

    # Schedule reminders
    booking = await get_booking(db, booking_id)
    if booking:
        booking_start_utc = datetime.fromisoformat(booking["start_time"])
        reminder_service.schedule_reminders(booking_id, booking_start_utc)

    # Send ICS to user in DM
    ics_bytes = generate_ics(
        service_name=service["name"],
        start=start_kyiv,
        end=end_kyiv,
        therapist_name=therapist_name,
        location=location,
    )
    filename = ICS_FILENAME.format(
        date=start_kyiv.date().isoformat(),
        time=start_kyiv.strftime("%H%M"),
    )
    try:
        await bot.send_document(
            chat_id=call.from_user.id,
            document=BufferedInputFile(ics_bytes, filename=filename),
            caption=f"Ваш запис: {service['name']}, {date_label} о {time_label}",
        )
    except Exception:
        pass

    # Notify admins
    name = f"{client['first_name']} {client.get('last_name') or ''}".strip()
    phone = client.get("phone") or "—"
    notify_text = NEW_BOOKING_ADMIN.format(
        client=name,
        service=service["name"],
        date=date_label,
        time=time_label,
        phone=phone,
    )
    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=notify_text)
        except Exception:
            pass
