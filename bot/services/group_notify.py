"""
Helper for sending cancelled slot notifications to the cancellation group.
Used by my_bookings, admin/bookings, and reminder_service.
"""
import logging
from datetime import datetime

import aiosqlite
from aiogram import Bot

from bot.keyboards.client_kb import group_book_keyboard
from bot.models.database import create_group_slot, update_group_slot_message
from bot.utils.datetime_helpers import format_date_uk, format_time, kyiv_now, utc_to_kyiv
from bot.utils.texts import (
    GROUP_SLOT_AVAILABLE,
    GROUP_SLOT_AVAILABLE_URGENT,
    MONTHS_UK,
)

logger = logging.getLogger(__name__)


async def notify_group_cancellation(
    bot: Bot,
    db: aiosqlite.Connection,
    cancellation_group_id: str,
    booking: dict,
    is_urgent: bool = False,
) -> None:
    """Send freed slot to the cancellation group with a 'Book' button."""
    if not cancellation_group_id:
        return

    start_utc = datetime.fromisoformat(booking["start_time"])
    end_utc = datetime.fromisoformat(booking["end_time"])
    start_kyiv = utc_to_kyiv(start_utc)
    end_kyiv = utc_to_kyiv(end_utc)

    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_start_label = format_time(start_kyiv.time())
    time_end_label = format_time(end_kyiv.time())

    price_line = f"💰 {booking['price']}₴" if booking.get("price") else ""
    template = GROUP_SLOT_AVAILABLE_URGENT if is_urgent else GROUP_SLOT_AVAILABLE
    text = template.format(
        service=booking["service_name"],
        date=date_label,
        time_start=time_start_label,
        time_end=time_end_label,
        price_line=price_line,
    )

    slot_id = await create_group_slot(
        db,
        service_id=booking["service_id"],
        start_time=booking["start_time"],
        end_time=booking["end_time"],
    )

    now_hour = kyiv_now().hour
    silent = now_hour >= 23 or now_hour < 8

    try:
        sent = await bot.send_message(
            chat_id=int(cancellation_group_id),
            text=text,
            reply_markup=group_book_keyboard(slot_id),
            disable_notification=silent,
        )
        await update_group_slot_message(db, slot_id, sent.message_id, sent.chat.id)
    except Exception as e:
        logger.error("Failed to send cancellation group notification: %s", e)
