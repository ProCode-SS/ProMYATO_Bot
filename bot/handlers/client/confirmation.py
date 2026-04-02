from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot.models.database import confirm_booking_by_reminder, get_booking
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import (
    MONTHS_UK,
    REMINDER_CONFIRM_ADMIN,
    REMINDER_CONFIRMED,
)

router = Router()


@router.callback_query(F.data.startswith("confirm_reminder:"))
async def handle_reminder_confirmation(
    call: CallbackQuery,
    db: aiosqlite.Connection,
    bot: Bot,
    admin_ids: list[int],
) -> None:
    booking_id = int(call.data.split(":")[1])
    booking = await get_booking(db, booking_id)

    if not booking or booking["status"] != "confirmed":
        await call.answer("Запис вже не актуальний.", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if booking["confirmed_at"]:
        await call.answer("Ви вже підтвердили цей запис.", show_alert=True)
        return

    confirmed_at = datetime.now(timezone.utc).isoformat()
    await confirm_booking_by_reminder(db, booking_id, confirmed_at)

    await call.answer(REMINDER_CONFIRMED, show_alert=True)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
    name = f"{booking['first_name']} {booking.get('last_name') or ''}".strip()
    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_label = format_time(start_kyiv.time())

    notify_text = REMINDER_CONFIRM_ADMIN.format(
        client=name,
        service=booking["service_name"],
        date=date_label,
        time=time_label,
    )
    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=notify_text)
        except Exception:
            pass
